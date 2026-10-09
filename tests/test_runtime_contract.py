"""
ContextBind — S1-S4 Runtime Contract & Verification Unit Tests
Built strictly from frozen task specifications to verify runtime contract invariants.
"""

import os
import sys
import unittest
import sqlite3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.verification.oracle_temporal_verifier import OracleTemporalVerifier
from src.runtime.contextbind_runtime import ContextBindRuntime

class TestRuntimeContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = "data/interim/contextbind_timeline.sqlite"
        cls.verifier = OracleTemporalVerifier(cls.db_path)
        cls.runtime = ContextBindRuntime(db_path=cls.db_path)

        # Find sample patient data for unit testing from non-test pool
        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get observation patient with >= 3 readings
        cursor.execute("""
        SELECT patient_id, clinical_code, clinical_display
        FROM timeline_events
        WHERE resource_type = 'Observation' AND value_numeric IS NOT NULL AND is_post_death_event = 0
        GROUP BY patient_id, clinical_code
        HAVING COUNT(*) >= 3
        LIMIT 1
        """)
        r_obs = cursor.fetchone()
        cls.obs_patient = r_obs["patient_id"]
        cls.obs_code = r_obs["clinical_code"]

        cursor.execute("""
        SELECT resource_id, value_numeric, event_time_epoch
        FROM timeline_events
        WHERE patient_id = ? AND clinical_code = ? AND resource_type = 'Observation' AND value_numeric IS NOT NULL AND is_post_death_event = 0
        ORDER BY event_time_epoch ASC
        LIMIT 3
        """, (cls.obs_patient, cls.obs_code))
        cls.obs_rows = cursor.fetchall()
        cls.s1_event_ids = [r["resource_id"] for r in cls.obs_rows]

        # Get S2 patient with >= 2 distinct events
        cursor.execute("""
        SELECT patient_id
        FROM timeline_events
        WHERE is_post_death_event = 0
        GROUP BY patient_id
        HAVING COUNT(DISTINCT resource_id) >= 2
        LIMIT 1
        """)
        cls.s2_patient = cursor.fetchone()["patient_id"]
        cursor.execute("""
        SELECT resource_id, event_time_epoch
        FROM timeline_events
        WHERE patient_id = ? AND is_post_death_event = 0
        ORDER BY event_time_epoch ASC
        LIMIT 2
        """, (cls.s2_patient,))
        s2_rows = cursor.fetchall()
        cls.s2_event_A = s2_rows[0]["resource_id"]
        cls.s2_event_B = s2_rows[1]["resource_id"]

        conn.close()

    def test_s1_canonical_predicate_verifier_decides(self):
        """S1 valid structured predicate -> verifier decides (PASS or BLOCK)."""
        adapted_pred = ContextBindRuntime.adapt_predicate_for_verifier({
            "clinical_concept": self.obs_code,
            "claim_type": "TREND_INCREASING",
            "comparator": "GT",
            "temporal_window": "LAST_3"
        }, "S1")
        claim_rec = {
            "task_code": "S1",
            "patient_id": self.obs_patient,
            "claim_text": "Observation has increased over last 3 measurements.",
            "structured_predicate": adapted_pred,
            "source_event_ids": self.s1_event_ids
        }
        verdict, exp = self.verifier.verify_claim_predicate(claim_rec)
        self.assertIn(verdict, ["PASS", "BLOCK"], f"S1 verifier returned {verdict}: {exp}")

    def test_s2_canonical_predicate_verifier_decides(self):
        """S2 valid structured predicate -> verifier decides (PASS or BLOCK)."""
        adapted_pred = ContextBindRuntime.adapt_predicate_for_verifier({
            "claim_type": "BEFORE",
            "comparator": "LT",
            "event_A_id": self.s2_event_A,
            "event_B_id": self.s2_event_B
        }, "S2")
        claim_rec = {
            "task_code": "S2",
            "patient_id": self.s2_patient,
            "claim_text": "Event A occurred before Event B.",
            "structured_predicate": adapted_pred,
            "source_event_ids": [self.s2_event_A, self.s2_event_B]
        }
        verdict, exp = self.verifier.verify_claim_predicate(claim_rec)
        self.assertIn(verdict, ["PASS", "BLOCK"], f"S2 verifier returned {verdict}: {exp}")

    def test_s3_canonical_predicate_verifier_decides(self):
        """S3 valid structured predicate -> verifier decides (PASS or BLOCK)."""
        adapted_pred = ContextBindRuntime.adapt_predicate_for_verifier({
            "clinical_concept": self.obs_code,
            "claim_type": "HIGHER_THAN_PREVIOUS",
            "comparator": "GT"
        }, "S3")
        claim_rec = {
            "task_code": "S3",
            "patient_id": self.obs_patient,
            "claim_text": "Latest reading exceeds previous.",
            "structured_predicate": adapted_pred,
            "source_event_ids": self.s1_event_ids[:2]
        }
        verdict, exp = self.verifier.verify_claim_predicate(claim_rec)
        self.assertIn(verdict, ["PASS", "BLOCK"], f"S3 verifier returned {verdict}: {exp}")

    def test_s4_canonical_predicate_verifier_decides(self):
        """S4 valid structured predicate -> verifier decides (PASS or BLOCK)."""
        val = self.obs_rows[-1]["value_numeric"]
        adapted_pred = ContextBindRuntime.adapt_predicate_for_verifier({
            "clinical_concept": self.obs_code,
            "claim_type": "CURRENT_VALUE",
            "claimed_value": val
        }, "S4")
        claim_rec = {
            "task_code": "S4",
            "patient_id": self.obs_patient,
            "claim_text": f"Current reading is {val}.",
            "structured_predicate": adapted_pred,
            "source_event_ids": []
        }
        verdict, exp = self.verifier.verify_claim_predicate(claim_rec)
        self.assertIn(verdict, ["PASS", "BLOCK"], f"S4 verifier returned {verdict}: {exp}")

    def test_incomplete_predicate_holds_before_verifier(self):
        """Incomplete predicate -> RULE_HOLD / AI_HOLD before reaching verifier."""
        # Missing clinical_concept in S1
        p_invalid_s1 = {"task_type": "S1", "claim_type": "TREND_INCREASING"}
        self.assertFalse(self.runtime._is_rule_predicate_valid(p_invalid_s1))

        # Missing event IDs in S2
        p_invalid_s2 = {"task_type": "S2", "claim_type": "BEFORE", "event_A_id": None}
        self.assertFalse(self.runtime._is_rule_predicate_valid(p_invalid_s2))

        # Missing claimed_value in S4
        p_invalid_s4 = {"task_type": "S4", "claim_type": "CURRENT_VALUE", "clinical_concept": self.obs_code, "claimed_value": None}
        self.assertFalse(self.runtime._is_rule_predicate_valid(p_invalid_s4))

    def test_invalid_resource_reference_holds(self):
        """Invalid resource reference -> HOLD."""
        adapted_pred = ContextBindRuntime.adapt_predicate_for_verifier({
            "claim_type": "BEFORE",
            "comparator": "LT",
            "event_A_id": "non_existent_event_A",
            "event_B_id": "non_existent_event_B"
        }, "S2")
        claim_rec = {
            "task_code": "S2",
            "patient_id": self.s2_patient,
            "claim_text": "Non-existent events.",
            "structured_predicate": adapted_pred,
            "source_event_ids": ["non_existent_event_A", "non_existent_event_B"]
        }
        verdict, exp = self.verifier.verify_claim_predicate(claim_rec)
        self.assertEqual(verdict, "HOLD")

if __name__ == "__main__":
    unittest.main()
