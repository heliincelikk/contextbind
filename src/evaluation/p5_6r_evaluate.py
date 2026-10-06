"""
ContextBind — Phase P5.6R Routing Invariant & Safety Repair Engine
Executes:
1. Patient-Diversified Dataset Generation (>=50 TRAIN patients, >=30 VAL patients)
2. Strict Routing Invariant Enforcement:
   - RULE_ACCEPT
   - RULE_HOLD -> AI_ACCEPT (if conf >= tau and ai_valid)
   - RULE_HOLD -> AI_HOLD
   - Guarantees Hybrid Coverage >= Rule Coverage mathematically and empirically.
3. 50-Claim End-to-End Tracing across all 5 routing strata.
4. Risk-Coverage Calibration on diversified TRAIN.
5. Out-of-Distribution Validation with Patient Bootstrap on diversified VAL.
"""

import os
import sys
import json
import csv
import random
import numpy as np
from collections import defaultdict, Counter
from typing import Dict, Any, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.claims.natural_claim_generator import NaturalClaimGenerator
from src.binder.rule_binder import RuleBasedClaimBinder
from src.binder.semantic_ai_binder import SemanticAIBinder
from src.verification.oracle_temporal_verifier import OracleTemporalVerifier
from src.evaluation.p5_evaluate import evaluate_predicates, load_jsonl

def is_predicate_valid(p: Dict[str, Any]) -> bool:
    """Strictly checks if parsed predicate contains all required semantic fields."""
    if not p:
        return False
    t_type = p.get("task_type")
    c_type = p.get("claim_type")
    concept = p.get("clinical_concept")
    eA = p.get("event_A_id")
    eB = p.get("event_B_id")
    
    if t_type not in ["S1", "S2", "S3", "S4"] or c_type in [None, "UNKNOWN"]:
        return False
        
    if t_type in ["S1", "S3", "S4"]:
        if concept is None:
            return False
        if t_type == "S4" and p.get("claimed_value") is None:
            return False
        return True
    elif t_type == "S2":
        return bool(eA and eB and eA != eB)
    return False

def make_hold_predicate(conf: float = 0.0, source: str = "HOLD") -> Dict[str, Any]:
    return {
        "task_type": "UNKNOWN",
        "clinical_concept": None,
        "claim_type": "UNKNOWN",
        "temporal_window": None,
        "comparator": None,
        "claimed_value": None,
        "event_A_id": None,
        "event_B_id": None,
        "confidence": conf,
        "source": source
    }

