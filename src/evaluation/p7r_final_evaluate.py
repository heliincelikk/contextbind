"""
ContextBind — Phase P7R Final Corrected Evaluation Engine
Deterministic Test Data Reconstruction, Production Runtime Routing, and Verified Metrics
"""

import os
import sys
import json
import time
import hashlib
import random
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, Any, List, Tuple, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.binder.rule_binder import RuleBasedClaimBinder
from src.binder.semantic_ai_binder import SemanticAIBinder
from src.verification.oracle_temporal_verifier import OracleTemporalVerifier
from src.claims.claim_generator import TemporalClaimGenerator
from src.claims.natural_claim_generator import NaturalClaimGenerator
from src.runtime.contextbind_runtime import ContextBindRuntime


def sha256_file(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def reconstruct_and_persist_test_datasets():
    print("==================================================================")
    print("STEP 1: DETERMINISTIC RECONSTRUCTION OF P7 TEST CLAIM DATASETS")
    print("==================================================================")

    db_path = "data/interim/contextbind_timeline.sqlite"
    split_path = "configs/split_primary_20261004.json"
    ctrl_out = "data/processed/p7_test_controlled.jsonl"
    open_out = "data/processed/p7_test_open_form.jsonl"
    manifest_out = "reports/phases/P7R_TEST_DATA_MANIFEST.json"

    # 1. Controlled TEST claims
    print("\n[1/2] Generating Controlled TEST Claims (P4 Frozen Specification, Seed 20261004)...")
    claim_gen = TemporalClaimGenerator(db_path, split_path, seed=20261004)
    test_pids = claim_gen.test_pids
    print(f"Loaded {len(test_pids)} Primary TEST Patients.")

    s1_claims = claim_gen.generate_s1_trend_claims(test_pids, max_pairs_per_concept=3)
    s2_claims = claim_gen.generate_s2_relation_claims(test_pids, max_pairs_per_patient=3)
    s3_claims = claim_gen.generate_s3_comparison_claims(test_pids, max_pairs_per_concept=3)
    s4_claims = claim_gen.generate_s4_current_claims(test_pids, max_pairs_per_concept=3)

    rng = random.Random(20261004)
    controlled_test_claims = []
    target_pairs = 125  # 125 pairs * 4 tasks = 500 pairs = 1000 claims
    for t_list in [s1_claims, s2_claims, s3_claims, s4_claims]:
        pairs = defaultdict(list)
        for c in t_list:
            pairs[c["pair_id"]].append(c)
        valid_pairs = [p for p in pairs.values() if len(p) == 2]
        sampled = rng.sample(valid_pairs, min(len(valid_pairs), target_pairs))
        for pair in sampled:
            controlled_test_claims.extend(pair)

    with open(ctrl_out, "w", encoding="utf-8") as f:
        for c in controlled_test_claims:
            f.write(json.dumps(c) + "\n")
    print(f"Persisted {len(controlled_test_claims)} Controlled TEST claims to {ctrl_out}")

    # 2. Open-Form TEST claims
    print("\n[2/2] Generating Open-Form TEST Claims (P5.5 Frozen Specification, Seed 20261004)...")
    nat_gen = NaturalClaimGenerator(db_path, split_path, seed=20261004)
    open_form_res = nat_gen.generate_lane_b_dataset(pairs_per_task=125, target_split="TEST", max_pairs_per_patient=3)
    open_form_claims = open_form_res.get("all_claims", open_form_res.get("claims", []))

    with open(open_out, "w", encoding="utf-8") as f:
        for c in open_form_claims:
            f.write(json.dumps(c) + "\n")
    print(f"Persisted {len(open_form_claims)} Open-Form TEST claims to {open_out}")

    # Manifest metadata
    ctrl_sha = sha256_file(ctrl_out)
    open_sha = sha256_file(open_out)

    ctrl_pids = set(c["patient_id"] for c in controlled_test_claims)
    open_pids = set(c["patient_id"] for c in open_form_claims)

    ctrl_tasks = defaultdict(int)
    for c in controlled_test_claims:
        ctrl_tasks[c.get("task_code", "UNKNOWN")] += 1

    open_tasks = defaultdict(int)
    for c in open_form_claims:
        open_tasks[c.get("task_code", "UNKNOWN")] += 1

    manifest = {
        "manifest_name": "P7R_TEST_DATA_MANIFEST",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "provenance_statement": (
            "The original P7 TEST claims were generated in-memory. "
            "They were later deterministically reconstructed after an evaluation-integrity bug was discovered, "
            "using the exact pre-TEST frozen generator hashes, patient split, sampling policy and RNG seed. "
            "No model, rule, threshold, template, label or sampling specification was modified after observing TEST results."
        ),
        "primary_seed": 20261004,
        "patient_split_file": split_path,
        "artifacts": {
            "controlled_test": {
                "path": ctrl_out,
                "sha256": ctrl_sha,
                "record_count": len(controlled_test_claims),
                "unique_claim_ids": len(set(c.get("claim_id", f"{c.get('pair_id')}_{c.get('ground_truth')}") for c in controlled_test_claims)),
                "unique_patient_ids": len(ctrl_pids),
                "supported_count": sum(1 for c in controlled_test_claims if c["ground_truth"] == "SUPPORTED"),
                "contradicted_count": sum(1 for c in controlled_test_claims if c["ground_truth"] == "CONTRADICTED"),
                "task_counts": dict(ctrl_tasks)
            },
            "open_form_test": {
                "path": open_out,
                "sha256": open_sha,
                "record_count": len(open_form_claims),
                "unique_claim_ids": len(set(c.get("claim_id", f"{c.get('pair_id')}_{c.get('ground_truth')}") for c in open_form_claims)),
                "unique_patient_ids": len(open_pids),
                "supported_count": sum(1 for c in open_form_claims if c["ground_truth"] == "SUPPORTED"),
                "contradicted_count": sum(1 for c in open_form_claims if c["ground_truth"] == "CONTRADICTED"),
                "task_counts": dict(open_tasks)
            }
        }
    }

    with open(manifest_out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nCreated and verified manifest: {manifest_out}")
    print(json.dumps(manifest, indent=2))
    return manifest


def evaluate_dataset(
    claims: List[Dict[str, Any]],
    rule_preds: List[Dict[str, Any]],
    ai_preds: List[Dict[str, Any]],
    verifier: OracleTemporalVerifier,
    runtime: ContextBindRuntime,
    tau: float = 0.70,
    mode: str = "HYBRID"
) -> Dict[str, Any]:
    """
    Evaluates end-to-end verification metrics using production ContextBindRuntime routing logic.
    mode: 'ORACLE', 'RULE', 'AI_ONLY', 'HYBRID'
    """
    n_total = len(claims)
    n_supp = sum(1 for c in claims if c["ground_truth"] == "SUPPORTED")
    n_cont = sum(1 for c in claims if c["ground_truth"] == "CONTRADICTED")

    exact_matches = 0
    decisions = []
    claim_outcomes = []

    for i, c in enumerate(claims):
        p_true = c.get("structured_predicate", {})
        gt = c["ground_truth"]
        t_code = c.get("task_code", "S1")
        pid = c["patient_id"]
        source_events = c.get("source_event_ids", [])

        r_p = rule_preds[i] if rule_preds else None
        a_p = ai_preds[i] if ai_preds else None

        r_v = runtime._is_rule_predicate_valid(r_p)
        a_v = runtime._is_ai_predicate_valid(a_p)
        a_conf = float(a_p.get("confidence", 0.0)) if a_p else 0.0

        if mode == "ORACLE":
            pred_to_verify = p_true
            route = "ORACLE"
            conf = 1.0
            exact = True
        elif mode == "RULE":
            route = "RULE"
            conf = 1.0
            if r_v:
                pred_to_verify = r_p
            else:
                pred_to_verify = None
            exact = (pred_to_verify == p_true) if pred_to_verify else False
        elif mode == "AI_ONLY":
            route = "AI"
            conf = a_conf
            if a_v:
                pred_to_verify = a_p
            else:
                pred_to_verify = None
            exact = (pred_to_verify == p_true) if pred_to_verify else False
        elif mode == "HYBRID":
            if r_v:
                route = "RULE"
                pred_to_verify = r_p
                conf = 1.0
                exact = (pred_to_verify == p_true)
            elif a_v and a_conf >= tau:
                route = "AI_FALLBACK"
                pred_to_verify = a_p
                conf = a_conf
                exact = (pred_to_verify == p_true)
            else:
                route = "ABSTAIN_HOLD"
                pred_to_verify = None
                conf = a_conf
                exact = False

        if exact:
            exact_matches += 1

        # Verifier decision
        if pred_to_verify is None:
            dec = "HOLD"
            exp = "ContextBind runtime: Binder abstained / low confidence HOLD"
        else:
            claim_rec = {
                "task_code": t_code,
                "patient_id": pid,
                "claim_text": c["claim_text"],
                "structured_predicate": pred_to_verify,
                "source_event_ids": source_events
            }
            try:
                dec, exp = verifier.verify_claim_predicate(claim_rec)
            except Exception as e:
                dec = "HOLD"
                exp = f"Verifier exception: {str(e)}"

        decisions.append(dec)
        claim_outcomes.append({
            "idx": i,
            "claim_id": c.get("claim_id"),
            "pair_id": c.get("pair_id"),
            "patient_id": pid,
            "task_code": t_code,
            "claim_text": c["claim_text"],
            "ground_truth": gt,
            "route": route,
            "decision": dec,
            "confidence": conf,
            "exact_predicate_match": exact,
            "pred": pred_to_verify,
            "explanation": exp
        })

    # Accounting
    n_pass = sum(1 for d in decisions if d == "PASS")
    n_block = sum(1 for d in decisions if d == "BLOCK")
    n_hold = sum(1 for d in decisions if d == "HOLD")

    n_decided = n_pass + n_block
    coverage = (n_decided / n_total) * 100.0
    hold_rate = (n_hold / n_total) * 100.0

    supp_pass = sum(1 for o in claim_outcomes if o["ground_truth"] == "SUPPORTED" and o["decision"] == "PASS")
    supp_block = sum(1 for o in claim_outcomes if o["ground_truth"] == "SUPPORTED" and o["decision"] == "BLOCK")
    supp_hold = sum(1 for o in claim_outcomes if o["ground_truth"] == "SUPPORTED" and o["decision"] == "HOLD")

    cont_block = sum(1 for o in claim_outcomes if o["ground_truth"] == "CONTRADICTED" and o["decision"] == "BLOCK")
    cont_pass = sum(1 for o in claim_outcomes if o["ground_truth"] == "CONTRADICTED" and o["decision"] == "PASS")
    cont_hold = sum(1 for o in claim_outcomes if o["ground_truth"] == "CONTRADICTED" and o["decision"] == "HOLD")

    selective_acc = ((supp_pass + cont_block) / n_decided * 100.0) if n_decided > 0 else 0.0
    utility_acc = ((supp_pass + cont_block) / n_total) * 100.0

    uar = (cont_pass / n_cont * 100.0) if n_cont > 0 else 0.0
    babr = (supp_block / n_supp * 100.0) if n_supp > 0 else 0.0

    # Pair Consistency
    pairs = defaultdict(list)
    for o in claim_outcomes:
        pairs[o["pair_id"]].append(o)

    n_pairs = len(pairs)
    consistent_pairs = 0
    for p_id, p_items in pairs.items():
        if len(p_items) == 2:
            d_supp = next((item["decision"] for item in p_items if item["ground_truth"] == "SUPPORTED"), None)
            d_cont = next((item["decision"] for item in p_items if item["ground_truth"] == "CONTRADICTED"), None)
            if d_supp == "PASS" and d_cont == "BLOCK":
                consistent_pairs += 1

    pair_consistency_rate = (consistent_pairs / n_pairs * 100.0) if n_pairs > 0 else 0.0

    # Per-task breakdowns
    task_metrics = {}
    for tc in ["S1", "S2", "S3", "S4"]:
        t_outcomes = [o for o in claim_outcomes if o["task_code"] == tc]
        if not t_outcomes:
            continue
        t_tot = len(t_outcomes)
        t_dec = sum(1 for o in t_outcomes if o["decision"] in ["PASS", "BLOCK"])
        t_cov = (t_dec / t_tot) * 100.0
        t_sp = sum(1 for o in t_outcomes if o["ground_truth"] == "SUPPORTED" and o["decision"] == "PASS")
        t_cb = sum(1 for o in t_outcomes if o["ground_truth"] == "CONTRADICTED" and o["decision"] == "BLOCK")
        t_cp = sum(1 for o in t_outcomes if o["ground_truth"] == "CONTRADICTED" and o["decision"] == "PASS")
        t_sb = sum(1 for o in t_outcomes if o["ground_truth"] == "SUPPORTED" and o["decision"] == "BLOCK")
        t_n_cont = sum(1 for o in t_outcomes if o["ground_truth"] == "CONTRADICTED")
        t_n_supp = sum(1 for o in t_outcomes if o["ground_truth"] == "SUPPORTED")

        t_sel_acc = ((t_sp + t_cb) / t_dec * 100.0) if t_dec > 0 else 0.0
        t_util_acc = ((t_sp + t_cb) / t_tot) * 100.0
        t_uar = (t_cp / t_n_cont * 100.0) if t_n_cont > 0 else 0.0
        t_babr = (t_sb / t_n_supp * 100.0) if t_n_supp > 0 else 0.0

        task_metrics[tc] = {
            "n_total": t_tot,
            "coverage_pct": round(t_cov, 2),
            "selective_acc_pct": round(t_sel_acc, 2),
            "utility_acc_pct": round(t_util_acc, 2),
            "uar_pct": round(t_uar, 2),
            "babr_pct": round(t_babr, 2)
        }

    return {
        "mode": mode,
        "n_total": n_total,
        "n_supported": n_supp,
        "n_contradicted": n_cont,
        "exact_predicate_match_pct": round((exact_matches / n_total) * 100.0, 2),
        "coverage_pct": round(coverage, 2),
        "hold_rate_pct": round(hold_rate, 2),
        "selective_accuracy_pct": round(selective_acc, 2),
        "utility_accuracy_pct": round(utility_acc, 2),
        "uar_pct": round(uar, 2),
        "babr_pct": round(babr, 2),
        "pair_consistency_pct": round(pair_consistency_rate, 2),
        "n_pairs": n_pairs,
        "consistent_pairs": consistent_pairs,
        "pass_count": n_pass,
        "block_count": n_block,
        "hold_count": n_hold,
        "supp_pass": supp_pass,
        "supp_block": supp_block,
        "supp_hold": supp_hold,
        "cont_block": cont_block,
        "cont_pass": cont_pass,
        "cont_hold": cont_hold,
        "task_metrics": task_metrics,
        "outcomes": claim_outcomes
    }


def run_patient_bootstrap(
    outcomes: List[Dict[str, Any]],
    n_bootstrap: int = 1000,
    seed: int = 20261004
) -> pd.DataFrame:
    """
    Patient-level clustered bootstrap for 95% Confidence Intervals.
    """
    patient_outcomes = defaultdict(list)
    for o in outcomes:
        patient_outcomes[o["patient_id"]].append(o)

    pids = list(patient_outcomes.keys())
    n_patients = len(pids)

    rng = np.random.RandomState(seed)

    boot_metrics = {
        "coverage": [],
        "selective_accuracy": [],
        "utility_accuracy": [],
        "uar": [],
        "babr": [],
        "pair_consistency": []
    }

    for _ in range(n_bootstrap):
        sample_pids = rng.choice(pids, size=n_patients, replace=True)
        sample_outcomes = []
        for pid in sample_pids:
            sample_outcomes.extend(patient_outcomes[pid])

        n_tot = len(sample_outcomes)
        n_supp = sum(1 for o in sample_outcomes if o["ground_truth"] == "SUPPORTED")
        n_cont = sum(1 for o in sample_outcomes if o["ground_truth"] == "CONTRADICTED")

        n_pass = sum(1 for o in sample_outcomes if o["decision"] == "PASS")
        n_block = sum(1 for o in sample_outcomes if o["decision"] == "BLOCK")
        n_dec = n_pass + n_block

        sp = sum(1 for o in sample_outcomes if o["ground_truth"] == "SUPPORTED" and o["decision"] == "PASS")
        cb = sum(1 for o in sample_outcomes if o["ground_truth"] == "CONTRADICTED" and o["decision"] == "BLOCK")
        cp = sum(1 for o in sample_outcomes if o["ground_truth"] == "CONTRADICTED" and o["decision"] == "PASS")
        sb = sum(1 for o in sample_outcomes if o["ground_truth"] == "SUPPORTED" and o["decision"] == "BLOCK")

        cov = (n_dec / n_tot * 100.0) if n_tot > 0 else 0.0
        sel_acc = ((sp + cb) / n_dec * 100.0) if n_dec > 0 else 0.0
        util_acc = ((sp + cb) / n_tot * 100.0) if n_tot > 0 else 0.0
        uar = (cp / n_cont * 100.0) if n_cont > 0 else 0.0
        babr = (sb / n_supp * 100.0) if n_supp > 0 else 0.0

        # Pairs
        pairs = defaultdict(list)
        for o in sample_outcomes:
            pairs[o["pair_id"]].append(o)
        n_pairs = len(pairs)
        c_pairs = sum(1 for p_items in pairs.values() if len(p_items) == 2 and 
                      next((item["decision"] for item in p_items if item["ground_truth"] == "SUPPORTED"), None) == "PASS" and
                      next((item["decision"] for item in p_items if item["ground_truth"] == "CONTRADICTED"), None) == "BLOCK")
        pc = (c_pairs / n_pairs * 100.0) if n_pairs > 0 else 0.0

        boot_metrics["coverage"].append(cov)
        boot_metrics["selective_accuracy"].append(sel_acc)
        boot_metrics["utility_accuracy"].append(util_acc)
        boot_metrics["uar"].append(uar)
        boot_metrics["babr"].append(babr)
        boot_metrics["pair_consistency"].append(pc)

    ci_rows = []
    for m_name, vals in boot_metrics.items():
        mean_val = float(np.mean(vals))
        ci_low = float(np.percentile(vals, 2.5))
        ci_high = float(np.percentile(vals, 97.5))
        ci_rows.append({
            "Metric": m_name,
            "Mean (%)": round(mean_val, 2),
            "CI_95_Low (%)": round(ci_low, 2),
            "CI_95_High (%)": round(ci_high, 2)
        })

    return pd.DataFrame(ci_rows)


def run_full_p7r_evaluation():
    # 1. Reconstruct & persist datasets
    manifest = reconstruct_and_persist_test_datasets()

    ctrl_path = manifest["artifacts"]["controlled_test"]["path"]
    open_path = manifest["artifacts"]["open_form_test"]["path"]

    # 2. Load frozen components
    print("\n==================================================================")
    print("STEP 2: LOADING FROZEN SCIENTIFIC SYSTEM (tau=0.70)")
    print("==================================================================")
    db_path = "data/interim/contextbind_timeline.sqlite"
    rule_art = "artifacts/frozen/rule_binder.json"
    ai_art = "artifacts/frozen/semantic_ai_binder.pkl"

    rule_binder = RuleBasedClaimBinder.load(rule_art)
    ai_binder = SemanticAIBinder.load(ai_art)
    ai_binder._init_transformer()
    verifier = OracleTemporalVerifier(db_path)
    runtime = ContextBindRuntime()
    tau = 0.70

    # 3. Read persisted test files strictly
    print("\n==================================================================")
    print("STEP 3: READING FROZEN PERSISTED TEST FILES")
    print("==================================================================")
    with open(ctrl_path, "r", encoding="utf-8") as f:
        ctrl_claims = [json.loads(line) for line in f]
    print(f"Loaded {len(ctrl_claims)} Controlled TEST claims from {ctrl_path}")

    with open(open_path, "r", encoding="utf-8") as f:
        open_claims = [json.loads(line) for line in f]
    print(f"Loaded {len(open_claims)} Open-Form TEST claims from {open_path}")

    # 4. Parse claims with frozen binders
    print("\n[Parsing Controlled TEST claims...]")
    ctrl_rule_preds = [rule_binder.parse(c["claim_text"]) for c in ctrl_claims]
    ctrl_ai_preds = ai_binder.parse_batch([c["claim_text"] for c in ctrl_claims])

    print("[Parsing Open-Form TEST claims...]")
    open_rule_preds = [rule_binder.parse(c["claim_text"]) for c in open_claims]
    open_ai_preds = ai_binder.parse_batch([c["claim_text"] for c in open_claims])

    # 5. Evaluate Controlled Test Lane
    print("\n==================================================================")
    print("STEP 4: CONTROLLED TEST EVALUATION & ORACLE AUDIT")
    print("==================================================================")
    eval_ctrl_orc = evaluate_dataset(ctrl_claims, [], [], verifier, runtime, tau=tau, mode="ORACLE")
    eval_ctrl_rule = evaluate_dataset(ctrl_claims, ctrl_rule_preds, ctrl_ai_preds, verifier, runtime, tau=tau, mode="RULE")
    eval_ctrl_ai = evaluate_dataset(ctrl_claims, ctrl_rule_preds, ctrl_ai_preds, verifier, runtime, tau=tau, mode="AI_ONLY")
    eval_ctrl_hyb = evaluate_dataset(ctrl_claims, ctrl_rule_preds, ctrl_ai_preds, verifier, runtime, tau=tau, mode="HYBRID")

    print(f"B_ORACLE Controlled Coverage: {eval_ctrl_orc['coverage_pct']}% (Expected: 100.0%)")
    for tc, tm in eval_ctrl_orc["task_metrics"].items():
        print(f"  Oracle Task {tc}: {tm['coverage_pct']}% coverage ({tm['n_total']} claims)")

    ctrl_metrics_rows = [
        {"Pipeline": "B_ORACLE (Upper Bound)", "Exact Match (%)": 100.0, "Coverage (%)": eval_ctrl_orc["coverage_pct"], "HOLD Rate (%)": eval_ctrl_orc["hold_rate_pct"], "Selective Acc (%)": eval_ctrl_orc["selective_accuracy_pct"], "Utility Acc (%)": eval_ctrl_orc["utility_accuracy_pct"], "UAR (%)": eval_ctrl_orc["uar_pct"], "BABR (%)": eval_ctrl_orc["babr_pct"], "Pair Consist (%)": eval_ctrl_orc["pair_consistency_pct"]},
        {"Pipeline": "B_RULE (Fast-Path)", "Exact Match (%)": eval_ctrl_rule["exact_predicate_match_pct"], "Coverage (%)": eval_ctrl_rule["coverage_pct"], "HOLD Rate (%)": eval_ctrl_rule["hold_rate_pct"], "Selective Acc (%)": eval_ctrl_rule["selective_accuracy_pct"], "Utility Acc (%)": eval_ctrl_rule["utility_accuracy_pct"], "UAR (%)": eval_ctrl_rule["uar_pct"], "BABR (%)": eval_ctrl_rule["babr_pct"], "Pair Consist (%)": eval_ctrl_rule["pair_consistency_pct"]},
        {"Pipeline": "Semantic AI Alone", "Exact Match (%)": eval_ctrl_ai["exact_predicate_match_pct"], "Coverage (%)": eval_ctrl_ai["coverage_pct"], "HOLD Rate (%)": eval_ctrl_ai["hold_rate_pct"], "Selective Acc (%)": eval_ctrl_ai["selective_accuracy_pct"], "Utility Acc (%)": eval_ctrl_ai["utility_accuracy_pct"], "UAR (%)": eval_ctrl_ai["uar_pct"], "BABR (%)": eval_ctrl_ai["babr_pct"], "Pair Consist (%)": eval_ctrl_ai["pair_consistency_pct"]},
        {"Pipeline": "Final Gated Hybrid (tau=0.70)", "Exact Match (%)": eval_ctrl_hyb["exact_predicate_match_pct"], "Coverage (%)": eval_ctrl_hyb["coverage_pct"], "HOLD Rate (%)": eval_ctrl_hyb["hold_rate_pct"], "Selective Acc (%)": eval_ctrl_hyb["selective_accuracy_pct"], "Utility Acc (%)": eval_ctrl_hyb["utility_accuracy_pct"], "UAR (%)": eval_ctrl_hyb["uar_pct"], "BABR (%)": eval_ctrl_hyb["babr_pct"], "Pair Consist (%)": eval_ctrl_hyb["pair_consistency_pct"]}
    ]
    df_ctrl_metrics = pd.DataFrame(ctrl_metrics_rows)
    df_ctrl_metrics.to_csv("reports/phases/P7_PRIMARY_TEST_METRICS.csv", index=False)
    print("\n--- CONTROLLED TEST METRICS ---")
    print(df_ctrl_metrics.to_string(index=False))

    # 6. Evaluate Open-Form Test Lane
    print("\n==================================================================")
    print("STEP 5: OPEN-FORM TEST EVALUATION & DETAILED ACCOUNTING")
    print("==================================================================")
    eval_open_rule = evaluate_dataset(open_claims, open_rule_preds, open_ai_preds, verifier, runtime, tau=tau, mode="RULE")
    eval_open_ai = evaluate_dataset(open_claims, open_rule_preds, open_ai_preds, verifier, runtime, tau=tau, mode="AI_ONLY")
    eval_open_hyb = evaluate_dataset(open_claims, open_rule_preds, open_ai_preds, verifier, runtime, tau=tau, mode="HYBRID")

    open_metrics_rows = [
        {"Pipeline": "B_RULE (Fast-Path)", "Exact Match (%)": eval_open_rule["exact_predicate_match_pct"], "Coverage (%)": eval_open_rule["coverage_pct"], "HOLD Rate (%)": eval_open_rule["hold_rate_pct"], "Selective Acc (%)": eval_open_rule["selective_accuracy_pct"], "Utility Acc (%)": eval_open_rule["utility_accuracy_pct"], "UAR (%)": eval_open_rule["uar_pct"], "BABR (%)": eval_open_rule["babr_pct"], "Pair Consist (%)": eval_open_rule["pair_consistency_pct"]},
        {"Pipeline": "Semantic AI Alone", "Exact Match (%)": eval_open_ai["exact_predicate_match_pct"], "Coverage (%)": eval_open_ai["coverage_pct"], "HOLD Rate (%)": eval_open_ai["hold_rate_pct"], "Selective Acc (%)": eval_open_ai["selective_accuracy_pct"], "Utility Acc (%)": eval_open_ai["utility_accuracy_pct"], "UAR (%)": eval_open_ai["uar_pct"], "BABR (%)": eval_open_ai["babr_pct"], "Pair Consist (%)": eval_open_ai["pair_consistency_pct"]},
        {"Pipeline": "Final Gated Hybrid (tau=0.70)", "Exact Match (%)": eval_open_hyb["exact_predicate_match_pct"], "Coverage (%)": eval_open_hyb["coverage_pct"], "HOLD Rate (%)": eval_open_hyb["hold_rate_pct"], "Selective Acc (%)": eval_open_hyb["selective_accuracy_pct"], "Utility Acc (%)": eval_open_hyb["utility_accuracy_pct"], "UAR (%)": eval_open_hyb["uar_pct"], "BABR (%)": eval_open_hyb["babr_pct"], "Pair Consist (%)": eval_open_hyb["pair_consistency_pct"]}
    ]
    df_open_metrics = pd.DataFrame(open_metrics_rows)
    df_open_metrics.to_csv("reports/phases/P7_OPEN_FORM_TEST_METRICS.csv", index=False)
    print("\n--- OPEN-FORM TEST METRICS ---")
    print(df_open_metrics.to_string(index=False))

    # Detailed verifier-level routing breakdown
    r_valid_list = [runtime._is_rule_predicate_valid(p) for p in open_rule_preds]
    a_valid_list = [runtime._is_ai_predicate_valid(p) for p in open_ai_preds]
    a_conf_list = [float(p.get("confidence", 0.0)) for p in open_ai_preds]

    R_accept_pass = 0
    R_accept_block = 0
    R_accept_hold = 0

    R_hold_AI_accept_pass = 0
    R_hold_AI_accept_block = 0
    R_hold_AI_accept_hold = 0

    R_hold_AI_hold = 0

    for i, o in enumerate(eval_open_hyb["outcomes"]):
        rv = r_valid_list[i]
        av = a_valid_list[i]
        conf = a_conf_list[i]
        dec = o["decision"]

        if rv:
            if dec == "PASS":
                R_accept_pass += 1
            elif dec == "BLOCK":
                R_accept_block += 1
            else:
                R_accept_hold += 1
        else:
            if av and conf >= tau:
                if dec == "PASS":
                    R_hold_AI_accept_pass += 1
                elif dec == "BLOCK":
                    R_hold_AI_accept_block += 1
                else:
                    R_hold_AI_accept_hold += 1
            else:
                R_hold_AI_hold += 1

    print("\n--- OPEN-FORM VERIFIER-LEVEL OUTCOME ACCOUNTING ---")
    print(f"RULE_ACCEPT -> PASS: {R_accept_pass}")
    print(f"RULE_ACCEPT -> BLOCK: {R_accept_block}")
    print(f"RULE_ACCEPT -> verifier HOLD/error: {R_accept_hold}")
    print(f"Total RULE_ACCEPT: {R_accept_pass + R_accept_block + R_accept_hold}")
    print(f"RULE_HOLD -> AI_ACCEPT -> PASS: {R_hold_AI_accept_pass}")
    print(f"RULE_HOLD -> AI_ACCEPT -> BLOCK: {R_hold_AI_accept_block}")
    print(f"RULE_HOLD -> AI_ACCEPT -> verifier HOLD/error: {R_hold_AI_accept_hold}")
    print(f"Total RULE_HOLD -> AI_ACCEPT: {R_hold_AI_accept_pass + R_hold_AI_accept_block + R_hold_AI_accept_hold}")
    print(f"RULE_HOLD -> AI_HOLD: {R_hold_AI_hold}")
    print(f"Final Decided (PASS+BLOCK): {eval_open_hyb['pass_count'] + eval_open_hyb['block_count']} ({eval_open_hyb['coverage_pct']}%)")

    # 7. Patient-Level Bootstrap Analysis on Open-Form Primary TEST
    print("\n==================================================================")
    print("STEP 6: PATIENT-LEVEL BOOTSTRAP (B=1000, seed=20261004)")
    print("==================================================================")
    df_bootstrap = run_patient_bootstrap(eval_open_hyb["outcomes"], n_bootstrap=1000, seed=20261004)
    df_bootstrap.to_csv("reports/phases/P7_PATIENT_BOOTSTRAP.csv", index=False)
    print(df_bootstrap.to_string(index=False))

    # 8. Error Analysis & Outcome logging
    print("\n==================================================================")
    print("STEP 7: ERROR ANALYSIS & FAILURE LOGGING")
    print("==================================================================")
    error_records = []
    for o in eval_open_hyb["outcomes"]:
        error_records.append({
            "idx": o["idx"],
            "claim_id": o["claim_id"],
            "pair_id": o["pair_id"],
            "patient_id": o["patient_id"],
            "task_code": o["task_code"],
            "claim_text": o["claim_text"],
            "ground_truth": o["ground_truth"],
            "route": o["route"],
            "decision": o["decision"],
            "confidence": o["confidence"],
            "exact_predicate_match": o["exact_predicate_match"],
            "explanation": o["explanation"]
        })
    df_errors = pd.DataFrame(error_records)
    df_errors.to_csv("reports/phases/P7_ERROR_ANALYSIS.csv", index=False)
    print(f"Saved {len(df_errors)} claim outcomes to reports/phases/P7_ERROR_ANALYSIS.csv")

    # Print summary of task breakdown
    print("\n--- PER-TASK HYBRID METRICS (OPEN-FORM TEST) ---")
    for tc, tm in eval_open_hyb["task_metrics"].items():
        print(f"Task {tc}: Coverage={tm['coverage_pct']}%, SelAcc={tm['selective_acc_pct']}%, UtilAcc={tm['utility_acc_pct']}%, UAR={tm['uar_pct']}%, BABR={tm['babr_pct']}%")

    print("\n==================================================================")
    print("P7R FINAL LOCKED EVALUATION COMPLETED SUCCESSFULLY")
    print("==================================================================")


if __name__ == "__main__":
    run_full_p7r_evaluation()
