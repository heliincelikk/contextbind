"""
ContextBind — Runtime Audit Logger
Persists runtime verification requests, semantic routing paths, structured predicates,
symbolic evidence, interlock decisions, and tool execution logs.
Strictly separated from authoritative source FHIR databases.
"""

import os
import json
import sqlite3
import datetime
from typing import Dict, Any, List, Optional

class RuntimeAuditLogger:
    def __init__(self, db_path: str = "data/interim/runtime_audit_log.sqlite"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS runtime_audit_log (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_utc TEXT NOT NULL,
            patient_id TEXT NOT NULL,
            action_id TEXT NOT NULL,
            claim_text TEXT NOT NULL,
            proposed_tool TEXT NOT NULL,
            tool_arguments_json TEXT NOT NULL,
            semantic_route TEXT NOT NULL,
            structured_predicate_json TEXT NOT NULL,
            binder_confidence REAL,
            decision TEXT NOT NULL,
            verifier_result TEXT NOT NULL,
            reason_codes_json TEXT NOT NULL,
            evidence_json TEXT NOT NULL,
            tool_executed INTEGER NOT NULL,
            execution_response_json TEXT
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS clinical_tool_side_effects (
            effect_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_utc TEXT NOT NULL,
            patient_id TEXT NOT NULL,
            action_id TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """)
        conn.commit()
        conn.close()

    def log_verification(
        self,
        patient_id: str,
        action_id: str,
        claim_text: str,
        proposed_tool: str,
        tool_arguments: Dict[str, Any],
        semantic_route: str,
        structured_predicate: Dict[str, Any],
        binder_confidence: Optional[float],
        decision: str,
        verifier_result: str,
        reason_codes: List[str],
        evidence: List[Dict[str, Any]],
        tool_executed: bool,
        execution_response: Optional[Dict[str, Any]] = None
    ) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor.execute("""
        INSERT INTO runtime_audit_log (
            timestamp_utc, patient_id, action_id, claim_text, proposed_tool,
            tool_arguments_json, semantic_route, structured_predicate_json,
            binder_confidence, decision, verifier_result, reason_codes_json,
            evidence_json, tool_executed, execution_response_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now_utc,
            patient_id,
            action_id,
            claim_text,
            proposed_tool,
            json.dumps(tool_arguments),
            semantic_route,
            json.dumps(structured_predicate),
            binder_confidence,
            decision,
            verifier_result,
            json.dumps(reason_codes),
            json.dumps(evidence),
            1 if tool_executed else 0,
            json.dumps(execution_response or {})
        ))
        audit_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return audit_id

    def log_side_effect(self, patient_id: str, action_id: str, tool_name: str, payload: Dict[str, Any], status: str) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor.execute("""
        INSERT INTO clinical_tool_side_effects (
            timestamp_utc, patient_id, action_id, tool_name, payload_json, status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """, (now_utc, patient_id, action_id, tool_name, json.dumps(payload), status))
        effect_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return effect_id

    def get_recent_audits(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM runtime_audit_log ORDER BY audit_id DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def get_recent_side_effects(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clinical_tool_side_effects ORDER BY effect_id DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows
