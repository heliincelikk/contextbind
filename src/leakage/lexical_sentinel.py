"""
ContextBind — L2 Bag-of-Words Lexical Leakage Sentinel
Evaluates whether claim text word distributions alone predict SUPPORTED vs CONTRADICTED labels.
Strictly uses Python Standard Library.
"""

import math
import re
import random
from collections import Counter
from typing import List, Dict, Any, Tuple
from src.leakage.metadata_sentinel import compute_roc_auc, compute_balanced_accuracy, bootstrap_ci_auc

def tokenize(text: str) -> List[str]:
    clean = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
    return [w for w in clean.split() if w]

class LexicalBagOfWordsSentinel:
    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self.vocab = {}
        self.log_prior_pos = 0.0
        self.log_prior_neg = 0.0
        self.log_prob_pos = {}
        self.log_prob_neg = {}

    def fit_predict(self, train_claims: List[Dict[str, Any]], val_claims: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Build vocabulary from training set
        word_counts = Counter()
        pos_word_counts = Counter()
        neg_word_counts = Counter()
        n_pos = 0
        n_neg = 0

        for c in train_claims:
            is_pos = (c["ground_truth"] == "SUPPORTED")
            tokens = tokenize(c["claim_text"])
            if is_pos:
                n_pos += 1
                pos_word_counts.update(tokens)
            else:
                n_neg += 1
                neg_word_counts.update(tokens)
            word_counts.update(tokens)

        # Retain frequent tokens
        self.vocab = {w for w, cnt in word_counts.items() if cnt >= 2}
        total_vocab = len(self.vocab)

        total_pos_words = sum(pos_word_counts[w] for w in self.vocab)
        total_neg_words = sum(neg_word_counts[w] for w in self.vocab)

        self.log_prior_pos = math.log((n_pos + 1.0) / (n_pos + n_neg + 2.0))
        self.log_prior_neg = math.log((n_neg + 1.0) / (n_pos + n_neg + 2.0))

        self.log_prob_pos = {
            w: math.log((pos_word_counts[w] + self.alpha) / (total_pos_words + self.alpha * total_vocab))
            for w in self.vocab
        }
        self.log_prob_neg = {
            w: math.log((neg_word_counts[w] + self.alpha) / (total_neg_words + self.alpha * total_vocab))
            for w in self.vocab
        }

        # Evaluate on Validation
        y_val = [1 if c["ground_truth"] == "SUPPORTED" else 0 for c in val_claims]
        val_scores = []
        val_preds = []

        for c in val_claims:
            tokens = [w for w in tokenize(c["claim_text"]) if w in self.vocab]
            log_p_pos = self.log_prior_pos + sum(self.log_prob_pos[w] for w in tokens)
            log_p_neg = self.log_prior_neg + sum(self.log_prob_neg[w] for w in tokens)

            # Convert to posterior prob via softmax
            max_log = max(log_p_pos, log_p_neg)
            p_pos = math.exp(log_p_pos - max_log)
            p_neg = math.exp(log_p_neg - max_log)
            prob = p_pos / (p_pos + p_neg)

            val_scores.append(prob)
            val_preds.append(1 if prob >= 0.5 else 0)

        acc = sum(1 for p, y in zip(val_preds, y_val) if p == y) / len(y_val) if y_val else 0.5
        bal_acc = compute_balanced_accuracy(y_val, val_preds)
        auc_base, auc_low, auc_high = bootstrap_ci_auc(y_val, val_scores, n_bootstraps=300, seed=20261004)

        return {
            "sentinel": "L2_LEXICAL_BAG_OF_WORDS",
            "vocab_size": total_vocab,
            "accuracy": acc,
            "balanced_accuracy": bal_acc,
            "auc": auc_base,
            "auc_ci_95": [auc_low, auc_high],
            "leakage_detected": (auc_low > 0.55) # Leakage if lower CI bound strictly exceeds chance baseline
        }
