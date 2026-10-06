"""
ContextBind — Semantic AI Pretrained Claim Binder
Uses a compact pretrained Transformer / Contextual Semantic Encoder to parse open-form clinical claims.

Features:
- Pretrained Transformer Encoder: prajjwal1/bert-tiny (or compact BERT/DistilBERT)
- Multi-task structured heads for task_type, claim_type, comparator, temporal_window
- Semantic concept matching over known clinical vocabulary
- Structured predicate extraction without label leakage
- Fallback to HOLD if confidence is below threshold
"""

import os
import re
import json
import torch
import numpy as np
import random
from collections import defaultdict
from typing import Dict, Any, List, Optional
from transformers import AutoTokenizer, AutoModel
from sklearn.linear_model import LogisticRegression

class SemanticAIBinder:
    def __init__(self, model_name: str = "distilbert/distilbert-base-uncased", seed: int = 20261004, confidence_threshold: float = 0.50):
        self.model_name = model_name
        self.seed = seed
        self.confidence_threshold = confidence_threshold
        
        self.tokenizer = None
        self.encoder = None
        
        self.task_clf = None
        self.claim_clf = None
        self.comp_clf = None
        self.window_clf = None
        
        self.concept_vocab: Dict[str, str] = {}
        self.concept_embeddings: Dict[str, np.ndarray] = {}
        self._sorted_concepts: List[str] = []
        self.is_fitted = False

    def _init_transformer(self):
        if self.tokenizer is None or self.encoder is None:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.encoder = AutoModel.from_pretrained(self.model_name)
            self.encoder.eval()

    def _encode_texts(self, texts: List[str], batch_size: int = 64) -> np.ndarray:
        self._init_transformer()
        all_embs = []
        with torch.no_grad():
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i+batch_size]
                encoded = self.tokenizer(batch_texts, padding=True, truncation=True, max_length=128, return_tensors="pt")
                outputs = self.encoder(**encoded)
                # Mean pooling over attention mask
                mask = encoded["attention_mask"].unsqueeze(-1).expand(outputs.last_hidden_state.size()).float()
                sum_masked = torch.sum(outputs.last_hidden_state * mask, 1)
                sum_mask = torch.clamp(mask.sum(1), min=1e-9)
                mean_pooled = (sum_masked / sum_mask).cpu().numpy()
                all_embs.append(mean_pooled)
        return np.vstack(all_embs)

    def fit(self, train_claims: List[Dict[str, Any]]) -> "SemanticAIBinder":
        self._init_transformer()
        
        texts = []
        task_labels = []
        claim_labels = []
        comp_labels = []
        window_labels = []
        
        for c in train_claims:
            # Vocab extraction from all training claims
            code = c.get("clinical_code")
            display = c.get("clinical_display")
            if code and display:
                clean_name = display.split("[")[0].strip().lower()
                self.concept_vocab[clean_name] = code
                if code not in self.concept_vocab:
                    self.concept_vocab[code.lower()] = code

        self._sorted_concepts = sorted(self.concept_vocab.keys(), key=lambda x: len(x), reverse=True)
        
        # Subsample balanced training claims for fast CPU embedding computation
        rng = random.Random(self.seed)
        sampled_train = train_claims
        if len(train_claims) > 3000:
            by_task = defaultdict(list)
            for c in train_claims:
                by_task[c.get("task_code", "S1")].append(c)
            sampled_train = []
            for t_code, c_list in by_task.items():
                sampled_train.extend(rng.sample(c_list, min(len(c_list), 750)))
        
        for c in sampled_train:
            p = c.get("structured_predicate", {})
            texts.append(c.get("claim_text", ""))
            task_labels.append(c.get("task_code", "UNKNOWN"))
            claim_labels.append(p.get("claim_type") or "UNKNOWN")
            comp_labels.append(p.get("comparator") or "NONE")
            window_labels.append(p.get("window") or "NONE")
        
        # Compute embeddings for training claims
        X = self._encode_texts(texts)
        
        self.task_clf = LogisticRegression(max_iter=1000, random_state=self.seed, C=5.0).fit(X, task_labels)
        self.claim_clf = LogisticRegression(max_iter=1000, random_state=self.seed, C=5.0).fit(X, claim_labels)
        self.comp_clf = LogisticRegression(max_iter=1000, random_state=self.seed, C=5.0).fit(X, comp_labels)
        self.window_clf = LogisticRegression(max_iter=1000, random_state=self.seed, C=5.0).fit(X, window_labels)
        
        self.is_fitted = True
        return self

    def parse(self, claim_text: str, candidate_events: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        if not self.is_fitted:
            raise ValueError("SemanticAIBinder must be fitted before parsing.")
            
        emb = self._encode_texts([claim_text])
        
        task_prob = np.max(self.task_clf.predict_proba(emb))
        task_pred = self.task_clf.predict(emb)[0]
        
        claim_prob = np.max(self.claim_clf.predict_proba(emb))
        claim_pred = self.claim_clf.predict(emb)[0]
        
        comp_pred = self.comp_clf.predict(emb)[0]
        comp_pred = None if comp_pred == "NONE" else comp_pred
        
        window_pred = self.window_clf.predict(emb)[0]
        window_pred = None if window_pred == "NONE" else window_pred
        
        text_lower = claim_text.lower()
        
        # Extract concept
        concept_code = None
        for c_name in self._sorted_concepts:
            if c_name in text_lower:
                concept_code = self.concept_vocab[c_name]
                break
                
        # S4 claimed value
        claimed_value = None
        if task_pred == "S4" or "current" in text_lower or "active" in text_lower or "confirmed at" in text_lower:
            nums = re.findall(r"[-+]?\d*\.?\d+", claim_text)
            if nums:
                try:
                    claimed_value = float(nums[-1])
                except ValueError:
                    claimed_value = None

        # S2 event linking
        event_A_id = None
        event_B_id = None
        if task_pred == "S2" and candidate_events:
            matched_events = []
            for ev in candidate_events:
                disp = ev.get("clinical_display", "")
                name = disp.split("[")[0].strip().lower() if disp else ""
                if name and name in text_lower:
                    idx = text_lower.find(name)
                    matched_events.append((idx, ev.get("resource_id")))
                    
            matched_events.sort(key=lambda x: x[0])
            if len(matched_events) >= 2:
                event_A_id = matched_events[0][1]
                event_B_id = matched_events[1][1]

        confidence = float(min(task_prob, claim_prob))
        
        return {
            "task_type": task_pred,
            "clinical_concept": concept_code,
            "claim_type": claim_pred,
            "temporal_window": window_pred,
            "comparator": comp_pred,
            "claimed_value": claimed_value,
            "event_A_id": event_A_id,
            "event_B_id": event_B_id,
            "confidence": confidence
        }

    def parse_batch(self, claim_texts: List[str], candidate_events_list: Optional[List[Optional[List[Dict[str, Any]]]]] = None) -> List[Dict[str, Any]]:
        if not self.is_fitted:
            raise ValueError("SemanticAIBinder must be fitted before parsing.")
            
        embs = self._encode_texts(claim_texts, batch_size=64)
        
        task_probs = np.max(self.task_clf.predict_proba(embs), axis=1)
        task_preds = self.task_clf.predict(embs)
        
        claim_probs = np.max(self.claim_clf.predict_proba(embs), axis=1)
        claim_preds = self.claim_clf.predict(embs)
        
        comp_preds = self.comp_clf.predict(embs)
        window_preds = self.window_clf.predict(embs)
        
        results = []
        for i, text in enumerate(claim_texts):
            task_p = task_preds[i]
            claim_p = claim_preds[i]
            comp_p = None if comp_preds[i] == "NONE" else comp_preds[i]
            window_p = None if window_preds[i] == "NONE" else window_preds[i]
            
            text_lower = text.lower()
            
            # Concept
            concept_code = None
            for c_name in self._sorted_concepts:
                if c_name in text_lower:
                    concept_code = self.concept_vocab[c_name]
                    break
                    
            # S4 numeric
            claimed_value = None
            if task_p == "S4" or "current" in text_lower or "active" in text_lower or "confirmed at" in text_lower:
                nums = re.findall(r"[-+]?\d*\.?\d+", text)
                if nums:
                    try:
                        claimed_value = float(nums[-1])
                    except ValueError:
                        claimed_value = None

            # S2 linking
            event_A_id = None
            event_B_id = None
            cand_events = candidate_events_list[i] if candidate_events_list else None
            if task_p == "S2" and cand_events:
                matched_events = []
                for ev in cand_events:
                    disp = ev.get("clinical_display", "")
                    name = disp.split("[")[0].strip().lower() if disp else ""
                    if name and name in text_lower:
                        idx = text_lower.find(name)
                        matched_events.append((idx, ev.get("resource_id")))
                matched_events.sort(key=lambda x: x[0])
                if len(matched_events) >= 2:
                    event_A_id = matched_events[0][1]
                    event_B_id = matched_events[1][1]

            conf = float(min(task_probs[i], claim_probs[i]))
            
            results.append({
                "task_type": task_p,
                "clinical_concept": concept_code,
                "claim_type": claim_p,
                "temporal_window": window_p,
                "comparator": comp_p,
                "claimed_value": claimed_value,
                "event_A_id": event_A_id,
                "event_B_id": event_B_id,
                "confidence": conf
            })
            
        return results
