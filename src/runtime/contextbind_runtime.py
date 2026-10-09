"""
ContextBind — Pre-Action Runtime Safety Interlock Engine
Core Runtime Engine enforcing:
1. Frozen Rule Fast-Path (B_RULE)
2. Frozen Confidence-Gated Semantic AI Fallback (DistilBERT, tau=0.70)
3. Deterministic Symbolic FHIR Timeline Verifier (OracleTemporalVerifier)
4. Strict Fail-Closed Policy (Any ambiguity/error -> HOLD)
"""

import os
import sys
import json
import sqlite3
import datetime
from typing import Dict, Any, List, Optional, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.binder.rule_binder import RuleBasedClaimBinder
from src.binder.semantic_ai_binder import SemanticAIBinder
from src.verification.oracle_temporal_verifier import OracleTemporalVerifier
from src.runtime.audit_logger import RuntimeAuditLogger

class ContextBindRuntime:
    def __init__(
        self,
        db_path: str = "data/interim/contextbind_timeline.sqlite",
        rule_artifact_path: str = "artifacts/frozen/rule_binder.json",
        ai_artifact_path: str = "artifacts/frozen/semantic_ai_binder.pkl",
        audit_db_path: str = "data/interim/runtime_audit_log.sqlite",
        tau: float = 0.70
    ):
        self.db_path = db_path
        self.tau = tau

        # Initialize Audit Logger
        self.audit_logger = RuntimeAuditLogger(audit_db_path)

        # Load Frozen Binders from serialized artifacts (ZERO runtime training / ZERO training data read)
        if os.path.exists(rule_artifact_path):
            self.rule_binder = RuleBasedClaimBinder.load(rule_artifact_path)
        else:
            self.rule_binder = RuleBasedClaimBinder()

        if os.path.exists(ai_artifact_path):
            self.ai_binder = SemanticAIBinder.load(ai_artifact_path)
        else:
            self.ai_binder = SemanticAIBinder(confidence_threshold=tau)

        # Warm DistilBERT transformer encoder in memory
        self.ai_binder._init_transformer()

        self.verifier = OracleTemporalVerifier(db_path)

        # Cache timeline event displays
        self.event_display_map = {}
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT resource_id, clinical_display FROM timeline_events WHERE is_post_death_event = 0")
            for r in cursor.fetchall():
                if r[0] and r[1]:
                    self.event_display_map[r[0]] = r[1]
            conn.close()

    def _is_rule_predicate_valid(self, p: Dict[str, Any]) -> bool:
        if not p:
            return False
        t_type = p.get("task_type")
        c_type = p.get("claim_type")
        concept = p.get("clinical_concept")
        eA = p.get("event_A_id")
        eB = p.get("event_B_id")

        if t_type not in ["S1", "S2", "S3", "S4"] or c_type in [None, "UNKNOWN"]:
            return False
        if t_type in ["S1", "S3", "S4"]:
            if concept is None:
                return False
            if t_type == "S4" and p.get("claimed_value") is None:
                return False
            return True
        elif t_type == "S2":
            return bool(eA and eB and eA != eB)
        return False

    def _is_ai_predicate_valid(self, p: Dict[str, Any]) -> bool:
        return self._is_rule_predicate_valid(p)

    def _fetch_evidence_records(self, patient_id: str, task_code: str, pred: Dict[str, Any], candidate_ev_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Extracts readable longitudinal evidence records from FHIR SQLite timeline."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        evidence = []

        try:
            concept = pred.get("clinical_concept")
            if task_code in ["S1", "S3", "S4"] and concept:
                cursor.execute("""
                SELECT resource_id, clinical_code, clinical_display, value_numeric, unit, event_time_norm, event_time_epoch
                FROM timeline_events
                WHERE patient_id = ? AND clinical_code = ? AND resource_type = 'Observation' AND is_post_death_event = 0
                ORDER BY event_time_epoch ASC
                """, (patient_id, concept))
                rows = cursor.fetchall()
                for r in rows:
                    evidence.append({
                        "resource_id": r["resource_id"],
                        "code": r["clinical_code"],
                        "display": r["clinical_display"],
                        "value": r["value_numeric"],
                        "unit": r["unit"],
                        "timestamp": r["event_time_norm"]
                    })
            elif task_code == "S2":
                eA_id = pred.get("event_A_id")
                eB_id = pred.get("event_B_id")
                target_ids = [eid for eid in [eA_id, eB_id] if eid]
                if target_ids:
                    q_marks = ",".join(["?"] * len(target_ids))
                    cursor.execute(f"""
                    SELECT resource_id, clinical_code, clinical_display, event_time_norm, event_time_epoch
                    FROM timeline_events
                    WHERE resource_id IN ({q_marks})
                    """, target_ids)
                    rows = cursor.fetchall()
                    for r in rows:
                        evidence.append({
                            "resource_id": r["resource_id"],
                            "display": r["clinical_display"],
                            "timestamp": r["event_time_norm"]
                        })
        except Exception as e:
            evidence.append({"error": f"Evidence lookup error: {str(e)}"})
        finally:
            conn.close()

        return evidence

    @staticmethod
    def adapt_predicate_for_verifier(predicate: Dict[str, Any], task_code: str) -> Dict[str, Any]:
        """
        Deterministic runtime adapter normalizing binder predicates to OracleTemporalVerifier schema.
        Maps slot aliases and extracts canonical fields without altering scientific semantics.
        """
        if not predicate:
            return {}
        c_type = predicate.get("claim_type")
        comp = predicate.get("comparator")
        c_dir = predicate.get("claimed_direction")
        if not c_dir:
            if c_type == "TREND_INCREASING" or (comp == "GT" and task_code == "S1"):
                c_dir = "INCREASING"
            elif c_type == "TREND_DECREASING" or (comp == "LT" and task_code == "S1"):
                c_dir = "DECREASING"

        return {
            "concept": predicate.get("clinical_concept") or predicate.get("concept"),
            "claim_type": c_type,
            "comparator": comp,
            "window": predicate.get("temporal_window") or predicate.get("window"),
            "claimed_direction": c_dir,
            "claimed_value": predicate.get("claimed_value"),
            "event_A_id": predicate.get("event_A_id"),
            "event_B_id": predicate.get("event_B_id")
        }

    def verify_action(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main Runtime Interlock Contract:
        Validates request -> Rule Fast-Path -> Confidence-Gated AI Fallback -> Symbolic Verifier.
        Enforces 100% Fail-Closed Policy on any error or low confidence.
        """
        action_id = request.get("action_id") or f"act_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        patient_id = request.get("patient_id")
        claim_text = request.get("claim_text", "").strip()
        proposed_tool = request.get("proposed_tool", "update_patient_note")
        tool_args = request.get("tool_arguments", {})
        action_type = request.get("action_type", "CLINICAL_NOTE_UPDATE")

        # 1. Fail-closed on missing inputs
        if not patient_id or not claim_text:
            out = {
                "action_id": action_id,
                "decision": "HOLD",
                "route": "HOLD",
                "structured_predicate": {},
                "binder_confidence": None,
                "verifier_result": "Missing required patient_id or claim_text",
                "reason_codes": ["INVALID_INPUT_PAYLOAD"],
                "evidence": [],
                "tool_execution_allowed": False
            }
            self.audit_logger.log_verification(
                patient_id=str(patient_id), action_id=action_id, claim_text=claim_text,
                proposed_tool=proposed_tool, tool_arguments=tool_args, semantic_route="HOLD",
                structured_predicate={}, binder_confidence=None, decision="HOLD",
                verifier_result=out["verifier_result"], reason_codes=out["reason_codes"],
                evidence=[], tool_executed=False
            )
            return out

        # 2. Check patient existence in FHIR timeline
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM timeline_events WHERE patient_id = ?", (patient_id,))
        p_count = cursor.fetchone()[0]
        conn.close()

        if p_count == 0:
            out = {
                "action_id": action_id,
                "decision": "HOLD",
                "route": "HOLD",
                "structured_predicate": {},
                "binder_confidence": None,
                "verifier_result": f"Patient {patient_id} not found in authoritative FHIR timeline database.",
                "reason_codes": ["PATIENT_NOT_FOUND"],
                "evidence": [],
                "tool_execution_allowed": False
            }
            self.audit_logger.log_verification(
                patient_id=patient_id, action_id=action_id, claim_text=claim_text,
                proposed_tool=proposed_tool, tool_arguments=tool_args, semantic_route="HOLD",
                structured_predicate={}, binder_confidence=None, decision="HOLD",
                verifier_result=out["verifier_result"], reason_codes=out["reason_codes"],
                evidence=[], tool_executed=False
            )
            return out

        # 3. Candidate timeline events for S2
        candidate_events = request.get("candidate_events")
        if not candidate_events:
            # Look up recent events for patient
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
            SELECT resource_id, clinical_display FROM timeline_events
            WHERE patient_id = ? AND is_post_death_event = 0 AND clinical_display IS NOT NULL
            ORDER BY event_time_epoch ASC
            """, (patient_id,))
            candidate_events = [{"resource_id": r["resource_id"], "clinical_display": r["clinical_display"]} for r in cursor.fetchall()]
            conn.close()

        # 4. Step 1: Rule Fast-Path
        try:
            r_pred = self.rule_binder.parse(claim_text, candidate_events=candidate_events)
        except Exception as e:
            r_pred = {}

        if self._is_rule_predicate_valid(r_pred):
            route = "RULE"
            final_predicate = r_pred
            conf = 1.0
        else:
            # Step 2: Confidence-Gated Semantic AI Fallback
            try:
                a_pred = self.ai_binder.parse(claim_text, candidate_events=candidate_events)
                conf = float(a_pred.get("confidence", 0.0))
            except Exception as e:
                a_pred = {}
                conf = 0.0

            if self._is_ai_predicate_valid(a_pred) and conf >= self.tau:
                route = "AI_FALLBACK"
                final_predicate = a_pred
            else:
                # Abstain / HOLD
                route = "HOLD"
                final_predicate = {}
                reason = "Low semantic parser confidence or ambiguous syntax" if conf < self.tau else "Incomplete/invalid semantic predicate structure"
                out = {
                    "action_id": action_id,
                    "decision": "HOLD",
                    "route": "HOLD",
                    "structured_predicate": a_pred if a_pred else {},
                    "binder_confidence": conf,
                    "verifier_result": f"Abstained: {reason} (confidence={conf:.2f} < threshold={self.tau:.2f})",
                    "reason_codes": ["LOW_CONFIDENCE_OR_UNRECOGNIZED_SYNTAX"],
                    "evidence": [],
                    "tool_execution_allowed": False
                }
                self.audit_logger.log_verification(
                    patient_id=patient_id, action_id=action_id, claim_text=claim_text,
                    proposed_tool=proposed_tool, tool_arguments=tool_args, semantic_route="HOLD",
                    structured_predicate=a_pred, binder_confidence=conf, decision="HOLD",
                    verifier_result=out["verifier_result"], reason_codes=out["reason_codes"],
                    evidence=[], tool_executed=False
                )
                return out

        # 5. Step 3: Symbolic FHIR Verifier Execution
        task_code = final_predicate.get("task_type", "S4")
        
        # Resolve source_event_ids if not provided
        resolved_event_ids = request.get("source_event_ids", [])
        if task_code == "S2":
            resolved_event_ids = [final_predicate.get("event_A_id"), final_predicate.get("event_B_id")]
        elif not resolved_event_ids and final_predicate.get("clinical_concept"):
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if task_code == "S1":
                cursor.execute("""
                SELECT resource_id FROM timeline_events
                WHERE patient_id = ? AND clinical_code = ? AND resource_type = 'Observation' AND value_numeric IS NOT NULL AND is_post_death_event = 0
                ORDER BY event_time_epoch DESC
                LIMIT 3
                """, (patient_id, final_predicate["clinical_concept"]))
                rows = cursor.fetchall()
                resolved_event_ids = [r[0] for r in reversed(rows)]
            elif task_code == "S3":
                cursor.execute("""
                SELECT resource_id FROM timeline_events
                WHERE patient_id = ? AND clinical_code = ? AND resource_type = 'Observation' AND value_numeric IS NOT NULL AND is_post_death_event = 0
                ORDER BY event_time_epoch DESC
                LIMIT 2
                """, (patient_id, final_predicate["clinical_concept"]))
                rows = cursor.fetchall()
                resolved_event_ids = [r[0] for r in reversed(rows)]
            conn.close()

        claim_rec = {
            "task_code": task_code,
            "patient_id": patient_id,
            "claim_text": claim_text,
            "structured_predicate": self.adapt_predicate_for_verifier(final_predicate, task_code),
            "source_event_ids": resolved_event_ids
        }

        try:
            verdict, explanation = self.verifier.verify_claim_predicate(claim_rec)
        except Exception as e:
            verdict = "HOLD"
            explanation = f"Symbolic verifier execution error: {str(e)}"

        evidence_list = self._fetch_evidence_records(patient_id, task_code, final_predicate, resolved_event_ids)

        decision = verdict if verdict in ["PASS", "BLOCK", "HOLD"] else "HOLD"
        allowed = (decision == "PASS")
        reason_codes = [f"VERDICT_{decision}", f"ROUTE_{route}"]

        out = {
            "action_id": action_id,
            "decision": decision,
            "route": route,
            "structured_predicate": final_predicate,
            "binder_confidence": conf,
            "verifier_result": explanation,
            "reason_codes": reason_codes,
            "evidence": evidence_list,
            "tool_execution_allowed": allowed
        }

        self.audit_logger.log_verification(
            patient_id=patient_id, action_id=action_id, claim_text=claim_text,
            proposed_tool=proposed_tool, tool_arguments=tool_args, semantic_route=route,
            structured_predicate=final_predicate, binder_confidence=conf, decision=decision,
            verifier_result=explanation, reason_codes=reason_codes,
            evidence=evidence_list, tool_executed=False
        )

        return out
