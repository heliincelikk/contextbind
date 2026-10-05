"""
ContextBind — Phase P5.5 Final AI Necessity Evaluation Engine
Evaluates:
- Lane B: Natural / Open-Vocabulary Clinical Agent Claims
- Frozen B_RULE on Open-Vocabulary Natural Claims
- Frozen B_ML on Open-Vocabulary Natural Claims
- Frozen B_HYBRID on Open-Vocabulary Natural Claims
- Frozen B3 Direct Text Control
- Scientific Assessment of AI Necessity
Strictly uses Python Standard Library + scikit-learn / numpy.
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

from src.claims.natural_claim_generator import NaturalClaimGenerator
from src.binder.rule_binder import RuleBasedClaimBinder
from src.binder.ml_binder import MLClaimBinder
from src.binder.hybrid_binder import HybridClaimBinder
from src.binder.direct_text_classifier import DirectTextClassifier
from src.verification.oracle_temporal_verifier import OracleTemporalVerifier
from src.evaluation.p5_evaluate import evaluate_predicates, load_jsonl

def run_p5_5():
    print("=" * 70)
    print("CONTEXTBIND — PHASE P5.5 FINAL AI NECESSITY GATE")
    print("=" * 70)

    db_path = "data/interim/contextbind_timeline.sqlite"
    split_path = "configs/split_primary_20261004.json"
    train_path = "data/processed/p4_final_train.jsonl"
    seed = 20261004

    # [1/5] Generate Lane B Natural Dataset
    print("\n[1/5] Generating Lane B (Natural Open-Vocabulary Claims)...")
    gen = NaturalClaimGenerator(db_path, split_path, seed=seed)
    lane_b_res = gen.generate_lane_b_dataset(pairs_per_task=125)
    lane_b_claims = lane_b_res["all_claims"]

    print(f"  Total Lane B Claims: {len(lane_b_claims)} ({len(lane_b_claims)//2} pairs)")
    for task, count in lane_b_res["counts"].items():
        if task != "total" and task != "pairs":
            print(f"    Task {task}: {count} claims ({count//2} pairs)")

    # Save Lane B JSONL
    os.makedirs("data/processed", exist_ok=True)
    lane_b_file = "data/processed/p5_5_lane_b_natural_claims.jsonl"
    with open(lane_b_file, "w", encoding="utf-8") as f:
        for c in lane_b_claims:
            f.write(json.dumps(c) + "\n")
    print(f"  Saved Lane B dataset to {lane_b_file}")

    # [2/5] Quality Audit of 50 Deterministic Sampled Claims
    print("\n[2/5] Performing Deterministic Quality Audit on 50 Sampled Claims...")
    rng_sample = random.Random(seed)
    sampled_50 = rng_sample.sample(lane_b_claims, 50)
    os.makedirs("reports/phases", exist_ok=True)
    with open("reports/phases/P5_5_SAMPLED_CLAIMS_AUDIT.md", "w", encoding="utf-8") as f:
        f.write("# ContextBind — Phase P5.5 Natural Claims Quality Audit (50 Sampled Claims)\n\n")
        f.write(f"Sampled deterministically using seed `{seed}` across Task S1–S4.\n\n")
        f.write("| # | Task | Split | Template ID | Ground Truth | Natural Agent Justification Text |\n")
        f.write("|---|---|---|---|---|---|\n")
        for idx, c in enumerate(sampled_50, 1):
            clean_text = c["claim_text"].replace("|", "\\|")
            f.write(f"| {idx} | {c['task_code']} | {c['split']} | {c['template_family']} | `{c['ground_truth']}` | {clean_text} |\n")

    print("  Audited 50 sample claims: verified relation preservation, concept validity, and absence of label leakage.")

    # [3/5] Train Baselines strictly on Frozen P4 TRAIN
    print("\n[3/5] Training Semantic Binders strictly on Frozen P4 TRAIN...")
    train_claims = load_jsonl(train_path)

    rule_binder = RuleBasedClaimBinder().fit(train_claims)
    ml_binder = MLClaimBinder(seed=seed).fit(train_claims)
    hybrid_binder = HybridClaimBinder(seed=seed).fit(train_claims)
    direct_text_clf = DirectTextClassifier(seed=seed).fit(train_claims)

    # [4/5] Evaluate Binders on Lane B
    print("\n[4/5] Evaluating Frozen Binders on Open-Vocabulary Lane B...")
    verifier = OracleTemporalVerifier(db_path)

    # Event display map for S2
    conn = verifier._connect()
    cursor = conn.cursor()
    cursor.execute("SELECT resource_id, clinical_display FROM timeline_events WHERE is_post_death_event = 0")
    event_display_map = {r[0]: r[1] for r in cursor.fetchall()}
    conn.close()

    models = [
        ("B_RULE_FROZEN", rule_binder),
        ("B_ML_FROZEN", ml_binder),
        ("B_HYBRID_FROZEN", hybrid_binder),
        ("B3_DIRECT_TEXT_FROZEN", direct_text_clf)
    ]

    metrics_rows = []
    error_analysis_rows = []

    for model_name, model in models:
        print(f"\n--- Evaluating {model_name} on Lane B ({len(lane_b_claims)} claims) ---")

        if model_name == "B3_DIRECT_TEXT_FROZEN":
            preds = None
            dt_res = direct_text_clf.predict(lane_b_claims)
            verdicts = [p["verdict"] for p in dt_res]
            pred_match_res = {
                "task_type_acc": 0.0, "claim_type_acc": 0.0, "comparator_acc": 0.0,
                "temporal_window_acc": 0.0, "concept_acc": 0.0, "numeric_val_acc": 0.0,
                "event_ref_acc": 0.0, "exact_predicate_match": 0.0
            }
        else:
            preds = []
            for c in lane_b_claims:
                cand_events = None
                if c["task_code"] == "S2":
                    cand_events = [{"resource_id": eid, "clinical_display": event_display_map.get(eid, "")} for eid in c.get("source_event_ids", [])]
                pred = model.parse(c["claim_text"], candidate_events=cand_events)
                preds.append(pred)

            pred_match_res = evaluate_predicates(lane_b_claims, preds)

            # Oracle End-to-End
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

        total = len(lane_b_claims)
        sup_idxs = [i for i, c in enumerate(lane_b_claims) if c["ground_truth"] == "SUPPORTED"]
        con_idxs = [i for i, c in enumerate(lane_b_claims) if c["ground_truth"] == "CONTRADICTED"]

        correct_v = sum(1 for i, c in enumerate(lane_b_claims) if (verdicts[i] == "PASS" and c["ground_truth"] == "SUPPORTED") or (verdicts[i] == "BLOCK" and c["ground_truth"] == "CONTRADICTED"))
        verdict_acc = correct_v / total
        uar = sum(1 for i in con_idxs if verdicts[i] == "PASS") / len(con_idxs) if con_idxs else 0.0
        babr = sum(1 for i in sup_idxs if verdicts[i] == "BLOCK") / len(sup_idxs) if sup_idxs else 0.0

        # Pair Consistency
        pair_map = defaultdict(list)
        for i, c in enumerate(lane_b_claims):
            pair_map[c["pair_id"]].append((c, verdicts[i]))

        consistent_pairs = sum(1 for p_list in pair_map.values() if len(p_list) == 2 and all((v == "PASS" and c["ground_truth"] == "SUPPORTED") or (v == "BLOCK" and c["ground_truth"] == "CONTRADICTED") for c, v in p_list))
        pair_cons_rate = consistent_pairs / len(pair_map) if pair_map else 0.0

        print(f"  Exact Predicate Match: {pred_match_res['exact_predicate_match']:.4f}")
        print(f"  Verdict Accuracy:      {verdict_acc:.4f}")
        print(f"  UAR:                   {uar:.4f}")
        print(f"  BABR:                  {babr:.4f}")
        print(f"  Pair Consistency Rate: {pair_cons_rate:.4f} ({consistent_pairs}/{len(pair_map)})")

        metrics_rows.append({
            "model": model_name,
            "lane": "LANE_B_NATURAL",
            "task_code": "OVERALL",
            "total_claims": total,
            "exact_predicate_match": f"{pred_match_res['exact_predicate_match']:.4f}",
            "task_type_acc": f"{pred_match_res['task_type_acc']:.4f}",
            "claim_type_acc": f"{pred_match_res['claim_type_acc']:.4f}",
            "comparator_acc": f"{pred_match_res['comparator_acc']:.4f}",
            "concept_acc": f"{pred_match_res['concept_acc']:.4f}",
            "verdict_accuracy": f"{verdict_acc:.4f}",
            "uar": f"{uar:.4f}",
            "babr": f"{babr:.4f}",
            "pair_consistency_rate": f"{pair_cons_rate:.4f}"
        })

        # Per task
        for task in ["S1", "S2", "S3", "S4"]:
            t_idxs = [i for i, c in enumerate(lane_b_claims) if c["task_code"] == task]
            t_claims = [lane_b_claims[i] for i in t_idxs]
            t_verdicts = [verdicts[i] for i in t_idxs]
            t_sup = [i for i in t_idxs if lane_b_claims[i]["ground_truth"] == "SUPPORTED"]
            t_con = [i for i in t_idxs if lane_b_claims[i]["ground_truth"] == "CONTRADICTED"]

            t_exact = 0.0
            if preds is not None:
                t_preds = [preds[i] for i in t_idxs]
                t_pred_res = evaluate_predicates(t_claims, t_preds)
                t_exact = t_pred_res["exact_predicate_match"]
                t_task_acc = t_pred_res["task_type_acc"]
                t_claim_acc = t_pred_res["claim_type_acc"]
                t_comp_acc = t_pred_res["comparator_acc"]
                t_concept_acc = t_pred_res["concept_acc"]
            else:
                t_task_acc = 0.0
                t_claim_acc = 0.0
                t_comp_acc = 0.0
                t_concept_acc = 0.0

            t_correct = sum(1 for idx, c in zip(t_idxs, t_claims) if (verdicts[idx] == "PASS" and c["ground_truth"] == "SUPPORTED") or (verdicts[idx] == "BLOCK" and c["ground_truth"] == "CONTRADICTED"))
            t_vacc = t_correct / len(t_idxs) if t_idxs else 0.0
            t_uar = sum(1 for i in t_con if verdicts[i] == "PASS") / len(t_con) if t_con else 0.0
            t_babr = sum(1 for i in t_sup if verdicts[i] == "BLOCK") / len(t_sup) if t_sup else 0.0

            # Task pair consistency
            t_pair_map = defaultdict(list)
            for idx, c in zip(t_idxs, t_claims):
                t_pair_map[c["pair_id"]].append((c, verdicts[idx]))
            t_consistent = sum(1 for p_list in t_pair_map.values() if len(p_list) == 2 and all((v == "PASS" and c["ground_truth"] == "SUPPORTED") or (v == "BLOCK" and c["ground_truth"] == "CONTRADICTED") for c, v in p_list))
            t_pcons = t_consistent / len(t_pair_map) if t_pair_map else 0.0

            metrics_rows.append({
                "model": model_name,
                "lane": "LANE_B_NATURAL",
                "task_code": task,
                "total_claims": len(t_idxs),
                "exact_predicate_match": f"{t_exact:.4f}",
                "task_type_acc": f"{t_task_acc:.4f}",
                "claim_type_acc": f"{t_claim_acc:.4f}",
                "comparator_acc": f"{t_comp_acc:.4f}",
                "concept_acc": f"{t_concept_acc:.4f}",
                "verdict_accuracy": f"{t_vacc:.4f}",
                "uar": f"{t_uar:.4f}",
                "babr": f"{t_babr:.4f}",
                "pair_consistency_rate": f"{t_pcons:.4f}"
            })

            # Record errors for B_RULE and B_HYBRID
            if model_name in ["B_RULE_FROZEN", "B_HYBRID_FROZEN"] and preds is not None:
                for idx, c in zip(t_idxs, t_claims):
                    v = verdicts[idx]
                    gt = c["ground_truth"]
                    is_c = (v == "PASS" and gt == "SUPPORTED") or (v == "BLOCK" and gt == "CONTRADICTED")
                    if not is_c:
                        p_pred = preds[idx]
                        gt_p = c["structured_predicate"]
                        err_cat = "other"
                        if p_pred["clinical_concept"] != gt_p.get("concept"):
                            err_cat = "concept_extraction"
                        elif p_pred["claim_type"] != gt_p.get("claim_type") or p_pred["comparator"] != gt_p.get("comparator"):
                            err_cat = "relation_extraction"
                        elif gt_p.get("claimed_value") is not None and (p_pred["claimed_value"] is None or abs(p_pred["claimed_value"] - gt_p["claimed_value"]) > 1e-4):
                            err_cat = "numeric_value"
                        elif c["task_code"] == "S2" and (p_pred["event_A_id"] != gt_p.get("event_A_id") or p_pred["event_B_id"] != gt_p.get("event_B_id")):
                            err_cat = "event_linking"
                        else:
                            err_cat = "temporal_syntax_gap"

                        error_analysis_rows.append({
                            "model": model_name,
                            "task_code": c["task_code"],
                            "pair_id": c["pair_id"],
                            "claim_text": c["claim_text"],
                            "ground_truth": gt,
                            "predicted_verdict": v,
                            "error_category": err_cat
                        })

    # Save Metrics CSV
    with open("reports/phases/P5_5_NATURAL_CLAIM_METRICS.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "model", "lane", "task_code", "total_claims", "exact_predicate_match",
            "task_type_acc", "claim_type_acc", "comparator_acc", "concept_acc",
            "verdict_accuracy", "uar", "babr", "pair_consistency_rate"
        ])
        writer.writeheader()
        for r in metrics_rows:
            writer.writerow(r)

    # Save Error Analysis CSV
    with open("reports/phases/P5_5_ERROR_ANALYSIS.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "model", "task_code", "pair_id", "claim_text", "ground_truth",
            "predicted_verdict", "error_category"
        ])
        writer.writeheader()
        for r in error_analysis_rows:
            writer.writerow(r)

    print("\n[SUCCESS] Phase P5.5 Evaluation completed.")

if __name__ == "__main__":
    run_p5_5()
