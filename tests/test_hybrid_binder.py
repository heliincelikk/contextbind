"""
Unit tests for HybridClaimBinder and MLClaimBinder.
"""

import unittest
from src.binder.hybrid_binder import HybridClaimBinder
from src.binder.ml_binder import MLClaimBinder

class TestHybridClaimBinder(unittest.TestCase):
    def setUp(self):
        train_mock = [
            {
                "task_code": "S1",
                "clinical_code": "9843-4",
                "clinical_display": "Head Occipital-frontal circumference",
                "claim_text": "The Head Occipital-frontal circumference level has increased across the last 3 measurements.",
                "structured_predicate": {"claim_type": "TREND_INCREASING", "comparator": "GT"}
            },
            {
                "task_code": "S1",
                "clinical_code": "9843-4",
                "clinical_display": "Head Occipital-frontal circumference",
                "claim_text": "The Head Occipital-frontal circumference level has decreased across the last 3 measurements.",
                "structured_predicate": {"claim_type": "TREND_DECREASING", "comparator": "LT"}
            },
            {
                "task_code": "S2",
                "clinical_code": "834061_vs_410620009",
                "clinical_display": "Penicillin V Potassium 250 MG Oral Tablet vs Well child visit (procedure)",
                "claim_text": "Penicillin V Potassium 250 MG Oral Tablet was recorded before Well child visit (procedure).",
                "structured_predicate": {"claim_type": "BEFORE", "comparator": "LT"}
            },
            {
                "task_code": "S2",
                "clinical_code": "834061_vs_410620009",
                "clinical_display": "Penicillin V Potassium 250 MG Oral Tablet vs Well child visit (procedure)",
                "claim_text": "Penicillin V Potassium 250 MG Oral Tablet occurred following Well child visit (procedure).",
                "structured_predicate": {"claim_type": "AFTER", "comparator": "GT"}
            },
            {
                "task_code": "S3",
                "clinical_code": "2947-0",
                "clinical_display": "Sodium",
                "claim_text": "The latest Sodium reading is lower than the previous measurement.",
                "structured_predicate": {"claim_type": "LOWER_THAN_PREVIOUS", "comparator": "LT"}
            },
            {
                "task_code": "S3",
                "clinical_code": "2947-0",
                "clinical_display": "Sodium",
                "claim_text": "The latest Sodium reading is higher than the previous measurement.",
                "structured_predicate": {"claim_type": "HIGHER_THAN_PREVIOUS", "comparator": "GT"}
            },
            {
                "task_code": "S4",
                "clinical_code": "72514-3",
                "clinical_display": "Pain severity - 0-10 verbal numeric rating",
                "claim_text": "The patient's current Pain severity - 0-10 verbal numeric rating is 4.0.",
                "structured_predicate": {"claim_type": "CURRENT_VALUE", "comparator": None}
            }
        ]
        self.hybrid = HybridClaimBinder(seed=42)
        self.hybrid.fit(train_mock)

    def test_hybrid_parsing(self):
        text = "The latest Sodium reading is higher than the previous measurement."
        pred = self.hybrid.parse(text)
        self.assertEqual(pred["task_type"], "S3")
        self.assertEqual(pred["claim_type"], "HIGHER_THAN_PREVIOUS")
        self.assertEqual(pred["comparator"], "GT")
        self.assertEqual(pred["clinical_concept"], "2947-0")
        self.assertGreater(pred["confidence"], 0.0)

if __name__ == "__main__":
    unittest.main()
