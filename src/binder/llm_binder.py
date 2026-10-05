"""
ContextBind — Semantic LLM Claim Binder (Architectural Component)
Extracts structured temporal predicates from natural open-vocabulary agent justifications.

Strict Operational Contract:
- Does NOT predict SUPPORTED / CONTRADICTED labels (No label leakage).
- Strictly performs text -> structured temporal predicate extraction:
  * task_type: S1 | S2 | S3 | S4
  * clinical_concept: LOINC / SNOMED code or canonical name
  * claim_type: TREND_INCREASING | TREND_DECREASING | BEFORE | AFTER | HIGHER_THAN_PREVIOUS | LOWER_THAN_PREVIOUS | CURRENT_VALUE
  * temporal_window: LAST_3 | PREVIOUS | CURRENT | None
  * comparator: GT | LT | EQ | None
  * claimed_value: float or None
  * event_A: str / ID or None
  * event_B: str / ID or None
  * confidence: float [0.0, 1.0]
- If schema validation fails or confidence < threshold: returns HOLD / None.
- Downstream verification is strictly executed by symbolic OracleTemporalVerifier.
"""

import os
import json
import re
from typing import Dict, Any, Optional, List

LLM_BINDER_SYSTEM_PROMPT = """You are a precise clinical information extraction module.
Your task is to parse an AI clinical agent's natural-language justification into a structured temporal predicate.
Do NOT attempt to judge whether the claim is true or false.
Only extract the semantic components according to the JSON schema.

Schema:
{
  "task_type": "S1" | "S2" | "S3" | "S4",
  "clinical_concept": string or null,
  "claim_type": "TREND_INCREASING" | "TREND_DECREASING" | "BEFORE" | "AFTER" | "HIGHER_THAN_PREVIOUS" | "LOWER_THAN_PREVIOUS" | "CURRENT_VALUE",
  "temporal_window": "LAST_3" | "PREVIOUS" | "CURRENT" | null,
  "comparator": "GT" | "LT" | "EQ" | null,
  "claimed_value": float or null,
  "event_A": string or null,
  "event_B": string or null,
  "confidence": float between 0.0 and 1.0
}
Output strictly valid JSON matching this schema and nothing else."""

class LLMClaimBinder:
    def __init__(self, model_name: str = "gpt-4o-mini", api_key: Optional[str] = None, confidence_threshold: float = 0.70):
        self.model_name = model_name
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        self.confidence_threshold = confidence_threshold

    def is_available(self) -> bool:
        """Checks if remote or local LLM execution runtime is configured."""
        return bool(self.api_key)

    def parse(self, claim_text: str, candidate_events: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Extracts structured temporal predicate from natural claim text.
        Returns normalized dictionary with parsed elements or HOLD fallback.
        """
        if not self.is_available():
            return {
                "task_type": "UNKNOWN",
                "clinical_concept": None,
                "claim_type": "UNKNOWN",
                "temporal_window": None,
                "comparator": None,
                "claimed_value": None,
                "event_A_id": None,
                "event_B_id": None,
                "confidence": 0.0,
                "status": "HOLD_RUNTIME_UNAVAILABLE"
            }

        prompt = f"Claim text: \"{claim_text}\"\n"
        if candidate_events:
            prompt += "Candidate EHR timeline events:\n"
            for ev in candidate_events:
                prompt += f"- ID: {ev.get('resource_id')} | Name: {ev.get('clinical_display')}\n"

        # In live deployment, call OpenAI / Anthropic / Ollama client here
        # Return fallback if network / parse error
        return {
            "task_type": "UNKNOWN",
            "clinical_concept": None,
            "claim_type": "UNKNOWN",
            "temporal_window": None,
            "comparator": None,
            "claimed_value": None,
            "event_A_id": None,
            "event_B_id": None,
            "confidence": 0.0,
            "status": "HOLD"
        }
