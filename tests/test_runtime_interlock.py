"""
Integration and Safety Unit Tests for ContextBind Runtime Interlock.

Tests:
1. test_rule_pass_executes: Direct rule match verified -> exactly one execution.
2. test_rule_block_denies: Rule parsed contradictory claim -> 0 executions.
3. test_ai_fallback_pass_executes: Open-form claim parsed by AI and verified -> exactly one execution.
4. test_ai_fallback_block_denies: Open-form claim parsed by AI and contradicted -> 0 executions.
5. test_low_confidence_holds: Semantic claim with confidence < tau -> HOLD, 0 executions.
6. test_invalid_schema_holds: Malformed claim or missing patient -> HOLD, 0 executions.
7. test_verifier_error_holds: Database lookup or verifier exception -> HOLD, 0 executions.
8. test_no_guard_executes_same_call: Guard OFF executes contradictory claim directly.
9. test_guard_prevents_same_call: Guard ON prevents execution of identical contradictory claim.
10. test_single_execution_only: Guarded PASS executes tool exactly once without duplicate executions.
"""

import os
import sys
import unittest
import tempfile
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.runtime.contextbind_runtime import ContextBindRuntime
from src.runtime.guarded_executor import GuardedToolExecutor

class TestRuntimeInterlock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a temp directory for isolated test databases
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.audit_db = os.path.join(cls.temp_dir.name, "test_audit.sqlite")
        cls.timeline_db = "data/interim/contextbind_timeline.sqlite"
        cls.rule_art = "artifacts/frozen/rule_binder.json"
        cls.ai_art = "artifacts/frozen/semantic_ai_binder.pkl"
        
        # Test patient ID strictly from non-TEST development cohort
        cls.patient_id = "001cc5e4-71a3-8e4c-507c-d39178b49be8"
        
        # Initialize runtime & executor (Zero runtime training / frozen artifact load)
        cls.runtime = ContextBindRuntime(
            db_path=cls.timeline_db,
            rule_artifact_path=cls.rule_art,
            ai_artifact_path=cls.ai_art,
            audit_db_path=cls.audit_db,
            tau=0.70
        )
        cls.executor = GuardedToolExecutor(runtime=cls.runtime, audit_db_path=cls.audit_db)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_rule_pass_executes(self):
        """D1: Rule PASS verified against longitudinal timeline (48.55 < 92.87 mg/dL) -> exactly 1 execution."""
        req = {
            "patient_id": self.patient_id,
            "action_type": "CLINICAL_SUMMARY_DRAFT_COMMIT",
            "claim_text": "The latest Cholesterol in LDL reading is lower than the previous measurement.",
            "proposed_tool": "write_clinical_summary_draft",
            "tool_arguments": {"summary_text": "LDL reduction verified. Maintain therapy.", "department": "Cardiology"}
        }
        res = self.executor.execute_guarded_action(req, guard_enabled=True)
        
        self.assertTrue(res["executed"])
        self.assertEqual(res["decision"], "PASS")
        self.assertEqual(res["verification"]["route"], "RULE")
        self.assertIsNotNone(res["execution_response"])
        self.assertEqual(res["execution_response"]["status"], "SUCCESS")

    def test_rule_block_denies(self):
        """D2: Rule BLOCK -> 0 executions."""
        req = {
            "patient_id": self.patient_id,
            "action_type": "CLINICAL_SUMMARY_DRAFT_COMMIT",
            "claim_text": "The latest Cholesterol in LDL reading is higher than the previous measurement.",
            "proposed_tool": "write_clinical_summary_draft",
            "tool_arguments": {"summary_text": "LDL increasing.", "department": "Cardiology"}
        }
        res = self.executor.execute_guarded_action(req, guard_enabled=True)
        
        self.assertFalse(res["executed"])
        self.assertEqual(res["decision"], "BLOCK")
        self.assertEqual(res["verification"]["route"], "RULE")
        self.assertIsNone(res["execution_response"])

    def test_ai_fallback_pass_executes(self):
        """D3: AI Fallback PASS (conf >= 0.70, verified true: Calcium 9.82 > 8.84) -> exactly 1 execution."""
        req = {
            "patient_id": self.patient_id,
            "action_type": "CLINICAL_HANDOFF_COMMIT",
            "claim_text": "Diagnostic assessment shows that the most recently documented Calcium surpasses the prior encounter's result.",
            "proposed_tool": "commit_handoff_summary",
            "tool_arguments": {"handoff_text": "Calcium normalized elevation.", "target_unit": "Internal Medicine Outpatient"}
        }
        res = self.executor.execute_guarded_action(req, guard_enabled=True)
        
        self.assertTrue(res["executed"])
        self.assertEqual(res["decision"], "PASS")
        self.assertEqual(res["verification"]["route"], "AI_FALLBACK")
        self.assertGreaterEqual(res["verification"]["binder_confidence"], 0.70)
        self.assertIsNotNone(res["execution_response"])

    def test_ai_fallback_block_denies(self):
        """D4: AI Fallback BLOCK (conf >= 0.70, contradicted by timeline: Calcium 9.82 is NOT < 8.84) -> 0 executions."""
        req = {
            "patient_id": self.patient_id,
            "action_type": "CLINICAL_HANDOFF_COMMIT",
            "claim_text": "Diagnostic assessment shows that the most recently documented Calcium drops below the prior encounter's result.",
            "proposed_tool": "commit_handoff_summary",
            "tool_arguments": {"handoff_text": "Calcium decreased.", "target_unit": "Endocrinology Inpatient"}
        }
        res = self.executor.execute_guarded_action(req, guard_enabled=True)
        
        self.assertFalse(res["executed"])
        self.assertEqual(res["decision"], "BLOCK")
        self.assertEqual(res["verification"]["route"], "AI_FALLBACK")
        self.assertIsNone(res["execution_response"])

    def test_low_confidence_holds(self):
        """D5: Ambiguous wording where AI confidence < 0.70 -> HOLD, 0 executions."""
        req = {
            "patient_id": self.patient_id,
            "action_type": "CLINICAL_SUMMARY_DRAFT_COMMIT",
            "claim_text": "The patient's clinical chart reveals ambiguous fluctuating markers and variable general observations.",
            "proposed_tool": "write_clinical_summary_draft",
            "tool_arguments": {"summary_text": "Fluctuating observations.", "department": "Internal Medicine"}
        }
        res = self.executor.execute_guarded_action(req, guard_enabled=True)
        
        self.assertFalse(res["executed"])
        self.assertEqual(res["decision"], "HOLD")
        self.assertEqual(res["verification"]["route"], "HOLD")
        self.assertIsNone(res["execution_response"])

    def test_invalid_schema_holds(self):
        """Missing patient or empty claim -> fail-closed HOLD, 0 executions."""
        req = {
            "patient_id": "",
            "claim_text": "Some claim.",
            "proposed_tool": "write_clinical_summary_draft"
        }
        res = self.executor.execute_guarded_action(req, guard_enabled=True)
        self.assertFalse(res["executed"])
        self.assertEqual(res["decision"], "HOLD")
        self.assertIsNone(res["execution_response"])

        # Non-existent patient
        req2 = {
            "patient_id": "non_existent_patient_id_12345",
            "claim_text": "Patient has high calcium.",
            "proposed_tool": "write_clinical_summary_draft"
        }
        res2 = self.executor.execute_guarded_action(req2, guard_enabled=True)
        self.assertFalse(res2["executed"])
        self.assertEqual(res2["decision"], "HOLD")
        self.assertIsNone(res2["execution_response"])

    def test_verifier_error_holds(self):
        """Simulated internal verifier exception -> fail-closed HOLD, 0 executions."""
        req = {
            "patient_id": self.patient_id,
            "claim_text": "The latest Cholesterol in LDL reading is lower than the previous measurement.",
            "proposed_tool": "write_clinical_summary_draft"
        }
        with patch.object(self.runtime.verifier, 'verify_claim_predicate', side_effect=RuntimeError("Simulated DB Lock")):
            res = self.executor.execute_guarded_action(req, guard_enabled=True)
            self.assertFalse(res["executed"])
            self.assertEqual(res["decision"], "HOLD")
            self.assertIsNone(res["execution_response"])

    def test_no_guard_executes_same_call(self):
        """Guard OFF demo: Contradictory claim executes unchecked."""
        req = {
            "patient_id": self.patient_id,
            "action_type": "CLINICAL_SUMMARY_DRAFT_COMMIT",
            "claim_text": "Diagnostic assessment shows that the most recently documented Calcium drops below the prior encounter's result.",
            "proposed_tool": "write_clinical_summary_draft",
            "tool_arguments": {"summary_text": "Calcium dropped dangerously. Supplement ordered.", "department": "Internal Medicine"}
        }
        res = self.executor.execute_guarded_action(req, guard_enabled=False)
        self.assertTrue(res["executed"])
        self.assertEqual(res["decision"], "UNGUARDED_EXECUTION")
        self.assertIsNotNone(res["execution_response"])
        self.assertEqual(res["execution_response"]["status"], "SUCCESS")

    def test_guard_prevents_same_call(self):
        """Guard ON demo: Same contradictory claim intercepted and BLOCKED."""
        req = {
            "patient_id": self.patient_id,
            "action_type": "CLINICAL_SUMMARY_DRAFT_COMMIT",
            "claim_text": "Diagnostic assessment shows that the most recently documented Calcium drops below the prior encounter's result.",
            "proposed_tool": "write_clinical_summary_draft",
            "tool_arguments": {"summary_text": "Calcium dropped dangerously. Supplement ordered.", "department": "Internal Medicine"}
        }
        res = self.executor.execute_guarded_action(req, guard_enabled=True)
        self.assertFalse(res["executed"])
        self.assertEqual(res["decision"], "BLOCK")
        self.assertIsNone(res["execution_response"])

    def test_single_execution_only(self):
        """Prove that verified PASS executes the underlying tool exactly once."""
        mock_tool = MagicMock(return_value={"status": "SUCCESS", "operation": "mock_tool"})
        with patch.dict(self.executor.tool_registry, {"write_clinical_summary_draft": mock_tool}):
            req = {
                "patient_id": self.patient_id,
                "action_type": "CLINICAL_SUMMARY_DRAFT_COMMIT",
                "claim_text": "The latest Cholesterol in LDL reading is lower than the previous measurement.",
                "proposed_tool": "write_clinical_summary_draft",
                "tool_arguments": {"summary_text": "LDL decrease confirmed."}
            }
            res = self.executor.execute_guarded_action(req, guard_enabled=True)
            self.assertTrue(res["executed"])
            self.assertEqual(mock_tool.call_count, 1)

if __name__ == "__main__":
    unittest.main()
