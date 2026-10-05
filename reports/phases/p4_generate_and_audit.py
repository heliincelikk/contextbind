"""
ContextBind — Phase P4 Dataset Generation, Oracle Verification & Leakage Audit Engine
Generates balanced S1-S4 paired claims, executes Oracle Verifier (B_ORACLE),
and audits L1 Form and L2 Lexical leakage with 95% bootstrap confidence intervals.
Strictly uses Python Standard Library.
"""

import sys
import os
import json
import csv
import time
from collections import Counter, defaultdict

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.claims.claim_generator import TemporalClaimGenerator
from src.verification.oracle_temporal_verifier import OracleTemporalVerifier
from src.leakage.metadata_sentinel import MetadataFormSentinel
from src.leakage.lexical_sentinel import LexicalBagOfWordsSentinel, tokenize

def run_p4_audit():
    db_path = r"C:\Users\lenevo\Desktop\contexbind\data\interim\contextbind_timeline.sqlite"
    split_path = r"C:\Users\lenevo\Desktop\contexbind\configs\split_primary_20261004.json"
    out_dir = r"C:\Users\lenevo\Desktop\contexbind\data\processed"
    reports_dir = r"C:\Users\lenevo\Desktop\contexbind\reports\phases"

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)

    print("Step 1: Generating Controlled Temporal Claims across S1, S2, S3, S4...")
    start_t = time.time()
    generator = TemporalClaimGenerator(db_path, split_path, seed=20261004)
    all_splits = generator.generate_all_claims()
    elapsed_gen = time.time() - start_t
    print(f"Generation completed in {elapsed_gen:.2f}s.")

    train_claims = all_splits["train"]
    val_id_claims = all_splits["val_id"]
    val_ood_claims = all_splits["val_ood"]
    val_all_claims = val_id_claims + val_ood_claims

    # Assign persistent unique claim IDs
    for idx, c in enumerate(train_claims):
        c["claim_id"] = f"CLM_TRN_{idx:06d}"
    for idx, c in enumerate(val_id_claims):
        c["claim_id"] = f"CLM_VID_{idx:06d}"
    for idx, c in enumerate(val_ood_claims):
        c["claim_id"] = f"CLM_VOD_{idx:06d}"

    print(f"Train Claims: {len(train_claims)}")
    print(f"Validation In-Distribution Claims: {len(val_id_claims)}")
    print(f"Validation Held-Out (OOD) Claims: {len(val_ood_claims)}")

    # Save JSONL datasets
    for split_name, c_list in [
        ("p4_claims_train.jsonl", train_claims),
        ("p4_claims_val_id.jsonl", val_id_claims),
        ("p4_claims_val_ood.jsonl", val_ood_claims)
    ]:
        fpath = os.path.join(out_dir, split_name)
        with open(fpath, "w", encoding="utf-8") as f:
            for c in c_list:
                f.write(json.dumps(c) + "\n")
        print(f"Saved {fpath} ({len(c_list)} records)")

    # 1. Generate P4_CLAIM_COUNTS.csv
    csv1_path = os.path.join(reports_dir, "P4_CLAIM_COUNTS.csv")
    with open(csv1_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Partition", "TaskCode", "TotalClaims", "SupportedCount", "ContradictedCount", "PairBalance"])
        
        for part_name, c_list in [("TRAIN", train_claims), ("VAL_ID", val_id_claims), ("VAL_OOD", val_ood_claims)]:
            by_task = defaultdict(list)
            for c in c_list:
                by_task[c["task_code"]].append(c)
            for tcode in sorted(by_task.keys()):
                tc_list = by_task[tcode]
                n_sup = sum(1 for c in tc_list if c["ground_truth"] == "SUPPORTED")
                n_con = sum(1 for c in tc_list if c["ground_truth"] == "CONTRADICTED")
                writer.writerow([part_name, tcode, len(tc_list), n_sup, n_con, "1.00:1.00" if n_sup == n_con else f"{n_sup}:{n_con}"])

    # 2. Generate P4_TEMPLATE_BALANCE.csv
    csv2_path = os.path.join(reports_dir, "P4_TEMPLATE_BALANCE.csv")
    with open(csv2_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["TemplateFamily", "TaskCode", "IsHeldOutOOD", "TrainCount", "ValIDCount", "ValOODCount", "SupportedRatio"])
        
        all_c = train_claims + val_all_claims
        tf_map = defaultdict(lambda: {"task": "", "ood": False, "trn": 0, "vid": 0, "vod": 0, "sup": 0, "total": 0})
        
        for c in train_claims:
            tf = c["template_family"]
            tf_map[tf]["task"] = c["task_code"]
            tf_map[tf]["ood"] = c["is_held_out_template"]
            tf_map[tf]["trn"] += 1
            tf_map[tf]["total"] += 1
            if c["ground_truth"] == "SUPPORTED":
                tf_map[tf]["sup"] += 1

        for c in val_id_claims:
            tf = c["template_family"]
            tf_map[tf]["task"] = c["task_code"]
            tf_map[tf]["ood"] = c["is_held_out_template"]
            tf_map[tf]["vid"] += 1
            tf_map[tf]["total"] += 1
            if c["ground_truth"] == "SUPPORTED":
                tf_map[tf]["sup"] += 1

        for c in val_ood_claims:
            tf = c["template_family"]
            tf_map[tf]["task"] = c["task_code"]
            tf_map[tf]["ood"] = c["is_held_out_template"]
            tf_map[tf]["vod"] += 1
            tf_map[tf]["total"] += 1
            if c["ground_truth"] == "SUPPORTED":
                tf_map[tf]["sup"] += 1

        for tf in sorted(tf_map.keys()):
            data = tf_map[tf]
            ratio = data["sup"] / data["total"] if data["total"] else 0.0
            writer.writerow([tf, data["task"], "YES" if data["ood"] else "NO", data["trn"], data["vid"], data["vod"], f"{ratio:.2f}"])

    # 3. Generate P4_LEXICAL_BALANCE.csv
    csv3_path = os.path.join(reports_dir, "P4_LEXICAL_BALANCE.csv")
    key_words = [
        "increased", "decreased", "increasing", "decreasing", "rising", "downward",
        "before", "after", "prior", "following", "preceded", "succeeded", "earlier", "subsequent",
        "higher", "lower", "exceeds", "falls", "elevated", "reduced", "greater", "less",
        "current", "recent", "latest", "recorded", "active"
    ]
    with open(csv3_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["TargetWord", "CountInSupported", "CountInContradicted", "SupportedFraction", "BalanceAssessment"])
        
        all_train = train_claims
        pos_tokens = Counter()
        neg_tokens = Counter()
        for c in all_train:
            toks = set(tokenize(c["claim_text"]))
            if c["ground_truth"] == "SUPPORTED":
                pos_tokens.update(toks)
            else:
                neg_tokens.update(toks)

        for w in key_words:
            p_cnt = pos_tokens[w]
            n_cnt = neg_tokens[w]
            tot = p_cnt + n_cnt
            frac = p_cnt / tot if tot else 0.5
            assessment = "PERFECTLY_BALANCED" if p_cnt == n_cnt else ("BALANCED" if 0.45 <= frac <= 0.55 else "IMBALANCED")
            writer.writerow([w, p_cnt, n_cnt, f"{frac:.2f}", assessment])

    # 4. Step 2: Evaluate Oracle Verifier (B_ORACLE)
    print("\nStep 2: Evaluating Oracle Symbolic Verifier (B_ORACLE)...")
    verifier = OracleTemporalVerifier(db_path)
    oracle_results = []
    
    for split_lbl, c_list in [("TRAIN", train_claims), ("VAL_ID", val_id_claims), ("VAL_OOD", val_ood_claims)]:
        n_correct = 0
        n_hold = 0
        task_correct = Counter()
        task_total = Counter()
        
        for c in c_list:
            dec, expl = verifier.verify_claim_predicate(c)
            gt_dec = "PASS" if c["ground_truth"] == "SUPPORTED" else "BLOCK"
            if dec == gt_dec:
                n_correct += 1
                task_correct[c["task_code"]] += 1
            elif dec == "HOLD":
                n_hold += 1
            task_total[c["task_code"]] += 1

        overall_acc = n_correct / len(c_list) if c_list else 0.0
        oracle_results.append({
            "partition": split_lbl,
            "total": len(c_list),
            "correct": n_correct,
            "accuracy": overall_acc,
            "hold_count": n_hold,
            "task_acc": {t: task_correct[t] / task_total[t] for t in task_total}
        })
        print(f"Oracle Verifier on {split_lbl}: Accuracy = {overall_acc*100:.2f}% ({n_correct}/{len(c_list)})")

    csv5_path = os.path.join(reports_dir, "P4_ORACLE_RESULTS.csv")
    with open(csv5_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Partition", "TotalClaims", "CorrectVerifications", "OverallAccuracy", "S1_Accuracy", "S2_Accuracy", "S3_Accuracy", "S4_Accuracy", "HOLD_Count"])
        for res in oracle_results:
            ta = res["task_acc"]
            writer.writerow([
                res["partition"], res["total"], res["correct"], f"{res['accuracy']*100:.2f}%",
                f"{ta.get('S1', 0)*100:.2f}%", f"{ta.get('S2', 0)*100:.2f}%",
                f"{ta.get('S3', 0)*100:.2f}%", f"{ta.get('S4', 0)*100:.2f}%", res["hold_count"]
            ])

    # 5. Step 3: Run Leakage Sentinels (L1 Form & L2 Lexical)
    print("\nStep 3: Running L1 Metadata/Form and L2 Bag-of-Words Leakage Sentinels...")
    l1_sentinel = MetadataFormSentinel()
    l1_res_id = l1_sentinel.fit_predict(train_claims, val_id_claims)
    l1_res_ood = l1_sentinel.fit_predict(train_claims, val_ood_claims)

    l2_sentinel = LexicalBagOfWordsSentinel()
    l2_res_id = l2_sentinel.fit_predict(train_claims, val_id_claims)
    l2_res_ood = l2_sentinel.fit_predict(train_claims, val_ood_claims)

    csv4_path = os.path.join(reports_dir, "P4_LEAKAGE_RESULTS.csv")
    with open(csv4_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["SentinelType", "EvaluationSet", "Accuracy", "ROC_AUC", "AUC_CI_95_Low", "AUC_CI_95_High", "ChanceBaseline", "LeakageDetected"])
        for name, eval_set, res in [
            ("L1_Metadata_Form", "VAL_IN_DISTRIBUTION", l1_res_id),
            ("L1_Metadata_Form", "VAL_HELD_OUT_OOD", l1_res_ood),
            ("L2_Lexical_BagOfWords", "VAL_IN_DISTRIBUTION", l2_res_id),
            ("L2_Lexical_BagOfWords", "VAL_HELD_OUT_OOD", l2_res_ood),
        ]:
            writer.writerow([
                name, eval_set, f"{res['accuracy']:.4f}", f"{res['auc']:.4f}",
                f"{res['auc_ci_95'][0]:.4f}", f"{res['auc_ci_95'][1]:.4f}", "0.5000",
                "YES" if res["leakage_detected"] else "NO"
            ])

    print("=== LEAKAGE SENTINEL AUDIT ===")
    print("L1 Metadata/Form on Val ID:", l1_res_id)
    print("L2 Lexical BoW on Val ID:", l2_res_id)

    return {
        "train_count": len(train_claims),
        "val_id_count": len(val_id_claims),
        "val_ood_count": len(val_ood_claims),
        "oracle_results": oracle_results,
        "l1_results": l1_res_id,
        "l2_results": l2_res_id
    }

if __name__ == "__main__":
    run_p4_audit()
