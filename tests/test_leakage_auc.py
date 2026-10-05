"""
Unit tests for O(N log N) rank-based Mann-Whitney ROC-AUC and tie handling.
"""

import unittest
from src.leakage.metadata_sentinel import compute_roc_auc, compute_balanced_accuracy, bootstrap_ci_auc

class TestRankBasedAUC(unittest.TestCase):
    def test_perfect_separation(self):
        y_true = [1, 1, 0, 0]
        scores = [0.9, 0.8, 0.3, 0.1]
        auc = compute_roc_auc(y_true, scores)
        self.assertEqual(auc, 1.0)

    def test_reversed_separation(self):
        y_true = [1, 1, 0, 0]
        scores = [0.1, 0.2, 0.8, 0.9]
        auc = compute_roc_auc(y_true, scores)
        self.assertEqual(auc, 0.0)

    def test_identical_scores(self):
        y_true = [1, 1, 0, 0]
        scores = [0.5, 0.5, 0.5, 0.5]
        auc = compute_roc_auc(y_true, scores)
        self.assertEqual(auc, 0.5)

    def test_tied_scores_hand_calculated(self):
        # pos: [0.8, 0.4], neg: [0.8, 0.2]
        # pos(0.8) vs neg(0.8): tie (0.5)
        # pos(0.8) vs neg(0.2): win (1.0)
        # pos(0.4) vs neg(0.8): loss (0.0)
        # pos(0.4) vs neg(0.2): win (1.0)
        # Expected AUC = (0.5 + 1.0 + 0.0 + 1.0) / 4 = 2.5 / 4 = 0.625
        y_true = [1, 0, 1, 0]
        scores = [0.8, 0.8, 0.4, 0.2]
        auc = compute_roc_auc(y_true, scores)
        self.assertAlmostEqual(auc, 0.625, places=5)

    def test_balanced_accuracy(self):
        y_true = [1, 1, 0, 0]
        preds = [1, 0, 0, 0] # TPR=0.5, TNR=1.0 -> BalAcc=0.75
        bal_acc = compute_balanced_accuracy(y_true, preds)
        self.assertEqual(bal_acc, 0.75)

    def test_bootstrap_ci_deterministic(self):
        y_true = [1, 1, 0, 0]
        scores = [0.9, 0.8, 0.2, 0.1]
        base, low, high = bootstrap_ci_auc(y_true, scores, n_bootstraps=100, seed=20261004)
        self.assertEqual(base, 1.0)
        self.assertGreaterEqual(low, 0.0)
        self.assertLessEqual(high, 1.0)

if __name__ == "__main__":
    unittest.main()
