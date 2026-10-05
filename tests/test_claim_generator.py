"""
Unit tests for TemporalClaimGenerator and counterfactual pairing.
"""

import unittest
import os
import tempfile
import sqlite3
import json
from src.claims.claim_generator import TemporalClaimGenerator

class TestTemporalClaimGenerator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.sqlite")
        self.split_path = os.path.join(self.temp_dir.name, "split.json")
        
        # Mock split
        split_content = {
            "train_patient_ids": ["p1"],
            "val_patient_ids": ["p2"],
            "test_patient_ids": ["p3"]
        }
        with open(self.split_path, "w", encoding="utf-8") as f:
            json.dump(split_content, f)

        # Mock DB
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE timeline_events (
            event_id INTEGER PRIMARY KEY,
            patient_id TEXT,
            resource_type TEXT,
            resource_id TEXT,
            encounter_id TEXT,
            clinical_code TEXT,
            clinical_display TEXT,
            event_time_raw TEXT,
            event_time_norm TEXT,
            event_time_epoch REAL,
            value_numeric REAL,
            value_text TEXT,
            unit TEXT,
            status TEXT,
            source_file TEXT,
            is_post_death_event INTEGER
        )
        """)
        # Insert 3 increasing observations for p1
        cursor.execute("INSERT INTO timeline_events VALUES (1, 'p1', 'Observation', 'obs1', 'enc1', '2823-3', 'Potassium', '2023-01-01', '2023-01-01T00:00:00Z', 1000.0, 4.0, NULL, 'mmol/L', 'final', 'f.json', 0)")
        cursor.execute("INSERT INTO timeline_events VALUES (2, 'p1', 'Observation', 'obs2', 'enc1', '2823-3', 'Potassium', '2023-02-01', '2023-02-01T00:00:00Z', 2000.0, 4.5, NULL, 'mmol/L', 'final', 'f.json', 0)")
        cursor.execute("INSERT INTO timeline_events VALUES (3, 'p1', 'Observation', 'obs3', 'enc1', '2823-3', 'Potassium', '2023-03-01', '2023-03-01T00:00:00Z', 3000.0, 5.0, NULL, 'mmol/L', 'final', 'f.json', 0)")
        conn.commit()
        conn.close()

        self.generator = TemporalClaimGenerator(self.db_path, self.split_path, seed=42)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_s1_counterfactual_pairing(self):
        claims = self.generator.generate_s1_trend_claims({"p1"})
        self.assertEqual(len(claims), 2)
        
        labels = [c["ground_truth"] for c in claims]
        self.assertIn("SUPPORTED", labels)
        self.assertIn("CONTRADICTED", labels)

        sup_c = [c for c in claims if c["ground_truth"] == "SUPPORTED"][0]
        con_c = [c for c in claims if c["ground_truth"] == "CONTRADICTED"][0]

    def test_grammar_invariance(self):
        # Test increasing and decreasing trends across multiple calls
        claims = self.generator.generate_s1_trend_claims({"p1"})
        for c in claims:
            text = c["claim_text"]
            self.assertNotIn("an decreasing", text.lower(), f"Grammar violation in text: {text}")
            self.assertNotIn("a increasing", text.lower(), f"Grammar violation in text: {text}")
            self.assertNotIn("an stable", text.lower(), f"Grammar violation in text: {text}")

if __name__ == "__main__":
    unittest.main()
