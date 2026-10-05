"""
Unit tests for RuleBasedClaimBinder (B_RULE).
"""

import unittest
from src.binder.rule_binder import RuleBasedClaimBinder

class TestRuleBasedClaimBinder(unittest.TestCase):
    def setUp(self):
        train_mock = [
            {"task_code": "S1", "clinical_code": "9843-4", "clinical_display": "Head Occipital-frontal circumference", "claim_text": "The Head Occipital-frontal circumference level has increased across the last 3 measurements."},
            {"task_code": "S2", "clinical_code": "834061_vs_410620009", "clinical_display": "Penicillin V Potassium 250 MG Oral Tablet vs Well child visit (procedure)", "claim_text": "Penicillin V Potassium 250 MG Oral Tablet was recorded before Well child visit (procedure)."},
            {"task_code": "S3", "clinical_code": "2947-0", "clinical_display": "Sodium", "claim_text": "The latest Sodium reading is lower than the previous measurement."},
            {"task_code": "S4", "clinical_code": "72514-3", "clinical_display": "Pain severity - 0-10 verbal numeric rating", "claim_text": "The patient's current Pain severity - 0-10 verbal numeric rating is 4.0."}
        ]
        self.binder = RuleBasedClaimBinder()
        self.binder.fit(train_mock)

    def test_s1_parse(self):
        text = "The Head Occipital-frontal circumference level has increased across the last 3 measurements."
        pred = self.binder.parse(text)
        self.assertEqual(pred["task_type"], "S1")
        self.assertEqual(pred["claim_type"], "TREND_INCREASING")
        self.assertEqual(pred["comparator"], "GT")
        self.assertEqual(pred["temporal_window"], "LAST_3")
        self.assertEqual(pred["clinical_concept"], "9843-4")

    def test_s2_parse(self):
        text = "Penicillin V Potassium 250 MG Oral Tablet occurred prior to Well child visit (procedure)."
        candidates = [
            {"resource_id": "ev1", "clinical_display": "Penicillin V Potassium 250 MG Oral Tablet"},
            {"resource_id": "ev2", "clinical_display": "Well child visit (procedure)"}
        ]
        pred = self.binder.parse(text, candidates)
        self.assertEqual(pred["task_type"], "S2")
        self.assertEqual(pred["claim_type"], "BEFORE")
        self.assertEqual(pred["comparator"], "LT")
        self.assertEqual(pred["event_A_id"], "ev1")
        self.assertEqual(pred["event_B_id"], "ev2")

    def test_s3_parse(self):
        text = "The latest Sodium reading is lower than the previous measurement."
        pred = self.binder.parse(text)
        self.assertEqual(pred["task_type"], "S3")
        self.assertEqual(pred["claim_type"], "LOWER_THAN_PREVIOUS")
        self.assertEqual(pred["comparator"], "LT")
        self.assertEqual(pred["clinical_concept"], "2947-0")

    def test_s4_parse(self):
        text = "Latest recorded Pain severity - 0-10 verbal numeric rating stands at 4.5."
        pred = self.binder.parse(text)
        self.assertEqual(pred["task_type"], "S4")
        self.assertEqual(pred["claim_type"], "CURRENT_VALUE")
        self.assertEqual(pred["clinical_concept"], "72514-3")
        self.assertEqual(pred["claimed_value"], 4.5)

if __name__ == "__main__":
    unittest.main()
