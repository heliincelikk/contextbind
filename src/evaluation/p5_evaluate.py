"""
ContextBind — Comprehensive Phase P5 Evaluation Engine
Evaluates:
- Semantic Binder Baselines (B_RULE, ML Binder, Hybrid Binder)
- Slot-level & Exact Predicate Match Metrics
- End-to-End Verification Metrics (Verdict Accuracy, UAR, BABR)
- Counterfactual Pair Consistency
- B3 Direct Text Shortcut Baseline
- Error Decomposition
Strictly uses Python Standard Library + scikit-learn / numpy.
"""

import os
import sys
import json
import csv
import time
import hashlib
import pickle
from collections import defaultdict
from typing import Dict, Any, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.binder.rule_binder import RuleBasedClaimBinder
from src.binder.ml_binder import MLClaimBinder
from src.binder.hybrid_binder import HybridClaimBinder
from src.binder.direct_text_classifier import DirectTextClassifier
from src.verification.oracle_temporal_verifier import OracleTemporalVerifier

def load_jsonl(path: str) -> List[Dict[str, Any]]:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records

def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def evaluate_predicates(claims: List[Dict[str, Any]], preds: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Computes slot-level and exact predicate match accuracies.
    """
    n = len(claims)
    if n == 0:
        return {}

    task_match = 0
    claim_type_match = 0
    comp_match = 0
    win_match = 0
    concept_match = 0
    val_match = 0
    val_count = 0
    event_match = 0
    event_count = 0
    exact_match = 0

    for c, p in zip(claims, preds):
        gt_task = c["task_code"]
        gt_pred = c["structured_predicate"]
        
        # 1. Task Match
        m_task = (p["task_type"] == gt_task)
        if m_task:
            task_match += 1

        # 2. Claim Type Match
        m_claim_type = (p["claim_type"] == gt_pred.get("claim_type"))
        if m_claim_type:
            claim_type_match += 1

        # 3. Comparator Match
        gt_comp = gt_pred.get("comparator")
        m_comp = (p["comparator"] == gt_comp)
        if m_comp:
            comp_match += 1

        # 4. Temporal Window Match (for S1)
        gt_win = gt_pred.get("window")
        m_win = (p["temporal_window"] == gt_win)
        if m_win:
            win_match += 1

        # 5. Concept Match (for S1, S3, S4)
        gt_concept = gt_pred.get("concept")
        m_concept = True
        if gt_concept is not None:
            m_concept = (p["clinical_concept"] == gt_concept)
            if m_concept:
                concept_match += 1

        # 6. Numeric Value Match (for S4)
        gt_val = gt_pred.get("claimed_value")
        m_val = True
        if gt_val is not None:
            val_count += 1
            if p["claimed_value"] is not None and abs(p["claimed_value"] - gt_val) < 1e-4:
                val_match += 1
            else:
                m_val = False

        # 7. Event Reference Match (for S2)
        m_event = True
        if gt_task == "S2":
            event_count += 1
            gt_eA = gt_pred.get("event_A_id")
            gt_eB = gt_pred.get("event_B_id")
            if p["event_A_id"] == gt_eA and p["event_B_id"] == gt_eB:
                event_match += 1
            else:
                m_event = False

        # Exact Predicate Match
        if gt_task == "S1":
            is_exact = (m_task and m_claim_type and m_comp and m_win and m_concept)
        elif gt_task == "S2":
            is_exact = (m_task and m_claim_type and m_comp and m_event)
        elif gt_task == "S3":
            is_exact = (m_task and m_claim_type and m_comp and m_concept)
        elif gt_task == "S4":
            is_exact = (m_task and m_claim_type and m_concept and m_val)
        else:
            is_exact = False

        if is_exact:
            exact_match += 1

    concept_total = sum(1 for c in claims if c["structured_predicate"].get("concept") is not None)

    return {
        "task_type_acc": task_match / n,
        "claim_type_acc": claim_type_match / n,
        "comparator_acc": comp_match / n,
        "temporal_window_acc": win_match / n,
        "concept_acc": (concept_match / concept_total) if concept_total > 0 else 1.0,
        "numeric_val_acc": (val_match / val_count) if val_count > 0 else 1.0,
        "event_ref_acc": (event_match / event_count) if event_count > 0 else 1.0,
        "exact_predicate_match": exact_match / n
    }

def run_evaluation():
    print("=" * 70)
    print("CONTEXTBIND — PHASE P5 COMPREHENSIVE BENCHMARK EVALUATION")
    print("=" * 70)

    train_path = "data/processed/p4_final_train.jsonl"
    val_id_path = "data/processed/p4_final_val_id.jsonl"
    val_ood_path = "data/processed/p4_final_val_ood.jsonl"
    db_path = "data/interim/contextbind_timeline.sqlite"

    print("\n[1/6] Loading frozen datasets...")
    train_claims = load_jsonl(train_path)
    val_id_claims = load_jsonl(val_id_path)
    val_ood_claims = load_jsonl(val_ood_path)

    print(f"  Train:   {len(train_claims)} claims")
    print(f"  Val-ID:  {len(val_id_claims)} claims")
    print(f"  Val-OOD: {len(val_ood_claims)} claims")

    # [2/6] Fitting Binders strictly on TRAIN
    print("\n[2/6] Training Semantic Binders on TRAIN partition...")
    t0 = time.time()
    rule_binder = RuleBasedClaimBinder().fit(train_claims)
    ml_binder = MLClaimBinder(seed=20261004).fit(train_claims)
    hybrid_binder = HybridClaimBinder(seed=20261004).fit(train_claims)
    direct_text_clf = DirectTextClassifier(seed=20261004).fit(train_claims)
    train_time = time.time() - t0
    print(f"  Training completed in {train_time:.2f}s")

    # Save trained hybrid model artefact
    os.makedirs("artifacts/p5", exist_ok=True)
    artefact_path = "artifacts/p5/hybrid_claim_binder.pkl"
    with open(artefact_path, "wb") as f:
        pickle.dump(hybrid_binder, f)
    artefact_hash = compute_sha256(artefact_path)
    print(f"  Saved Hybrid Binder Artefact: {artefact_path} (SHA256: {artefact_hash[:16]}...)")

    # [3/6] Evaluating Semantic Binder Parsing
    print("\n[3/6] Evaluating Semantic Predicate Accuracy (Slot & Exact Match)...")
    binder_metrics_rows = []

    models = [
        ("B_RULE", rule_binder),
        ("B_ML", ml_binder),
        ("B_HYBRID", hybrid_binder)
    ]

    # Pre-parse candidate events for S2
    # In timeline, S2 candidate events are the source_event_ids in the claim
    conn = OracleTemporalVerifier(db_path)._connect()
    cursor = conn.cursor()
    cursor.execute("SELECT resource_id, clinical_display FROM timeline_events WHERE is_post_death_event = 0")
    event_display_map = {r[0]: r[1] for r in cursor.fetchall()}
    conn.close()

    parsed_cache = {}

    for model_name, model in models:
        for split_name, val_data in [("VAL-ID", val_id_claims), ("VAL-OOD", val_ood_claims)]:
            # Generate predictions
            preds = []
            for c in val_data:
                cand_events = None
                if c["task_code"] == "S2":
                    cand_events = [{"resource_id": eid, "clinical_display": event_display_map.get(eid, "")} for eid in c.get("source_event_ids", [])]
                pred = model.parse(c["claim_text"], candidate_events=cand_events)
                preds.append(pred)

            parsed_cache[(model_name, split_name)] = preds

            # 1. Overall metrics
            res = evaluate_predicates(val_data, preds)
            binder_metrics_rows.append({
                "model": model_name,
                "split": split_name,
                "task_code": "OVERALL",
                "task_type_acc": f"{res['task_type_acc']:.4f}",
                "claim_type_acc": f"{res['claim_type_acc']:.4f}",
                "comparator_acc": f"{res['comparator_acc']:.4f}",
                "temporal_window_acc": f"{res['temporal_window_acc']:.4f}",
                "concept_acc": f"{res['concept_acc']:.4f}",
                "numeric_val_acc": f"{res['numeric_val_acc']:.4f}",
                "event_ref_acc": f"{res['event_ref_acc']:.4f}",
                "exact_predicate_match": f"{res['exact_predicate_match']:.4f}"
            })

            # 2. Per-task breakdown
            for task in ["S1", "S2", "S3", "S4"]:
                t_claims = [c for c in val_data if c["task_code"] == task]
                t_preds = [p for c, p in zip(val_data, preds) if c["task_code"] == task]
                if t_claims:
                    t_res = evaluate_predicates(t_claims, t_preds)
                    binder_metrics_rows.append({
                        "model": model_name,
                        "split": split_name,
                        "task_code": task,
                        "task_type_acc": f"{t_res['task_type_acc']:.4f}",
                        "claim_type_acc": f"{t_res['claim_type_acc']:.4f}",
                        "comparator_acc": f"{t_res['comparator_acc']:.4f}",
                        "temporal_window_acc": f"{t_res['temporal_window_acc']:.4f}",
                        "concept_acc": f"{t_res['concept_acc']:.4f}",
                        "numeric_val_acc": f"{t_res['numeric_val_acc']:.4f}",
                        "event_ref_acc": f"{t_res['event_ref_acc']:.4f}",
                        "exact_predicate_match": f"{t_res['exact_predicate_match']:.4f}"
                    })

    # Save Binder Metrics CSV
    with open("reports/phases/P5_BINDER_METRICS.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "model", "split", "task_code", "task_type_acc", "claim_type_acc",
            "comparator_acc", "temporal_window_acc", "concept_acc",
            "numeric_val_acc", "event_ref_acc", "exact_predicate_match"
        ])
        writer.writeheader()
        for r in binder_metrics_rows:
            writer.writerow(r)

    # [4/6] End-to-End Verification Evaluation
    print("\n[4/6] Executing End-to-End Verification Pipeline (Binder -> Predicate -> B_ORACLE)...")
    verifier = OracleTemporalVerifier(db_path)
    end_to_end_rows = []
    pair_consistency_rows = []
    error_analysis_rows = []

    all_models = models + [("B3_DIRECT_TEXT", direct_text_clf)]

    for model_name, model in all_models:
        for split_name, val_data in [("VAL-ID", val_id_claims), ("VAL-OOD", val_ood_claims)]:
            # Get verdicts
            if model_name == "B3_DIRECT_TEXT":
                dt_preds = direct_text_clf.predict(val_data)
                verdicts = [p["verdict"] for p in dt_preds]
            else:
                preds = parsed_cache[(model_name, split_name)]
                # Construct simulated claims for Oracle with predicted predicates
                claims_with_preds = []
                for c, p in zip(val_data, preds):
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

            # Compute Verdict Acc, UAR, BABR
            total_claims = len(val_data)
            sup_claims = [i for i, c in enumerate(val_data) if c["ground_truth"] == "SUPPORTED"]
            con_claims = [i for i, c in enumerate(val_data) if c["ground_truth"] == "CONTRADICTED"]

            correct_verdicts = sum(1 for i, c in enumerate(val_data) if (verdicts[i] == "PASS" and c["ground_truth"] == "SUPPORTED") or (verdicts[i] == "BLOCK" and c["ground_truth"] == "CONTRADICTED"))
            verdict_acc = correct_verdicts / total_claims

            # Unsafe Action Release: Contradicted claim incorrectly getting PASS
            unsafe_releases = sum(1 for i in con_claims if verdicts[i] == "PASS")
            uar = unsafe_releases / len(con_claims) if con_claims else 0.0

            # Benign Action Block: Supported claim incorrectly getting BLOCK
            benign_blocks = sum(1 for i in sup_claims if verdicts[i] == "BLOCK")
            babr = benign_blocks / len(sup_claims) if sup_claims else 0.0

            end_to_end_rows.append({
                "model": model_name,
                "split": split_name,
                "task_code": "OVERALL",
                "total_claims": total_claims,
                "verdict_accuracy": f"{verdict_acc:.4f}",
                "uar": f"{uar:.4f}",
                "babr": f"{babr:.4f}"
            })

            # Per-task End-to-End
            for task in ["S1", "S2", "S3", "S4"]:
                t_idxs = [i for i, c in enumerate(val_data) if c["task_code"] == task]
                t_sup = [i for i in t_idxs if val_data[i]["ground_truth"] == "SUPPORTED"]
                t_con = [i for i in t_idxs if val_data[i]["ground_truth"] == "CONTRADICTED"]

                t_correct = sum(1 for i in t_idxs if (verdicts[i] == "PASS" and val_data[i]["ground_truth"] == "SUPPORTED") or (verdicts[i] == "BLOCK" and val_data[i]["ground_truth"] == "CONTRADICTED"))
                t_acc = t_correct / len(t_idxs) if t_idxs else 0.0
                t_uar = sum(1 for i in t_con if verdicts[i] == "PASS") / len(t_con) if t_con else 0.0
                t_babr = sum(1 for i in t_sup if verdicts[i] == "BLOCK") / len(t_sup) if t_sup else 0.0

                end_to_end_rows.append({
                    "model": model_name,
                    "split": split_name,
                    "task_code": task,
                    "total_claims": len(t_idxs),
                    "verdict_accuracy": f"{t_acc:.4f}",
                    "uar": f"{t_uar:.4f}",
                    "babr": f"{t_babr:.4f}"
                })

            # Counterfactual Pair Consistency
            # Group claims by pair_id
            pair_map = defaultdict(list)
            for i, c in enumerate(val_data):
                pair_map[c["pair_id"]].append((c, verdicts[i]))

            consistent_pairs = 0
            s1_consistent_pairs = 0
            s1_total_pairs = 0

            for pid, p_list in pair_map.items():
                if len(p_list) == 2:
                    is_s1 = (p_list[0][0]["task_code"] == "S1")
                    if is_s1:
                        s1_total_pairs += 1

                    both_correct = all((v == "PASS" and c["ground_truth"] == "SUPPORTED") or (v == "BLOCK" and c["ground_truth"] == "CONTRADICTED") for c, v in p_list)
                    if both_correct:
                        consistent_pairs += 1
                        if is_s1:
                            s1_consistent_pairs += 1

            total_pairs = len(pair_map)
            pair_cons_rate = consistent_pairs / total_pairs if total_pairs > 0 else 0.0
            s1_cons_rate = s1_consistent_pairs / s1_total_pairs if s1_total_pairs > 0 else 0.0

            pair_consistency_rows.append({
                "model": model_name,
                "split": split_name,
                "total_pairs": total_pairs,
                "consistent_pairs": consistent_pairs,
                "pair_consistency_rate": f"{pair_cons_rate:.4f}",
                "s1_total_pairs": s1_total_pairs,
                "s1_consistent_pairs": s1_consistent_pairs,
                "s1_pair_consistency_rate": f"{s1_cons_rate:.4f}"
            })

            # Error Decomposition (for Hybrid model)
            if model_name == "B_HYBRID":
                for i, c in enumerate(val_data):
                    v = verdicts[i]
                    gt = c["ground_truth"]
                    is_correct = (v == "PASS" and gt == "SUPPORTED") or (v == "BLOCK" and gt == "CONTRADICTED")
                    if not is_correct:
                        pred_p = preds[i]
                        gt_p = c["structured_predicate"]
                        err_category = "other"

                        if pred_p["clinical_concept"] != gt_p.get("concept"):
                            err_category = "concept_extraction"
                        elif pred_p["claim_type"] != gt_p.get("claim_type") or pred_p["comparator"] != gt_p.get("comparator"):
                            err_category = "relation_extraction"
                        elif pred_p["temporal_window"] != gt_p.get("window"):
                            err_category = "temporal_anchor"
                        elif gt_p.get("claimed_value") is not None and (pred_p["claimed_value"] is None or abs(pred_p["claimed_value"] - gt_p["claimed_value"]) > 1e-4):
                            err_category = "numeric_value"
                        elif c["task_code"] == "S2" and (pred_p["event_A_id"] != gt_p.get("event_A_id") or pred_p["event_B_id"] != gt_p.get("event_B_id")):
                            err_category = "event_linking"
                        else:
                            err_category = "verifier_inference"

                        error_analysis_rows.append({
                            "split": split_name,
                            "task_code": c["task_code"],
                            "pair_id": c["pair_id"],
                            "claim_text": c["claim_text"],
                            "ground_truth": gt,
                            "predicted_verdict": v,
                            "error_category": err_category
                        })

    # Save End-to-End CSV
    with open("reports/phases/P5_END_TO_END.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["model", "split", "task_code", "total_claims", "verdict_accuracy", "uar", "babr"])
        writer.writeheader()
        for r in end_to_end_rows:
            writer.writerow(r)

    # Save Pair Consistency CSV
    with open("reports/phases/P5_PAIR_CONSISTENCY.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["model", "split", "total_pairs", "consistent_pairs", "pair_consistency_rate", "s1_total_pairs", "s1_consistent_pairs", "s1_pair_consistency_rate"])
        writer.writeheader()
        for r in pair_consistency_rows:
            writer.writerow(r)

    # Save Error Analysis CSV
    with open("reports/phases/P5_ERROR_ANALYSIS.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["split", "task_code", "pair_id", "claim_text", "ground_truth", "predicted_verdict", "error_category"])
        writer.writeheader()
        for r in error_analysis_rows:
            writer.writerow(r)

    print("\n[SUCCESS] Phase P5 Evaluation Pipeline completed.")

if __name__ == "__main__":
    run_evaluation()