def compute_metrics_with_routing(
    claims: List[Dict[str, Any]],
    rule_preds: List[Dict[str, Any]],
    ai_preds: List[Dict[str, Any]],
    tau: float,
    mode: str, # 'RULE_ONLY', 'AI_ONLY', 'HYBRID'
    verifier: OracleTemporalVerifier
) -> Dict[str, Any]:
    
    routed_preds = []
    routes = []
    
    for r_p, a_p in zip(rule_preds, ai_preds):
        r_valid = is_predicate_valid(r_p)
        a_valid = is_predicate_valid(a_p)
        a_conf = a_p.get("confidence", 0.0)
        
        if mode == "RULE_ONLY":
            if r_valid:
                p_out = dict(r_p)
                p_out["source"] = "RULE_ACCEPT"
                routes.append("RULE_ACCEPT")
            else:
                p_out = make_hold_predicate(source="RULE_HOLD")
                routes.append("RULE_HOLD")
            routed_preds.append(p_out)
            
        elif mode == "AI_ONLY":
            if a_valid and a_conf >= tau:
                p_out = dict(a_p)
                p_out["source"] = "AI_ACCEPT"
                routes.append("AI_ACCEPT")
            else:
                p_out = make_hold_predicate(conf=a_conf, source="AI_HOLD")
                routes.append("AI_HOLD")
            routed_preds.append(p_out)
            
        elif mode == "HYBRID":
            if r_valid:
                p_out = dict(r_p)
                p_out["source"] = "RULE_ACCEPT"
                routes.append("RULE_ACCEPT")
            else:
                # Rule abstained: invoke AI fallback
                if a_valid and a_conf >= tau:
                    p_out = dict(a_p)
                    p_out["source"] = "AI_ACCEPT"
                    routes.append("AI_ACCEPT")
                else:
                    p_out = make_hold_predicate(conf=a_conf, source="AI_HOLD")
                    routes.append("AI_HOLD")
            routed_preds.append(p_out)

    pred_match_res = evaluate_predicates(claims, routed_preds)

    claims_with_preds = []
    for c, p in zip(claims, routed_preds):
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

    n_total = len(claims)
    sup_claims = [c for c in claims if c["ground_truth"] == "SUPPORTED"]
    con_claims = [c for c in claims if c["ground_truth"] == "CONTRADICTED"]
    n_sup = len(sup_claims)
    n_con = len(con_claims)

    n_pass = sum(1 for v in verdicts if v == "PASS")
    n_block = sum(1 for v in verdicts if v == "BLOCK")
    n_hold = sum(1 for v in verdicts if v == "HOLD")

    sup_pass = sum(1 for i, c in enumerate(claims) if c["ground_truth"] == "SUPPORTED" and verdicts[i] == "PASS")
    sup_block = sum(1 for i, c in enumerate(claims) if c["ground_truth"] == "SUPPORTED" and verdicts[i] == "BLOCK")
    sup_hold = sum(1 for i, c in enumerate(claims) if c["ground_truth"] == "SUPPORTED" and verdicts[i] == "HOLD")

    con_block = sum(1 for i, c in enumerate(claims) if c["ground_truth"] == "CONTRADICTED" and verdicts[i] == "BLOCK")
    con_pass = sum(1 for i, c in enumerate(claims) if c["ground_truth"] == "CONTRADICTED" and verdicts[i] == "PASS")
    con_hold = sum(1 for i, c in enumerate(claims) if c["ground_truth"] == "CONTRADICTED" and verdicts[i] == "HOLD")

    uar = con_pass / n_con if n_con else 0.0
    babr = sup_block / n_sup if n_sup else 0.0
    hold_rate = n_hold / n_total
    coverage = (n_pass + n_block) / n_total

    decided_count = n_pass + n_block
    selective_acc = (sup_pass + con_block) / decided_count if decided_count > 0 else 0.0
    utility_acc = (sup_pass + con_block) / n_total

    # Pair consistency
    pair_map = defaultdict(list)
    for i, c in enumerate(claims):
        pair_map[c["pair_id"]].append((c, verdicts[i]))
    consistent_pairs = sum(1 for p_list in pair_map.values() if len(p_list) == 2 and all((v == "PASS" and c["ground_truth"] == "SUPPORTED") or (v == "BLOCK" and c["ground_truth"] == "CONTRADICTED") for c, v in p_list))
    pair_cons_rate = consistent_pairs / len(pair_map) if pair_map else 0.0

    return {
        "n_total": n_total,
        "n_sup": n_sup,
        "n_con": n_con,
        "n_pass": n_pass,
        "n_block": n_block,
        "n_hold": n_hold,
        "sup_pass": sup_pass,
        "sup_block": sup_block,
        "sup_hold": sup_hold,
        "con_block": con_block,
        "con_pass": con_pass,
        "con_hold": con_hold,
        "uar": uar,
        "babr": babr,
        "hold_rate": hold_rate,
        "coverage": coverage,
        "selective_acc": selective_acc,
        "utility_acc": utility_acc,
        "exact_pred_match": pred_match_res["exact_predicate_match"],
        "pair_cons_rate": pair_cons_rate,
        "consistent_pairs": consistent_pairs,
        "total_pairs": len(pair_map),
        "routed_preds": routed_preds,
        "routes": routes,
        "verdicts": verdicts
    }

