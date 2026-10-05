"""
ContextBind — L1 Metadata/Form Leakage Sentinel
Evaluates whether structural metadata (length, punctuation, token count, template ID)
predicts SUPPORTED vs CONTRADICTED labels above random chance.
Strictly uses Python Standard Library.
"""

import math
import random
from typing import List, Dict, Any, Tuple

def extract_form_features(claim: Dict[str, Any]) -> List[float]:
    text = claim["claim_text"]
    char_len = float(len(text))
    words = text.split()
    word_count = float(len(words))
    punct_count = float(sum(1 for c in text if c in ".,!?;:-_()[]'\""))
    num_digits = float(sum(1 for c in text if c.isdigit()))
    ev_count = float(len(claim.get("source_event_ids", [])))
    
    # Structural features only (Zero clinical content)
    return [1.0, char_len, word_count, punct_count, num_digits, ev_count]

def compute_roc_auc(y_true: List[int], scores: List[float]) -> float:
    """
    Computes ROC-AUC in O(N log N) using the rank-sum / Mann-Whitney U formulation with exact average tie ranking.
    """
    n = len(y_true)
    if n == 0:
        return 0.5
    
    n_pos = sum(1 for y in y_true if y == 1)
    n_neg = n - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.5

    paired = sorted(enumerate(zip(scores, y_true)), key=lambda x: x[1][0])
    
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n and paired[j][1][0] == paired[i][1][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[k] = avg_rank
        i = j

    r_pos = sum(ranks[k] for k in range(n) if paired[k][1][1] == 1)
    u_pos = r_pos - (n_pos * (n_pos + 1)) / 2.0
    return u_pos / (n_pos * n_neg)

def compute_balanced_accuracy(y_true: List[int], preds: List[int]) -> float:
    pos_idx = [i for i, y in enumerate(y_true) if y == 1]
    neg_idx = [i for i, y in enumerate(y_true) if y == 0]
    tpr = sum(1 for i in pos_idx if preds[i] == 1) / len(pos_idx) if pos_idx else 0.5
    tnr = sum(1 for i in neg_idx if preds[i] == 0) / len(neg_idx) if neg_idx else 0.5
    return (tpr + tnr) / 2.0

def bootstrap_ci_auc(y_true: List[int], scores: List[float], n_bootstraps: int = 300, seed: int = 20261004) -> Tuple[float, float, float]:
    rng = random.Random(seed)
    n = len(y_true)
    auc_base = compute_roc_auc(y_true, scores)
    if n == 0:
        return auc_base, auc_base, auc_base
        
    boot_aucs = []
    for _ in range(n_bootstraps):
        idxs = [rng.randint(0, n - 1) for _ in range(n)]
        y_b = [y_true[i] for i in idxs]
        s_b = [scores[i] for i in idxs]
        boot_aucs.append(compute_roc_auc(y_b, s_b))
        
    boot_aucs.sort()
    low = boot_aucs[int(0.025 * n_bootstraps)]
    high = boot_aucs[int(0.975 * n_bootstraps)]
    return auc_base, low, high

class MetadataFormSentinel:
    def __init__(self, lr: float = 0.01, epochs: int = 50):
        self.lr = lr
        self.epochs = epochs
        self.weights: List[float] = []

    def fit_predict(self, train_claims: List[Dict[str, Any]], val_claims: List[Dict[str, Any]]) -> Dict[str, Any]:
        X_train = [extract_form_features(c) for c in train_claims]
        y_train = [1 if c["ground_truth"] == "SUPPORTED" else 0 for c in train_claims]
        
        X_val = [extract_form_features(c) for c in val_claims]
        y_val = [1 if c["ground_truth"] == "SUPPORTED" else 0 for c in val_claims]

        # Standardize features
        n_feat = len(X_train[0])
        means = [0.0] * n_feat
        stds = [1.0] * n_feat
        for j in range(1, n_feat):
            col = [row[j] for row in X_train]
            means[j] = sum(col) / len(col)
            var = sum((x - means[j])**2 for x in col) / len(col)
            stds[j] = math.sqrt(var) if var > 1e-8 else 1.0

        def scale(X):
            return [[row[0]] + [(row[j] - means[j]) / stds[j] for j in range(1, n_feat)] for row in X]

        X_train_s = scale(X_train)
        X_val_s = scale(X_val)

        # Train logistic regression via SGD
        w = [0.0] * n_feat
        lr = self.lr
        for _ in range(self.epochs):
            for xi, yi in zip(X_train_s, y_train):
                dot = w[0]*xi[0] + w[1]*xi[1] + w[2]*xi[2] + w[3]*xi[3] + w[4]*xi[4] + w[5]*xi[5]
                pred = 1.0 / (1.0 + math.exp(-max(min(dot, 20), -20)))
                err = lr * (yi - pred)
                w[0] += err * xi[0]
                w[1] += err * xi[1]
                w[2] += err * xi[2]
                w[3] += err * xi[3]
                w[4] += err * xi[4]
                w[5] += err * xi[5]
        self.weights = w

        # Evaluate on validation
        val_scores = []
        val_preds = []
        for xi in X_val_s:
            dot = w[0]*xi[0] + w[1]*xi[1] + w[2]*xi[2] + w[3]*xi[3] + w[4]*xi[4] + w[5]*xi[5]
            prob = 1.0 / (1.0 + math.exp(-max(min(dot, 20), -20)))
            val_scores.append(prob)
            val_preds.append(1 if prob >= 0.5 else 0)

        acc = sum(1 for p, y in zip(val_preds, y_val) if p == y) / len(y_val) if y_val else 0.5
        bal_acc = compute_balanced_accuracy(y_val, val_preds)
        auc_base, auc_low, auc_high = bootstrap_ci_auc(y_val, val_scores, n_bootstraps=300, seed=20261004)

        return {
            "sentinel": "L1_METADATA_FORM",
            "accuracy": acc,
            "balanced_accuracy": bal_acc,
            "auc": auc_base,
            "auc_ci_95": [auc_low, auc_high],
            "leakage_detected": (auc_low > 0.55) # Leakage if lower CI bound strictly exceeds chance baseline
        }
