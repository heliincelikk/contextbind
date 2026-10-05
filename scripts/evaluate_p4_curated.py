"""
ContextBind — Comprehensive Evaluation Runner for Phase P4 Curated Benchmark
Executes:
1. B_ORACLE Symbolic Verifier on all partitions (Train, Val-ID, Val-OOD)
2. L1 Metadata/Form Sentinel on Val-ID and Val-OOD (overall and per-task)
3. L2 Lexical Bag-of-Words Sentinel on Val-ID and Val-OOD (overall and per-task)
Strictly uses Python Standard Library.
"""

import os
import sys
import json
import time
import csv
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.verification.oracle_temporal_verifier import OracleTemporalVerifier
from src.leakage.metadata_sentinel import MetadataFormSentinel, compute_balanced_accuracy, compute_roc_auc, bootstrap_ci_auc
from src.leakage.lexical_sentinel import LexicalBagOfWordsSentinel

def load_jsonl(path: str):
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records

def run():
    print("=" * 70)
    print("CONTEXTBIND — PHASE P4 CURATED BENCHMARK EVALUATION")
    print("=" * 70)

    train_path = "data/processed/p4_final_train.jsonl"
    val_id_path = "data/processed/p4_final_val_id.jsonl"
    val_ood_path = "data/processed/p4_final_val_ood.jsonl"
    db_path = "data/interim/contextbind_timeline.sqlite"

    print("\n[1/3] Loading curated datasets...")
    train_claims = load_jsonl(train_path)
    val_id_claims = load_jsonl(val_id_path)
    val_ood_claims = load_jsonl(val_ood_path)
    all_claims = train_claims + val_id_claims + val_ood_claims

    print(f"  Train claims:   {len(train_claims)}")
    print(f"  Val-ID claims:  {len(val_id_claims)}")
    print(f"  Val-OOD claims: {len(val_ood_claims)}")
    print(f"  Total claims:   {len(all_claims)}")

    # ==========================================
    # Step 1: Oracle Evaluation
    # ==========================================
    print("\n[2/3] Running B_ORACLE Symbolic Verifier...")
    verifier = OracleTemporalVerifier(db_path)

    t0 = time.time()
    oracle_decisions = verifier.verify_batch(all_claims)
    t_elapsed = time.time() - t0

    # Evaluate Oracle accuracy per task and overall
    oracle_task_stats = defaultdict(lambda: {"total": 0, "correct": 0, "pass_sup": 0, "block_con": 0, "errors": 0})
    overall_correct = 0

    for c, (decision, expl) in zip(all_claims, oracle_decisions):
        task = c["task_code"]
        gt = c["ground_truth"]
        expected_decision = "PASS" if gt == "SUPPORTED" else "BLOCK"
        
        oracle_task_stats[task]["total"] += 1
        if decision == expected_decision:
            oracle_task_stats[task]["correct"] += 1
            overall_correct += 1
            if decision == "PASS":
                oracle_task_stats[task]["pass_sup"] += 1
            else:
                oracle_task_stats[task]["block_con"] += 1
        else:
            oracle_task_stats[task]["errors"] += 1

    overall_acc = overall_correct / len(all_claims)
    throughput = len(all_claims) / t_elapsed if t_elapsed > 0 else 0

    print(f"  Oracle Elapsed Time: {t_elapsed:.2f}s ({throughput:.1f} claims/sec)")
    print(f"  Oracle Overall Accuracy: {overall_acc * 100:.2f}% ({overall_correct}/{len(all_claims)})")
    
    oracle_csv_rows = []
    for task in ["S1", "S2", "S3", "S4"]:
        st = oracle_task_stats[task]
        acc = st["correct"] / st["total"] if st["total"] > 0 else 0.0
        print(f"    Task {task} Accuracy: {acc * 100:.2f}% ({st['correct']}/{st['total']})")
        oracle_csv_rows.append({
            "task_code": task,
            "total_claims": st["total"],
            "correct_verifications": st["correct"],
            "incorrect_verifications": st["errors"],
            "accuracy": f"{acc:.4f}",
            "runtime_seconds": f"{t_elapsed:.2f}"
        })

    oracle_csv_rows.append({
        "task_code": "OVERALL",
        "total_claims": len(all_claims),
        "correct_verifications": overall_correct,
        "incorrect_verifications": len(all_claims) - overall_correct,
        "accuracy": f"{overall_acc:.4f}",
        "runtime_seconds": f"{t_elapsed:.2f}"
    })

    with open("reports/phases/P4_ORACLE_RESULTS.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["task_code", "total_claims", "correct_verifications", "incorrect_verifications", "accuracy", "runtime_seconds"])
        writer.writeheader()
        for r in oracle_csv_rows:
            writer.writerow(r)

    assert overall_acc >= 0.999, f"B_ORACLE accuracy was {overall_acc}, expected ~100%!"

    # ==========================================
    # Step 2: Leakage Sentinels (L1 & L2)
    # ==========================================
    print("\n[3/3] Running Leakage Sentinels (L1 Metadata & L2 Lexical)...")
    leakage_rows = []

    for split_name, val_data in [("VAL-ID", val_id_claims), ("VAL-OOD", val_ood_claims)]:
        print(f"\n--- Evaluating on {split_name} ({len(val_data)} claims) ---")

        # 1. Overall evaluation
        # L1 Sentinel
        l1 = MetadataFormSentinel(epochs=50)
        res_l1 = l1.fit_predict(train_claims, val_data)
        print(f"  [L1 Overall] BalAcc: {res_l1['balanced_accuracy']:.4f}, AUC: {res_l1['auc']:.4f} (95% CI: [{res_l1['auc_ci_95'][0]:.4f}, {res_l1['auc_ci_95'][1]:.4f}])")

        leakage_rows.append({
            "split": split_name,
            "task_code": "OVERALL",
            "sentinel": "L1_METADATA_FORM",
            "accuracy": f"{res_l1['accuracy']:.4f}",
            "balanced_accuracy": f"{res_l1['balanced_accuracy']:.4f}",
            "auc": f"{res_l1['auc']:.4f}",
            "auc_ci_low": f"{res_l1['auc_ci_95'][0]:.4f}",
            "auc_ci_high": f"{res_l1['auc_ci_95'][1]:.4f}",
            "status": "PASS" if res_l1["auc"] <= 0.55 else ("CAUTION" if res_l1["auc"] <= 0.60 else "FAIL")
        })

        # L2 Sentinel
        l2 = LexicalBagOfWordsSentinel()
        res_l2 = l2.fit_predict(train_claims, val_data)
        print(f"  [L2 Overall] BalAcc: {res_l2['balanced_accuracy']:.4f}, AUC: {res_l2['auc']:.4f} (95% CI: [{res_l2['auc_ci_95'][0]:.4f}, {res_l2['auc_ci_95'][1]:.4f}])")

        leakage_rows.append({
            "split": split_name,
            "task_code": "OVERALL",
            "sentinel": "L2_LEXICAL_BAG_OF_WORDS",
            "accuracy": f"{res_l2['accuracy']:.4f}",
            "balanced_accuracy": f"{res_l2['balanced_accuracy']:.4f}",
            "auc": f"{res_l2['auc']:.4f}",
            "auc_ci_low": f"{res_l2['auc_ci_95'][0]:.4f}",
            "auc_ci_high": f"{res_l2['auc_ci_95'][1]:.4f}",
            "status": "PASS" if res_l2["auc"] <= 0.55 else ("CAUTION" if res_l2["auc"] <= 0.60 else "FAIL")
        })

        # 2. Per-task evaluation
        for task in ["S1", "S2", "S3", "S4"]:
            task_train = [c for c in train_claims if c["task_code"] == task]
            task_val = [c for c in val_data if c["task_code"] == task]
            if not task_val:
                continue

            # L1 task
            l1_t = MetadataFormSentinel(epochs=50)
            res_l1_t = l1_t.fit_predict(task_train, task_val)
            print(f"  [L1 {task}] BalAcc: {res_l1_t['balanced_accuracy']:.4f}, AUC: {res_l1_t['auc']:.4f} (95% CI: [{res_l1_t['auc_ci_95'][0]:.4f}, {res_l1_t['auc_ci_95'][1]:.4f}])")

            leakage_rows.append({
                "split": split_name,
                "task_code": task,
                "sentinel": "L1_METADATA_FORM",
                "accuracy": f"{res_l1_t['accuracy']:.4f}",
                "balanced_accuracy": f"{res_l1_t['balanced_accuracy']:.4f}",
                "auc": f"{res_l1_t['auc']:.4f}",
                "auc_ci_low": f"{res_l1_t['auc_ci_95'][0]:.4f}",
                "auc_ci_high": f"{res_l1_t['auc_ci_95'][1]:.4f}",
                "status": "PASS" if res_l1_t["auc"] <= 0.55 else ("CAUTION" if res_l1_t["auc"] <= 0.60 else "FAIL")
            })

            # L2 task
            l2_t = LexicalBagOfWordsSentinel()
            res_l2_t = l2_t.fit_predict(task_train, task_val)
            print(f"  [L2 {task}] BalAcc: {res_l2_t['balanced_accuracy']:.4f}, AUC: {res_l2_t['auc']:.4f} (95% CI: [{res_l2_t['auc_ci_95'][0]:.4f}, {res_l2_t['auc_ci_95'][1]:.4f}])")

            leakage_rows.append({
                "split": split_name,
                "task_code": task,
                "sentinel": "L2_LEXICAL_BAG_OF_WORDS",
                "accuracy": f"{res_l2_t['accuracy']:.4f}",
                "balanced_accuracy": f"{res_l2_t['balanced_accuracy']:.4f}",
                "auc": f"{res_l2_t['auc']:.4f}",
                "auc_ci_low": f"{res_l2_t['auc_ci_95'][0]:.4f}",
                "auc_ci_high": f"{res_l2_t['auc_ci_95'][1]:.4f}",
                "status": "PASS" if res_l2_t["auc"] <= 0.55 else ("CAUTION" if res_l2_t["auc"] <= 0.60 else "FAIL")
            })

    # Save Leakage Results CSV
    with open("reports/phases/P4_LEAKAGE_RESULTS.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "split", "task_code", "sentinel", "accuracy", "balanced_accuracy",
            "auc", "auc_ci_low", "auc_ci_high", "status"
        ])
        writer.writeheader()
        for r in leakage_rows:
            writer.writerow(r)

    print("\n[SUCCESS] Phase P4 evaluation complete.")

if __name__ == "__main__":
    run()