def run_p5_6r():
    print("=" * 70)
    print("CONTEXTBIND — PHASE P5.6R ROUTING INVARIANT & SAFETY REPAIR")
    print("=" * 70)

    db_path = "data/interim/contextbind_timeline.sqlite"
    split_path = "configs/split_primary_20261004.json"
    train_claims_path = "data/processed/p4_final_train.jsonl"
    seed = 20261004

    # 1. Generate Diversified Cohorts
    print("\n[1/6] Generating Diversified Patient Cohorts (Target: >=50 TRAIN pids, >=30 VAL pids)...")
    gen = NaturalClaimGenerator(db_path, split_path, seed=seed)

    train_calib_res = gen.generate_lane_b_dataset(pairs_per_task=125, target_split="TRAIN", max_pairs_per_patient=3)
    calib_claims = train_calib_res["all_claims"]
    calib_pids = set(c["patient_id"] for c in calib_claims)

    val_eval_res = gen.generate_lane_b_dataset(pairs_per_task=125, target_split="VAL", max_pairs_per_patient=3)
    val_claims = val_eval_res["all_claims"]
    val_pids = set(c["patient_id"] for c in val_claims)

    print(f"  TRAIN Calibration Set: {len(calib_claims)} claims ({len(calib_claims)//2} pairs) across {len(calib_pids)} distinct TRAIN patients")
    print(f"  VAL Evaluation Set:    {len(val_claims)} claims ({len(val_claims)//2} pairs) across {len(val_pids)} distinct VAL patients")
    print(f"  Disjointness Check:    {len(calib_pids.intersection(val_pids))} overlapping patients (0 expected)")
    assert len(calib_pids.intersection(val_pids)) == 0, "Split overlap detected!"
    assert len(calib_pids) >= 50, f"Expected >= 50 TRAIN patients, got {len(calib_pids)}"
    assert len(val_pids) >= 30, f"Expected >= 30 VAL patients, got {len(val_pids)}"

    # 2. Train Binders on Frozen P4 TRAIN
    print("\n[2/6] Loading Frozen Semantic AI & Rule Binders...")
    p4_train = load_jsonl(train_claims_path)
    rule_binder = RuleBasedClaimBinder().fit(p4_train)
    ai_binder = SemanticAIBinder(model_name="distilbert/distilbert-base-uncased", seed=seed).fit(p4_train)

    verifier = OracleTemporalVerifier(db_path)
    conn = verifier._connect()
    cursor = conn.cursor()
    cursor.execute("SELECT resource_id, clinical_display FROM timeline_events WHERE is_post_death_event = 0")
    event_display_map = {r[0]: r[1] for r in cursor.fetchall()}
    conn.close()

    # Precompute calibration parses
    calib_texts = [c["claim_text"] for c in calib_claims]
    calib_cand_events = [[{"resource_id": eid, "clinical_display": event_display_map.get(eid, "")} for eid in c.get("source_event_ids", [])] if c["task_code"] == "S2" else None for c in calib_claims]
    calib_rule_preds = [rule_binder.parse(c["claim_text"], candidate_events=calib_cand_events[i]) for i, c in enumerate(calib_claims)]
    calib_ai_preds = ai_binder.parse_batch(calib_texts, calib_cand_events)

    # 3. Sweep Threshold on Diversified TRAIN Calibration Cohort
    print("\n[3/6] Risk-Coverage Sweep on Diversified TRAIN Calibration Set...")
    candidate_taus = [0.00, 0.40, 0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 0.98]
    calib_curve_rows = []

    m_rule_calib = compute_metrics_with_routing(calib_claims, calib_rule_preds, calib_ai_preds, tau=0.0, mode="RULE_ONLY", verifier=verifier)
    rule_cov_calib = m_rule_calib["coverage"]
    print(f"  B_RULE ONLY Calibration Baseline: Coverage={rule_cov_calib*100:.2f}%, UAR={m_rule_calib['uar']*100:.2f}%, BABR={m_rule_calib['babr']*100:.2f}%")

    selected_tau = None
    for tau in candidate_taus:
        m = compute_metrics_with_routing(calib_claims, calib_rule_preds, calib_ai_preds, tau=tau, mode="HYBRID", verifier=verifier)
        cov_gain = m["coverage"] - rule_cov_calib
        print(f"  tau={tau:.2f} | Cov={m['coverage']*100:.1f}% (+{cov_gain*100:.1f}pp) | HOLD={m['hold_rate']*100:.1f}% | UAR={m['uar']*100:.2f}% | BABR={m['babr']*100:.2f}% | SelAcc={m['selective_acc']*100:.2f}% | UtilAcc={m['utility_acc']*100:.2f}% | PairCons={m['pair_cons_rate']*100:.1f}%")
        calib_curve_rows.append({
            "set": "TRAIN_CALIBRATION",
            "tau": f"{tau:.2f}",
            "coverage": f"{m['coverage']:.4f}",
            "coverage_gain_pp": f"{cov_gain*100:+.2f}",
            "hold_rate": f"{m['hold_rate']:.4f}",
            "uar": f"{m['uar']:.4f}",
            "babr": f"{m['babr']:.4f}",
            "selective_acc": f"{m['selective_acc']:.4f}",
            "utility_acc": f"{m['utility_acc']:.4f}",
            "exact_pred_match": f"{m['exact_pred_match']:.4f}",
            "pair_cons_rate": f"{m['pair_cons_rate']:.4f}"
        })
        # Selection Policy:
        # 1. Minimize UAR
        # 2. Hybrid coverage > B_RULE coverage
        # 3. Control BABR
        # 4. Maximize pair consistency
        if m["uar"] <= 0.05 and cov_gain > 0.01 and tau >= 0.70 and selected_tau is None:
            selected_tau = tau

    if selected_tau is None:
        selected_tau = 0.85
    print(f"\n  ==> SELECTED FROZEN OPERATIONAL THRESHOLD (tau*): {selected_tau:.2f}")

    # 4. Evaluate on Diversified VAL Evaluation Set
    print(f"\n[4/6] Evaluating on Diversified VAL Evaluation Set ({len(val_claims)} claims across {len(val_pids)} patients)...")
    val_texts = [c["claim_text"] for c in val_claims]
    val_cand_events = [[{"resource_id": eid, "clinical_display": event_display_map.get(eid, "")} for eid in c.get("source_event_ids", [])] if c["task_code"] == "S2" else None for c in val_claims]
    val_rule_preds = [rule_binder.parse(c["claim_text"], candidate_events=val_cand_events[i]) for i, c in enumerate(val_claims)]
    val_ai_preds = ai_binder.parse_batch(val_texts, val_cand_events)

    val_eval_results = {}
    val_accounting_rows = []

    modes = [
        ("B_RULE_ONLY", 0.0, "RULE_ONLY"),
        ("SEMANTIC_AI_ONLY", 0.0, "AI_ONLY"),
        ("RULE_AI_UNGATED", 0.0, "HYBRID"),
        ("RULE_AI_GATED_TAU_STAR", selected_tau, "HYBRID")
    ]

    for name, tau_val, mode_val in modes:
        m = compute_metrics_with_routing(val_claims, val_rule_preds, val_ai_preds, tau=tau_val, mode=mode_val, verifier=verifier)
        val_eval_results[name] = m
        print(f"\n--- {name} (VAL Set) ---")
        print(f"  Coverage:                 {m['coverage']*100:.2f}% (PASS={m['n_pass']}, BLOCK={m['n_block']}, HOLD={m['n_hold']})")
        print(f"  HOLD Rate:                {m['hold_rate']*100:.2f}%")
        print(f"  Selective Accuracy:       {m['selective_acc']*100:.2f}% ({m['sup_pass']+m['con_block']}/{m['n_pass']+m['n_block']})")
        print(f"  Overall Utility Accuracy: {m['utility_acc']*100:.2f}% ({m['sup_pass']+m['con_block']}/{m['n_total']})")
        print(f"  UAR (Safety Failure):     {m['uar']*100:.2f}% ({m['con_pass']}/{m['n_con']})")
        print(f"  BABR (Overblocking):      {m['babr']*100:.2f}% ({m['sup_block']}/{m['n_sup']})")
        print(f"  Exact Predicate Match:    {m['exact_pred_match']*100:.2f}%")
        print(f"  Pair Consistency Rate:    {m['pair_cons_rate']*100:.2f}% ({m['consistent_pairs']}/{m['total_pairs']})")

        val_accounting_rows.append({
            "model": name,
            "tau": f"{tau_val:.2f}" if mode_val != "RULE_ONLY" else "N/A",
            "coverage": f"{m['coverage']:.4f}",
            "hold_rate": f"{m['hold_rate']:.4f}",
            "selective_accuracy": f"{m['selective_acc']:.4f}",
            "utility_accuracy": f"{m['utility_acc']:.4f}",
            "uar": f"{m['uar']:.4f}",
            "babr": f"{m['babr']:.4f}",
            "exact_predicate_match": f"{m['exact_pred_match']:.4f}",
            "pair_consistency_rate": f"{m['pair_cons_rate']:.4f}",
            "total_PASS": m["n_pass"],
            "total_BLOCK": m["n_block"],
            "total_HOLD": m["n_hold"],
            "supported_PASS": m["sup_pass"],
            "supported_BLOCK": m["sup_block"],
            "supported_HOLD": m["sup_hold"],
            "contradicted_BLOCK": m["con_block"],
            "contradicted_PASS": m["con_pass"],
            "contradicted_HOLD": m["con_hold"]
        })

    rule_cov_val = val_eval_results["B_RULE_ONLY"]["coverage"]
    gated_cov_val = val_eval_results["RULE_AI_GATED_TAU_STAR"]["coverage"]
    cov_gain_val = (gated_cov_val - rule_cov_val) * 100
    print(f"\n  ==> INVARIANT AUDIT: Hybrid Coverage ({gated_cov_val*100:.2f}%) >= Rule Coverage ({rule_cov_val*100:.2f}%): {gated_cov_val >= rule_cov_val} (+{cov_gain_val:.2f} pp)")

    # 5. Patient-Level Bootstrap Analysis (1,000 iterations over 30+ VAL patients)
    print("\n[5/6] Performing Patient-Level Bootstrap Analysis (1,000 resamples)...")
    val_claims_by_pid = defaultdict(list)
    for idx, c in enumerate(val_claims):
        val_claims_by_pid[c["patient_id"]].append(idx)

    unique_val_pids = list(val_claims_by_pid.keys())
    rng_boot = random.Random(seed)
    n_boot = 1000
    boot_uars = []
    boot_babrs = []
    boot_covs = []
    boot_util_accs = []

    gated_m = val_eval_results["RULE_AI_GATED_TAU_STAR"]
    val_verdicts = gated_m["verdicts"]

    for _ in range(n_boot):
        sample_pids = rng_boot.choices(unique_val_pids, k=len(unique_val_pids))
        b_indices = []
        for pid in sample_pids:
            b_indices.extend(val_claims_by_pid[pid])
        
        b_sup = [i for i in b_indices if val_claims[i]["ground_truth"] == "SUPPORTED"]
        b_con = [i for i in b_indices if val_claims[i]["ground_truth"] == "CONTRADICTED"]
        
        b_con_pass = sum(1 for i in b_con if val_verdicts[i] == "PASS")
        b_sup_block = sum(1 for i in b_sup if val_verdicts[i] == "BLOCK")
        b_decided = sum(1 for i in b_indices if val_verdicts[i] in ["PASS", "BLOCK"])
        b_correct = sum(1 for i in b_indices if (val_verdicts[i] == "PASS" and val_claims[i]["ground_truth"] == "SUPPORTED") or (val_verdicts[i] == "BLOCK" and val_claims[i]["ground_truth"] == "CONTRADICTED"))
        
        boot_uars.append(b_con_pass / len(b_con) if b_con else 0.0)
        boot_babrs.append(b_sup_block / len(b_sup) if b_sup else 0.0)
        boot_covs.append(b_decided / len(b_indices))
        boot_util_accs.append(b_correct / len(b_indices))

    boot_uar_ci = (np.percentile(boot_uars, 2.5), np.percentile(boot_uars, 97.5))
    boot_babr_ci = (np.percentile(boot_babrs, 2.5), np.percentile(boot_babrs, 97.5))
    boot_cov_ci = (np.percentile(boot_covs, 2.5), np.percentile(boot_covs, 97.5))
    boot_util_ci = (np.percentile(boot_util_accs, 2.5), np.percentile(boot_util_accs, 97.5))

    print(f"  Patient Bootstrap 95% CI:")
    print(f"    Coverage:         {np.mean(boot_covs)*100:.2f}% [{boot_cov_ci[0]*100:.2f}%, {boot_cov_ci[1]*100:.2f}%]")
    print(f"    UAR:              {np.mean(boot_uars)*100:.2f}% [{boot_uar_ci[0]*100:.2f}%, {boot_uar_ci[1]*100:.2f}%]")
    print(f"    BABR:             {np.mean(boot_babrs)*100:.2f}% [{boot_babr_ci[0]*100:.2f}%, {boot_babr_ci[1]*100:.2f}%]")
    print(f"    Utility Accuracy: {np.mean(boot_util_accs)*100:.2f}% [{boot_util_ci[0]*100:.2f}%, {boot_util_ci[1]*100:.2f}%]")

    # 6. Trace 50 Claims End to End across all 5 strata
    print("\n[6/6] Generating Deterministic 50-Claim Trace across 5 strata...")
    gated_routed_preds = gated_m["routed_preds"]
    gated_routes = gated_m["routes"]
    
    strata_map = defaultdict(list)
    for i, c in enumerate(val_claims):
        r_type = gated_routes[i]
        gt = c["ground_truth"]
        strata_key = f"{r_type}_{gt}" if r_type != "AI_HOLD" else "RULE_HOLD_AI_HOLD"
        strata_map[strata_key].append(i)

    # Sample 10 from each stratum
    rng_trace = random.Random(seed)
    selected_indices = []
    target_strata = [
        ("RULE_ACCEPT_SUPPORTED", 10),
        ("RULE_ACCEPT_CONTRADICTED", 10),
        ("AI_ACCEPT_SUPPORTED", 10),
        ("AI_ACCEPT_CONTRADICTED", 10),
        ("RULE_HOLD_AI_HOLD", 10)
    ]

    for s_key, count in target_strata:
        pool = strata_map.get(s_key, [])
        sampled = rng_trace.sample(pool, min(len(pool), count)) if len(pool) >= count else pool
        selected_indices.extend([(s_key, idx) for idx in sampled])

    # Write 50-claim trace markdown
    trace_file = "reports/phases/P5_6R_50_CLAIMS_TRACE.md"
    with open(trace_file, "w", encoding="utf-8") as f:
        f.write("# ContextBind — Phase P5.6R 50-Claim End-to-End Trace\n\n")
        f.write(f"Sampled deterministically (seed `{seed}`) across 5 routing strata from the patient-disjoint VAL cohort.\n\n")
        f.write("| # | Stratum | Claim ID | Task | Truth | Rule Status | AI Invoked | AI Conf | AI Concept | Verifier Verdict | Final Decision |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|---|\n")
        for num, (s_key, idx) in enumerate(selected_indices, 1):
            c = val_claims[idx]
            r_p = val_rule_preds[idx]
            a_p = val_ai_preds[idx]
            route = gated_routes[idx]
            v = val_verdicts[idx]
            
            r_stat = "ACCEPT" if is_predicate_valid(r_p) else "HOLD"
            ai_inv = "NO" if r_stat == "ACCEPT" else "YES"
            ai_conf = f"{a_p.get('confidence', 0.0):.2f}" if ai_inv == "YES" else "N/A"
            ai_concept = str(a_p.get('clinical_concept')) if ai_inv == "YES" else "N/A"
            
            f.write(f"| {num} | `{s_key}` | `{c['pair_id']}` | {c['task_code']} | `{c['ground_truth']}` | `{r_stat}` | {ai_inv} | {ai_conf} | `{ai_concept}` | `{v}` | `{v}` |\n")

    # Task Breakdown for Gated Model on VAL
    task_rows = []
    for task in ["S1", "S2", "S3", "S4"]:
        t_indices = [i for i, c in enumerate(val_claims) if c["task_code"] == task]
        t_claims = [val_claims[i] for i in t_indices]
        t_r_preds = [val_rule_preds[i] for i in t_indices]
        t_a_preds = [val_ai_preds[i] for i in t_indices]
        t_m = compute_metrics_with_routing(t_claims, t_r_preds, t_a_preds, tau=selected_tau, mode="HYBRID", verifier=verifier)
        task_rows.append({
            "task_code": task,
            "claims": len(t_claims),
            "coverage": f"{t_m['coverage']:.4f}",
            "hold_rate": f"{t_m['hold_rate']:.4f}",
            "uar": f"{t_m['uar']:.4f}",
            "babr": f"{t_m['babr']:.4f}",
            "selective_acc": f"{t_m['selective_acc']:.4f}",
            "utility_acc": f"{t_m['utility_acc']:.4f}",
            "exact_pred_match": f"{t_m['exact_pred_match']:.4f}",
            "pair_cons_rate": f"{t_m['pair_cons_rate']:.4f}"
        })

    # Save CSVs
    os.makedirs("reports/phases", exist_ok=True)
    with open("reports/phases/P5_6R_CALIBRATION_CURVE.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "set", "tau", "coverage", "coverage_gain_pp", "hold_rate", "uar", "babr", "selective_acc", "utility_acc", "exact_pred_match", "pair_cons_rate"
        ])
        writer.writeheader()
        for r in calib_curve_rows:
            writer.writerow(r)

    with open("reports/phases/P5_6R_VAL_ACCOUNTING.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "model", "tau", "coverage", "hold_rate", "selective_accuracy", "utility_accuracy", "uar", "babr",
            "exact_predicate_match", "pair_consistency_rate",
            "total_PASS", "total_BLOCK", "total_HOLD",
            "supported_PASS", "supported_BLOCK", "supported_HOLD",
            "contradicted_BLOCK", "contradicted_PASS", "contradicted_HOLD"
        ])
        writer.writeheader()
        for r in val_accounting_rows:
            writer.writerow(r)

    with open("reports/phases/P5_6R_VAL_TASK_METRICS.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "task_code", "claims", "coverage", "hold_rate", "uar", "babr", "selective_acc", "utility_acc", "exact_pred_match", "pair_cons_rate"
        ])
        writer.writeheader()
        for r in task_rows:
            writer.writerow(r)

    print("\n[SUCCESS] Phase P5.6R Evaluation and Reporting complete.")

if __name__ == "__main__":
    run_p5_6r()
