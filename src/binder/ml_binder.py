"""
ContextBind — Machine Learning Semantic Claim Binder
Uses Word + Character TF-IDF and Logistic Regression heads for semantic intent & relation classification,
combined with deterministic slot-filling for entity and numeric arguments.
"""

import re
from typing import Dict, Any, Optional, List
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion

class MLClaimBinder:
    def __init__(self, c_reg: float = 1.0, seed: int = 20261004):
        self.c_reg = c_reg
        self.seed = seed
        self.vectorizer = FeatureUnion([
            ("word_tfidf", TfidfVectorizer(ngram_range=(1, 2), analyzer="word", lowercase=True, max_features=5000)),
            ("char_tfidf", TfidfVectorizer(ngram_range=(3, 5), analyzer="char", lowercase=True, max_features=5000))
        ])
        self.clf_task = LogisticRegression(C=c_reg, max_iter=250, random_state=seed)
        self.clf_claim_type = LogisticRegression(C=c_reg, max_iter=250, random_state=seed)
        self.clf_comparator = LogisticRegression(C=c_reg, max_iter=250, random_state=seed)
        
        self.concept_vocab: Dict[str, str] = {}
        self._sorted_concepts: List[str] = []
        self.is_fitted = False

    def fit(self, train_claims: List[Dict[str, Any]]) -> "MLClaimBinder":
        """
        Trains semantic heads strictly on TRAIN partition.
        """
        texts = [c["claim_text"] for c in train_claims]
        y_task = [c["task_code"] for c in train_claims]
        y_claim_type = [c["structured_predicate"]["claim_type"] for c in train_claims]
        y_comparator = [c["structured_predicate"].get("comparator") or "NONE" for c in train_claims]

        # Fit TF-IDF feature space
        X = self.vectorizer.fit_transform(texts)

        # Train separate classification heads
        self.clf_task.fit(X, y_task)
        self.clf_claim_type.fit(X, y_claim_type)
        self.clf_comparator.fit(X, y_comparator)

        # Build concept vocabulary from training split
        vocab = {}
        for c in train_claims:
            code = c.get("clinical_code")
            disp = c.get("clinical_display", "")
            if code and disp:
                clean = disp.split("[")[0].strip().lower()
                if clean and clean not in vocab:
                    vocab[clean] = code

        self.concept_vocab = vocab
        self._sorted_concepts = sorted(self.concept_vocab.keys(), key=len, reverse=True)
        self.is_fitted = True
        return self

    def parse(self, claim_text: str, candidate_events: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Predicts structured predicate from natural language text.
        """
        if not self.is_fitted:
            raise RuntimeError("MLClaimBinder must be fitted before calling parse().")

        # Transform features
        x_vec = self.vectorizer.transform([claim_text])

        # Predict semantic labels & probabilities
        task_type = self.clf_task.predict(x_vec)[0]
        claim_type = self.clf_claim_type.predict(x_vec)[0]
        comparator_raw = self.clf_comparator.predict(x_vec)[0]
        comparator = None if comparator_raw == "NONE" else comparator_raw

        # Confidence calculation
        prob_task = np.max(self.clf_task.predict_proba(x_vec))
        prob_claim = np.max(self.clf_claim_type.predict_proba(x_vec))
        prob_comp = np.max(self.clf_comparator.predict_proba(x_vec))
        confidence = float(prob_task * prob_claim * prob_comp)

        # Slot filling
        temporal_window = "LAST_3" if task_type == "S1" else None
        text_lower = claim_text.lower().strip()
        concept_code = self._extract_concept(text_lower)

        claimed_value = None
        if task_type == "S4":
            matches = re.findall(r"[-+]?\d*\.?\d+", claim_text)
            if matches:
                try:
                    for m in reversed(matches):
                        claimed_value = float(m)
                        break
                except ValueError:
                    claimed_value = None

        event_A_id = None
        event_B_id = None
        if task_type == "S2" and candidate_events and len(candidate_events) >= 2:
            ev1, ev2 = candidate_events[0], candidate_events[1]
            name1 = (ev1.get("clinical_display") or "").split("[")[0].strip().lower()
            name2 = (ev2.get("clinical_display") or "").split("[")[0].strip().lower()

            pos1 = text_lower.find(name1) if name1 else -1
            pos2 = text_lower.find(name2) if name2 else -1

            if pos1 != -1 and pos2 != -1:
                if pos1 < pos2:
                    event_A_id = ev1.get("resource_id")
                    event_B_id = ev2.get("resource_id")
                else:
                    event_A_id = ev2.get("resource_id")
                    event_B_id = ev1.get("resource_id")
            else:
                event_A_id = ev1.get("resource_id")
                event_B_id = ev2.get("resource_id")

        return {
            "task_type": task_type,
            "clinical_concept": concept_code,
            "claim_type": claim_type,
            "temporal_window": temporal_window,
            "comparator": comparator,
            "claimed_value": claimed_value,
            "event_A_id": event_A_id,
            "event_B_id": event_B_id,
            "confidence": confidence
        }

    def _extract_concept(self, text_lower: str) -> Optional[str]:
        for clean_str in self._sorted_concepts:
            if clean_str in text_lower:
                return self.concept_vocab[clean_str]
        return None
