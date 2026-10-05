"""
Unit tests for OracleTemporalVerifier (B_ORACLE).
"""

import unittest
import os
import tempfile
import sqlite3
from src.verification.oracle_temporal_verifier import OracleTemporalVerifier

class TestOracleTemporalVerifier(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_oracle.sqlite")
        
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
        # S1 series: 4.0 -> 4.5 -> 5.0 (Increasing)
        cursor.execute("INSERT INTO timeline_events VALUES (1, 'p1', 'Observation', 'obs1', 'enc1', '2823-3', 'Potassium', '2023-01-01', '2023-01-01T00:00:00Z', 1000.0, 4.0, NULL, 'mmol/L', 'final', 'f.json', 0)")
        cursor.execute("INSERT INTO timeline_events VALUES (2, 'p1', 'Observation', 'obs2', 'enc1', '2823-3', 'Potassium', '2023-02-01', '2023-02-01T00:00:00Z', 2000.0, 4.5, NULL, 'mmol/L', 'final', 'f.json', 0)")
        cursor.execute("INSERT INTO timeline_events VALUES (3, 'p1', 'Observation', 'obs3', 'enc1', '2823-3', 'Potassium', '2023-03-01', '2023-03-01T00:00:00Z', 3000.0, 5.0, NULL, 'mmol/L', 'final', 'f.json', 0)")
        
        # S2 events: eA at 1000.0, eB at 2000.0
        cursor.execute("INSERT INTO timeline_events VALUES (4, 'p1', 'Encounter', 'enc1', 'enc1', 'ENC', 'Admission', '2023-01-01', '2023-01-01T00:00:00Z', 1000.0, NULL, NULL, NULL, 'finished', 'f.json', 0)")
        cursor.execute("INSERT INTO timeline_events VALUES (5, 'p1', 'Encounter', 'enc2', 'enc2', 'ENC', 'Discharge', '2023-02-01', '2023-02-01T00:00:00Z', 2000.0, NULL, NULL, NULL, 'finished', 'f.json', 0)")
        
        conn.commit()
        conn.close()

        self.verifier = OracleTemporalVerifier(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_s1_oracle_verification(self):
        # Claim INCREASING on increasing series -> PASS
        rec_sup = {
            "task_code": "S1",
            "patient_id": "p1",
            "structured_predicate": {"claimed_direction": "INCREASING"},
            "source_event_ids": ["obs1", "obs2", "obs3"]
        }
        dec_sup, _ = self.verifier.verify_claim_predicate(rec_sup)
        self.assertEqual(dec_sup, "PASS")

        # Claim DECREASING on increasing series -> BLOCK
        rec_con = {
            "task_code": "S1",
            "patient_id": "p1",
            "structured_predicate": {"claimed_direction": "DECREASING"},
            "source_event_ids": ["obs1", "obs2", "obs3"]
        }
        dec_con, _ = self.verifier.verify_claim_predicate(rec_con)
        self.assertEqual(dec_con, "BLOCK")

    def test_s2_oracle_verification(self):
        # Claim enc1 BEFORE enc2 -> PASS
        rec_sup = {
            "task_code": "S2",
            "patient_id": "p1",
            "structured_predicate": {"event_A_id": "enc1", "event_B_id": "enc2", "comparator": "LT"},
            "source_event_ids": ["enc1", "enc2"]
        }
        dec_sup, _ = self.verifier.verify_claim_predicate(rec_sup)
        self.assertEqual(dec_sup, "PASS")

        # Claim enc1 AFTER enc2 -> BLOCK
        rec_con = {
            "task_code": "S2",
            "patient_id": "p1",
            "structured_predicate": {"event_A_id": "enc1", "event_B_id": "enc2", "comparator": "GT"},
            "source_event_ids": ["enc1", "enc2"]
        }
        dec_con, _ = self.verifier.verify_claim_predicate(rec_con)
        self.assertEqual(dec_con, "BLOCK")

if __name__ == "__main__":
    unittest.main()
