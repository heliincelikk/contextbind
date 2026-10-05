"""
ContextBind — B3 Direct Text Classification Baseline (Shortcut Control)
Directly predicts SUPPORTED vs CONTRADICTED from claim text without predicate grounding.
Used strictly as a diagnostic control for measuring lexical shortcut exploitation.
"""

from typing import Dict, Any, List
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion

class DirectTextClassifier:
    def __init__(self, c_reg: float = 1.0, seed: int = 20261004):
        self.vectorizer = FeatureUnion([
            ("word_tfidf", TfidfVectorizer(ngram_range=(1, 2), analyzer="word", lowercase=True, max_features=5000)),
            ("char_tfidf", TfidfVectorizer(ngram_range=(3, 5), analyzer="char", lowercase=True, max_features=5000))
        ])
        self.clf = LogisticRegression(C=c_reg, max_iter=250, random_state=seed)
        self.is_fitted = False

    def fit(self, train_claims: List[Dict[str, Any]]) -> "DirectTextClassifier":
        texts = [c["claim_text"] for c in train_claims]
        y = [1 if c["ground_truth"] == "SUPPORTED" else 0 for c in train_claims]

        X = self.vectorizer.fit_transform(texts)
        self.clf.fit(X, y)
        self.is_fitted = True
        return self

    def predict(self, val_claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self.is_fitted:
            raise RuntimeError("DirectTextClassifier must be fitted before predict().")

        texts = [c["claim_text"] for c in val_claims]
        X = self.vectorizer.transform(texts)
        preds = self.clf.predict(X)
        probs = self.clf.predict_proba(X)[:, 1]

        results = []
        for p, prob in zip(preds, probs):
            verdict = "PASS" if p == 1 else "BLOCK"
            results.append({"verdict": verdict, "prob_supported": float(prob)})
        return results
