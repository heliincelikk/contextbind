"""
ContextBind — Guarded Consequential Clinical Tool Executor
Intercepts consequential clinical agent actions and enforces the ContextBind Pre-Action Interlock.

Safety Guarantees:
- Agent-facing tools are guarded by default.
- PASS -> exactly one execution.
- BLOCK -> zero executions (Execution explicitly denied).
- HOLD -> zero executions (Held for clinical safety review).
- Exceptions/errors in verifier or binder -> zero executions.
- Supports guard_enabled flag strictly for side-by-side Guard OFF vs Guard ON comparative demonstrations.
"""

import os
import sys
import json
import datetime
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.runtime.contextbind_runtime import ContextBindRuntime
from src.runtime.audit_logger import RuntimeAuditLogger

class ConsequentialClinicalTools:
    """Simulated authoritative hospital clinical tools with observable database side effects."""
    
    @staticmethod
    def write_clinical_summary_draft(patient_id: str, summary_text: str, department: str = "Internal Medicine", author: str = "Clinical AI Agent") -> Dict[str, Any]:
        return {
            "status": "SUCCESS",
            "operation": "write_clinical_summary_draft",
            "patient_id": patient_id,
            "department": department,
            "author": author,
            "summary_text": summary_text,
            "committed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "draft_id": f"draft_{patient_id[:8]}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        }

    @staticmethod
    def commit_handoff_summary(patient_id: str, handoff_text: str, target_unit: str = "ICU Stepdown", author: str = "Clinical AI Agent") -> Dict[str, Any]:
        return {
            "status": "SUCCESS",
            "operation": "commit_handoff_summary",
            "patient_id": patient_id,
            "target_unit": target_unit,
            "author": author,
            "handoff_text": handoff_text,
            "committed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "handoff_id": f"hnd_{patient_id[:8]}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        }

    @staticmethod
    def update_patient_note(patient_id: str, note_text: str, author: str = "Clinical AI Agent", tags: Optional[list] = None) -> Dict[str, Any]:
        return {
            "status": "SUCCESS",
            "operation": "update_patient_note",
            "patient_id": patient_id,
            "author": author,
            "note_text": note_text,
            "tags": tags or ["AI_GENERATED", "PROGRESS_NOTE"],
            "committed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "record_version": 2
        }

    @staticmethod
    def write_clinical_summary(patient_id: str, summary_text: str, department: str = "Internal Medicine") -> Dict[str, Any]:
        return ConsequentialClinicalTools.write_clinical_summary_draft(patient_id=patient_id, summary_text=summary_text, department=department)

class GuardedToolExecutor:
    def __init__(self, runtime: Optional[ContextBindRuntime] = None, audit_db_path: str = "data/interim/runtime_audit_log.sqlite"):
        self.runtime = runtime or ContextBindRuntime(audit_db_path=audit_db_path)
        self.audit_logger = RuntimeAuditLogger(audit_db_path)
        self.tool_registry = {
            "write_clinical_summary_draft": ConsequentialClinicalTools.write_clinical_summary_draft,
            "commit_handoff_summary": ConsequentialClinicalTools.commit_handoff_summary,
            "update_patient_note": ConsequentialClinicalTools.update_patient_note,
            "write_clinical_summary": ConsequentialClinicalTools.write_clinical_summary
        }

    def execute_guarded_action(self, request: Dict[str, Any], guard_enabled: bool = True) -> Dict[str, Any]:
        """
        Main Agent-Facing Execution Interface.
        Evaluates pre-action verification before granting tool execution permissions.
        """
        action_id = request.get("action_id") or f"act_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        patient_id = request.get("patient_id", "UNKNOWN")
        proposed_tool = request.get("proposed_tool", "update_patient_note")
        tool_args = request.get("tool_arguments", {})

        tool_func = self.tool_registry.get(proposed_tool)
        if not tool_func:
            return {
                "action_id": action_id,
                "executed": False,
                "guard_enabled": guard_enabled,
                "decision": "HOLD",
                "status": "TOOL_NOT_REGISTERED",
                "message": f"Tool '{proposed_tool}' is not recognized in clinical tool registry.",
                "verification": None,
                "execution_response": None
            }

        # -------------------------------------------------------------
        # Guard OFF Mode (Demonstration baseline only)
        # -------------------------------------------------------------
        if not guard_enabled:
            # Execute tool directly without pre-action safety verification
            try:
                exec_res = tool_func(patient_id=patient_id, **tool_args)
                self.audit_logger.log_side_effect(patient_id, action_id, proposed_tool, exec_res, status="EXECUTED_UNGUARDED")
                return {
                    "action_id": action_id,
                    "executed": True,
                    "guard_enabled": False,
                    "decision": "UNGUARDED_EXECUTION",
                    "status": "SUCCESS",
                    "message": "Action executed without ContextBind pre-action interlock protection (GUARD OFF).",
                    "verification": None,
                    "execution_response": exec_res
                }
            except Exception as e:
                return {
                    "action_id": action_id,
                    "executed": False,
                    "guard_enabled": False,
                    "decision": "ERROR",
                    "status": "EXECUTION_EXCEPTION",
                    "message": f"Tool execution failed: {str(e)}",
                    "verification": None,
                    "execution_response": None
                }

        # -------------------------------------------------------------
        # Guard ON Mode (Active Runtime Interlock)
        # -------------------------------------------------------------
        verification_res = self.runtime.verify_action(request)
        decision = verification_res.get("decision", "HOLD")
        allowed = verification_res.get("tool_execution_allowed", False)

        if allowed and decision == "PASS":
            try:
                exec_res = tool_func(patient_id=patient_id, **tool_args)
                self.audit_logger.log_side_effect(patient_id, action_id, proposed_tool, exec_res, status="EXECUTED_VERIFIED")
                return {
                    "action_id": action_id,
                    "executed": True,
                    "guard_enabled": True,
                    "decision": "PASS",
                    "status": "SUCCESS",
                    "message": "Action verified against longitudinal EHR timeline and executed successfully.",
                    "verification": verification_res,
                    "execution_response": exec_res
                }
            except Exception as e:
                return {
                    "action_id": action_id,
                    "executed": False,
                    "guard_enabled": True,
                    "decision": "PASS",
                    "status": "TOOL_ERROR",
                    "message": f"Verification passed but tool threw exception: {str(e)}",
                    "verification": verification_res,
                    "execution_response": None
                }
        elif decision == "BLOCK":
            return {
                "action_id": action_id,
                "executed": False,
                "guard_enabled": True,
                "decision": "BLOCK",
                "status": "BLOCKED",
                "message": f"Action blocked by ContextBind: {verification_res.get('verifier_result')}",
                "verification": verification_res,
                "execution_response": None
            }
        else: # HOLD
            return {
                "action_id": action_id,
                "executed": False,
                "guard_enabled": True,
                "decision": "HOLD",
                "status": "HELD_FOR_REVIEW",
                "message": f"Action held by ContextBind for human clinician safety review: {verification_res.get('verifier_result')}",
                "verification": verification_res,
                "execution_response": None
            }
