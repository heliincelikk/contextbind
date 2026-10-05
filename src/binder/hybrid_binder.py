"""
ContextBind — Neuro-Symbolic Hybrid Semantic Claim Binder
Combines ML semantic interpretation with deterministic entity and numeric extraction.
Strictly uses Python Standard Library + scikit-learn / numpy.
"""

from typing import Dict, Any, Optional, List
from src.binder.rule_binder import RuleBasedClaimBinder
from src.binder.ml_binder import MLClaimBinder

class HybridClaimBinder:
    def __init__(self, confidence_threshold: Optional[float] = None, seed: int = 20261004):
        self.confidence_threshold = confidence_threshold
        self.seed = seed
        self.rule_binder = RuleBasedClaimBinder()
        self.ml_binder = MLClaimBinder(seed=seed)
        self.is_fitted = False

    def fit(self, train_claims: List[Dict[str, Any]]) -> "HybridClaimBinder":
        """
        Fits both rule-based vocabulary and ML classifier heads on training split.
        """
        self.rule_binder.fit(train_claims)
        self.ml_binder.fit(train_claims)
        self.is_fitted = True
        return self

    def parse(self, claim_text: str, candidate_events: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Executes neuro-symbolic parsing:
        - ML head resolves semantic task_type, claim_type, comparator.
        - Deterministic extraction resolves exact concept code, claimed_value, and event linking.
        - If confidence < threshold, marks as HOLD.
        """
        if not self.is_fitted:
            raise RuntimeError("HybridClaimBinder must be fitted before parse().")

        ml_pred = self.ml_binder.parse(claim_text, candidate_events)
        rule_pred = self.rule_binder.parse(claim_text, candidate_events)

        confidence = ml_pred.get("confidence", 1.0)
        is_hold = False
        if self.confidence_threshold is not None and confidence < self.confidence_threshold:
            is_hold = True

        # Use ML for high-level semantic intent & relation, and rule/dictionary for exact ontology slots
        concept_code = ml_pred.get("clinical_concept") or rule_pred.get("clinical_concept")
        claimed_val = ml_pred.get("claimed_value") if ml_pred.get("claimed_value") is not None else rule_pred.get("claimed_value")
        event_A = ml_pred.get("event_A_id") or rule_pred.get("event_A_id")
        event_B = ml_pred.get("event_B_id") or rule_pred.get("event_B_id")

        return {
            "task_type": ml_pred["task_type"],
            "clinical_concept": concept_code,
            "claim_type": ml_pred["claim_type"],
            "temporal_window": ml_pred["temporal_window"],
            "comparator": ml_pred["comparator"],
            "claimed_value": claimed_val,
            "event_A_id": event_A,
            "event_B_id": event_B,
            "confidence": confidence,
            "is_hold": is_hold
        }
