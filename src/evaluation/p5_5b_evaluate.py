"""
ContextBind — Phase P5.5b Evidence Repair & Real Semantic AI Evaluation Engine
Executes complete metric accounting, provenance audit, and real pretrained Semantic AI evaluation on Lane B.
"""

import os
import sys
import json
import csv
import time
import random
from collections import defaultdict, Counter
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.binder.rule_binder import RuleBasedClaimBinder
from src.binder.ml_binder import MLClaimBinder
from src.binder.semantic_ai_binder import SemanticAIBinder
from src.binder.direct_text_classifier import DirectTextClassifier
from src.verification.oracle_temporal_verifier import OracleTemporalVerifier
from src.evaluation.p5_evaluate import evaluate_predicates, load_jsonl

def run_p5_5b():
    print("=" * 70)
    print("CONTEXTBIND — PHASE P5.5b EVIDENCE REPAIR & REAL SEMANTIC AI EVALUATION")
    print("=" * 70)

    db_path = "data/interim/contextbind_timeline.sqlite"
    train_path = "data/processed/p4_final_train.jsonl"
    lane_b_file = "data/processed/p5_5_lane_b_natural_claims.jsonl"
    seed = 20261004

    # 1. Load Lane B dataset
    print(f"\n[1/4] Loading Lane B dataset ({lane_b_file})...")
    lane_b_claims = load_jsonl(lane_b_file)
    total_claims = len(lane_b_claims)
    sup_claims = [c for c in lane_b_claims if c["ground_truth"] == "SUPPORTED"]
    con_claims = [c for c in lane_b_claims if c["ground_truth"] == "CONTRADICTED"]
    n_total = total_claims
    n_sup = len(sup_claims)
    n_con = len(con_claims)

    print(f"  Total claims: {n_total} (Supported: {n_sup}, Contradicted: {n_con})")

    # 2. Provenance Analysis
    print("\n[2/4] Analyzing Lane B Provenance & Lexical Variation...")
    unique_texts = set(c["claim_text"] for c in lane_b_claims)
    template_families = Counter(c["template_family"] for c in lane_b_claims)
    print(f"  Unique surface sentences: {len(unique_texts)} / {total_claims}")
    print(f"  Template families: {len(template_families)} distinct adversarial families across S1-S4")

    # 3. Train all binders strictly on P4 TRAIN
    print("\n[3/4] Fitting Binders strictly on Frozen P4 TRAIN split...")
    train_claims = load_jsonl(train_path)

    rule_binder = RuleBasedClaimBinder().fit(train_claims)
    ml_binder = MLClaimBinder(seed=seed).fit(train_claims)
    semantic_ai_binder = SemanticAIBinder(model_name="distilbert/distilbert-base-uncased", seed=seed).fit(train_claims)
    direct_text_clf = DirectTextClassifier(seed=seed).fit(train_claims)

    # 4. Evaluate all models on Lane B
    print("\n[4/4] Evaluating Models on Lane B...")
    verifier = OracleTemporalVerifier(db_path)

    conn = verifier._connect()
    cursor = conn.cursor()
    cursor.execute("SELECT resource_id, clinical_display FROM timeline_events WHERE is_post_death_event = 0")
    event_display_map = {r[0]: r[1] for r in cursor.fetchall()}
    conn.close()

    # Hybrid Rule + Semantic AI
    class HybridRuleAIBinder:
        def __init__(self, rule_b, ai_b):
            self.rule_b = rule_b
            self.ai_b = ai_b
        def parse(self, text, candidate_events=None):
            r_res = self.rule_b.parse(text, candidate_events)
            if r_res.get("task_type") != "UNKNOWN" and r_res.get("clinical_concept") is not None and r_res.get("claim_type") != "UNKNOWN":
                return r_res
            return self.ai_b.parse(text, candidate_events)

    hybrid_rule_ai = HybridRuleAIBinder(rule_binder, semantic_ai_binder)

    models = [
        ("B_RULE_FROZEN", rule_binder),
        ("B_ML_FROZEN", ml_binder),
        ("SEMANTIC_AI_BERT_TINY", semantic_ai_binder),
        ("HYBRID_RULE_SEMANTIC_AI", hybrid_rule_ai),
        ("B3_DIRECT_TEXT_FROZEN", direct_text_clf)
    ]

    accounting_rows = []
    summary_metrics = []

    for model_name, model in models:
        print(f"\n--- Evaluating {model_name} ---")
        if model_name == "B3_DIRECT_TEXT_FROZEN":
            preds = None
            dt_res = direct_text_clf.predict(lane_b_claims)
            verdicts = [p["verdict"] for p in dt_res]
            pred_match_res = {"exact_predicate_match": 0.0, "task_type_acc": 0.0, "claim_type_acc": 0.0, "comparator_acc": 0.0, "concept_acc": 0.0}
        else:
            preds = []
            for c in lane_b_claims:
                cand_events = None
                if c["task_code"] == "S2":
                    cand_events = [{"resource_id": eid, "clinical_display": event_display_map.get(eid, "")} for eid in c.get("source_event_ids", [])]
                pred = model.parse(c["claim_text"], candidate_events=cand_events)
                preds.append(pred)

            pred_match_res = evaluate_predicates(lane_b_claims, preds)

            claims_with_preds = []
            for c, p in zip(lane_b_claims, preds):
                c_sim = dict(c)
                pred_dict = {
                    "concept": p["clinical_concept"],
                    "claim_type": p["claim_type"],
                    "comparator": p["comparator"],
                    "window": p["temporal_window"],
                    "claimed_direction": "INCREASING" if p["claim_type"] == "TREND_INCREASING" else ("DECREASING" if p["claim_type"] == "TREND_DECREASING" else None),
                    "claimed_value": p["claimed_value"],
                    "event_A_id": p["event_A_id"],
                    "event_B_id": p["event_B_id"]
                }
                c_sim["structured_predicate"] = pred_dict
                claims_with_preds.append(c_sim)

            oracle_res = verifier.verify_batch(claims_with_preds)
            verdicts = [r[0] for r in oracle_res]

        # Accounting Breakdown
        n_pass = sum(1 for v in verdicts if v == "PASS")
        n_block = sum(1 for v in verdicts if v == "BLOCK")
        n_hold = sum(1 for v in verdicts if v == "HOLD")

        sup_pass = sum(1 for i, c in enumerate(lane_b_claims) if c["ground_truth"] == "SUPPORTED" and verdicts[i] == "PASS")
        sup_block = sum(1 for i, c in enumerate(lane_b_claims) if c["ground_truth"] == "SUPPORTED" and verdicts[i] == "BLOCK")
        sup_hold = sum(1 for i, c in enumerate(lane_b_claims) if c["ground_truth"] == "SUPPORTED" and verdicts[i] == "HOLD")

        con_block = sum(1 for i, c in enumerate(lane_b_claims) if c["ground_truth"] == "CONTRADICTED" and verdicts[i] == "BLOCK")
        con_pass = sum(1 for i, c in enumerate(lane_b_claims) if c["ground_truth"] == "CONTRADICTED" and verdicts[i] == "PASS")
        con_hold = sum(1 for i, c in enumerate(lane_b_claims) if c["ground_truth"] == "CONTRADICTED" and verdicts[i] == "HOLD")

        # Frozen Metrics
        uar = con_pass / n_con if n_con else 0.0
        babr = sup_block / n_sup if n_sup else 0.0
        hold_rate = n_hold / n_total
        coverage = (n_pass + n_block) / n_total

        decided_count = n_pass + n_block
        selective_acc = (sup_pass + con_block) / decided_count if decided_count > 0 else 0.0
        overall_utility_acc = (sup_pass + con_block) / n_total

        # Pair Consistency
        pair_map = defaultdict(list)
        for i, c in enumerate(lane_b_claims):
            pair_map[c["pair_id"]].append((c, verdicts[i]))
        consistent_pairs = sum(1 for p_list in pair_map.values() if len(p_list) == 2 and all((v == "PASS" and c["ground_truth"] == "SUPPORTED") or (v == "BLOCK" and c["ground_truth"] == "CONTRADICTED") for c, v in p_list))
        pair_cons_rate = consistent_pairs / len(pair_map) if pair_map else 0.0

        print(f"  Exact Predicate Match:     {pred_match_res['exact_predicate_match']:.4f}")
        print(f"  Decided Coverage:          {coverage*100:.2f}% (PASS={n_pass}, BLOCK={n_block}, HOLD={n_hold})")
        print(f"  Selective Accuracy:        {selective_acc*100:.2f}% ({sup_pass+con_block}/{decided_count})")
        print(f"  Overall Utility Accuracy:  {overall_utility_acc*100:.2f}% ({sup_pass+con_block}/{n_total})")
        print(f"  UAR (Safety Failure):      {uar*100:.2f}% ({con_pass}/{n_con})")
        print(f"  BABR (Overblocking):       {babr*100:.2f}% ({sup_block}/{n_sup})")
        print(f"  Pair Consistency Rate:     {pair_cons_rate*100:.2f}% ({consistent_pairs}/{len(pair_map)})")

        accounting_rows.append({
            "model": model_name,
            "N_total": n_total,
            "N_supported": n_sup,
            "N_contradicted": n_con,
            "total_PASS": n_pass,
            "total_BLOCK": n_block,
            "total_HOLD": n_hold,
            "supported_PASS": sup_pass,
            "supported_BLOCK": sup_block,
            "supported_HOLD": sup_hold,
            "contradicted_BLOCK": con_block,
            "contradicted_PASS": con_pass,
            "contradicted_HOLD": con_hold,
            "UAR": f"{uar:.4f}",
            "BABR": f"{babr:.4f}",
            "HOLD_rate": f"{hold_rate:.4f}",
            "coverage": f"{coverage:.4f}",
            "selective_accuracy": f"{selective_acc:.4f}",
            "overall_utility_accuracy": f"{overall_utility_acc:.4f}",
            "exact_predicate_match": f"{pred_match_res['exact_predicate_match']:.4f}",
            "pair_consistency_rate": f"{pair_cons_rate:.4f}"
        })

    # Save Accounting CSV
    os.makedirs("reports/phases", exist_ok=True)
    out_csv = "reports/phases/P5_5B_METRIC_ACCOUNTING.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "model", "N_total", "N_supported", "N_contradicted",
            "total_PASS", "total_BLOCK", "total_HOLD",
            "supported_PASS", "supported_BLOCK", "supported_HOLD",
            "contradicted_BLOCK", "contradicted_PASS", "contradicted_HOLD",
            "UAR", "BABR", "HOLD_rate", "coverage",
            "selective_accuracy", "overall_utility_accuracy",
            "exact_predicate_match", "pair_consistency_rate"
        ])
        writer.writeheader()
        for r in accounting_rows:
            writer.writerow(r)

    print(f"\n[SUCCESS] Accounting and evaluation saved to {out_csv}")

if __name__ == "__main__":
    run_p5_5b()
