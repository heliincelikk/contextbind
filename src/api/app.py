"""
ContextBind — Runtime REST API Service
Provides endpoints for:
- POST /verify-action: Pre-action claim verification
- POST /execute-action: Guarded consequential tool execution
- GET /health: Operational component status & configuration hashes
- GET /scenarios: 5 Canonical Demo Scenarios (D1-D5) & Guard ON/OFF
- GET /audit-logs: Runtime verification logs
"""

import os
import sys
import json
import hashlib
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.runtime.contextbind_runtime import ContextBindRuntime
from src.runtime.guarded_executor import GuardedToolExecutor

app = FastAPI(
    title="ContextBind Runtime Interlock API",
    description="Pre-Action Runtime Safety Interlock for Clinical AI Agents",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Runtime & Executor Singletons
RUNTIME = ContextBindRuntime()
EXECUTOR = GuardedToolExecutor(runtime=RUNTIME)

class VerifyActionRequest(BaseModel):
    patient_id: str = Field(..., description="EHR Patient UUID")
    action_type: str = Field(default="CLINICAL_NOTE_UPDATE", description="Consequential action category")
    claim_text: str = Field(..., description="Natural language justification asserted by the agent")
    proposed_tool: str = Field(default="update_patient_note", description="Target tool name")
    tool_arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments for tool execution")
    as_of_time: Optional[str] = Field(default=None, description="ISO timestamp of action evaluation")
    action_id: Optional[str] = Field(default=None, description="Unique action transaction ID")
    candidate_events: Optional[List[Dict[str, Any]]] = Field(default=None, description="Candidate timeline event names/IDs for S2")

class ExecuteActionRequest(BaseModel):
    patient_id: str
    action_type: str = "CLINICAL_NOTE_UPDATE"
    claim_text: str
    proposed_tool: str = "update_patient_note"
    tool_arguments: Dict[str, Any] = Field(default_factory=dict)
    as_of_time: Optional[str] = None
    action_id: Optional[str] = None
    guard_enabled: bool = Field(default=True, description="Enables ContextBind Pre-Action Interlock")
    candidate_events: Optional[List[Dict[str, Any]]] = None

@app.get("/health")
def get_health():
    hashes = {}
    for fpath in ["src/binder/rule_binder.py", "src/binder/semantic_ai_binder.py", "src/verification/oracle_temporal_verifier.py"]:
        if os.path.exists(fpath):
            hashes[os.path.basename(fpath)] = hashlib.sha256(open(fpath, "rb").read()).hexdigest()

    return {
        "status": "HEALTHY",
        "service": "ContextBind Pre-Action Runtime Interlock",
        "product_tagline": "Right patient. Right context. Right time. Before action.",
        "disclaimer": "Research prototype. Not for clinical use or autonomous medical decision-making.",
        "operational_policy": "Rule-First + Confidence-Gated Semantic AI Fallback (tau=0.70) -> Symbolic FHIR Verifier",
        "confidence_threshold_tau": RUNTIME.tau,
        "component_hashes": hashes
    }

@app.post("/verify-action")
def verify_action(req: VerifyActionRequest):
    res = RUNTIME.verify_action(req.dict())
    return res

@app.post("/execute-action")
def execute_action(req: ExecuteActionRequest):
    res = EXECUTOR.execute_guarded_action(req.dict(), guard_enabled=req.guard_enabled)
    return res

@app.get("/scenarios")
def get_scenarios():
    scenarios_path = "reports/phases/P6_DEMO_SCENARIOS.json"
    if os.path.exists(scenarios_path):
        with open(scenarios_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"error": "Scenarios file not found"}

@app.get("/audit-logs")
def get_audit_logs(limit: int = 50):
    audits = RUNTIME.audit_logger.get_recent_audits(limit=limit)
    side_effects = RUNTIME.audit_logger.get_recent_side_effects(limit=limit)
    return {
        "verification_audits": audits,
        "tool_side_effects": side_effects
    }

# Mount static files for UI if directory exists
ui_dir = os.path.join(os.path.dirname(__file__), "../ui")
if os.path.exists(ui_dir):
    app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
