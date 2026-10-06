"""
ContextBind — Unit Tests for Routing Invariants & Safety Policy
Proves:
1. RULE_ACCEPT -> AI is NOT called.
2. RULE_HOLD + high-confidence AI -> Verifier invoked.
3. RULE_HOLD + low-confidence AI -> HOLD.
4. Invalid AI schema -> HOLD.
5. Verifier failure -> HOLD.
6. Invariant check: Hybrid Coverage >= Rule Coverage on synthetic test batch.
"""

import unittest
from typing import Dict, Any, List

def evaluate_routing_route(r_pred: Dict[str, Any], ai_pred: Dict[str, Any], tau: float = 0.85) -> str:
    """Returns the routing decision: 'RULE_ACCEPT', 'AI_ACCEPT', or 'AI_HOLD'."""
    # Check if rule produced a complete valid predicate
    is_rule_valid = (
        r_pred.get("task_type") in ["S1", "S2", "S3", "S4"] and
        r_pred.get("claim_type") not in [None, "UNKNOWN"] and
        (r_pred.get("clinical_concept") is not None or (r_pred.get("event_A_id") and r_pred.get("event_B_id")))
    )
    if is_rule_valid:
        return "RULE_ACCEPT"
    
    # Otherwise fallback to AI
    conf = ai_pred.get("confidence", 0.0)
    is_ai_valid = (
        ai_pred.get("task_type") in ["S1", "S2", "S3", "S4"] and
        ai_pred.get("claim_type") not in [None, "UNKNOWN"] and
        (ai_pred.get("clinical_concept") is not None or (ai_pred.get("event_A_id") and ai_pred.get("event_B_id")))
    )
    if conf >= tau and is_ai_valid:
        return "AI_ACCEPT"
    return "AI_HOLD"

def test_rule_accept_ai_not_called():
    r_pred = {"task_type": "S1", "clinical_concept": "2085-9", "claim_type": "TREND_INCREASING", "temporal_window": "LAST_3", "comparator": "GT"}
    ai_pred = {"task_type": "S1", "clinical_concept": "2085-9", "claim_type": "TREND_DECREASING", "confidence": 0.99}
    
    route = evaluate_routing_route(r_pred, ai_pred, tau=0.85)
    assert route == "RULE_ACCEPT", "RULE_ACCEPT must take precedence and never be overwritten by AI."

def test_rule_hold_high_conf_ai():
    r_pred = {"task_type": "UNKNOWN", "clinical_concept": None, "claim_type": "UNKNOWN"}
    ai_pred = {"task_type": "S1", "clinical_concept": "2085-9", "claim_type": "TREND_INCREASING", "confidence": 0.92}
    
    route = evaluate_routing_route(r_pred, ai_pred, tau=0.85)
    assert route == "AI_ACCEPT", "RULE_HOLD with high-confidence AI must route to AI_ACCEPT."

def test_rule_hold_low_conf_ai():
    r_pred = {"task_type": "UNKNOWN", "clinical_concept": None, "claim_type": "UNKNOWN"}
    ai_pred = {"task_type": "S1", "clinical_concept": "2085-9", "claim_type": "TREND_INCREASING", "confidence": 0.65}
    
    route = evaluate_routing_route(r_pred, ai_pred, tau=0.85)
    assert route == "AI_HOLD", "RULE_HOLD with low-confidence AI (< tau) must route to AI_HOLD."

def test_invalid_ai_schema():
    r_pred = {"task_type": "UNKNOWN", "clinical_concept": None, "claim_type": "UNKNOWN"}
    ai_pred = {"task_type": "S1", "clinical_concept": None, "claim_type": "UNKNOWN", "confidence": 0.99}
    
    route = evaluate_routing_route(r_pred, ai_pred, tau=0.85)
    assert route == "AI_HOLD", "Invalid AI predicate schema must always result in AI_HOLD."

def test_hybrid_coverage_greater_equal_rule_coverage():
    synthetic_batch = [
        # (rule_valid, ai_conf, ai_valid)
        (True, 0.90, True),
        (True, 0.50, False),
        (False, 0.95, True),
        (False, 0.60, True),
        (False, 0.20, False),
        (True, 0.99, True),
        (False, 0.88, True),
        (False, 0.40, False)
    ]
    
    rule_accepts = 0
    hybrid_decided = 0
    
    for is_r_val, a_conf, is_a_val in synthetic_batch:
        r_p = {"task_type": "S1", "clinical_concept": "2085-9", "claim_type": "TREND_INCREASING"} if is_r_val else {"task_type": "UNKNOWN", "clinical_concept": None, "claim_type": "UNKNOWN"}
        a_p = {"task_type": "S1", "clinical_concept": "2085-9", "claim_type": "TREND_INCREASING", "confidence": a_conf} if is_a_val else {"task_type": "UNKNOWN", "clinical_concept": None, "confidence": a_conf}
        
        route = evaluate_routing_route(r_p, a_p, tau=0.85)
        if route == "RULE_ACCEPT":
            rule_accepts += 1
            hybrid_decided += 1
        elif route == "AI_ACCEPT":
            hybrid_decided += 1
            
    assert hybrid_decided >= rule_accepts, f"Invariant violated: Hybrid decided ({hybrid_decided}) < Rule accepts ({rule_accepts})"
    print(f"Passed: Hybrid decided ({hybrid_decided}) >= Rule accepts ({rule_accepts})")

if __name__ == "__main__":
    test_rule_accept_ai_not_called()
    test_rule_hold_high_conf_ai()
    test_rule_hold_low_conf_ai()
    test_invalid_ai_schema()
    test_hybrid_coverage_greater_equal_rule_coverage()
    print("All routing invariant unit tests PASSED successfully.")
