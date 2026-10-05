"""
ContextBind — Curated Benchmark Generator & Diversity / Grammar Audit
Phase P4 Recovery
Strictly uses Python Standard Library.
"""

import os
import sys
import json
import random
import csv
from collections import Counter, defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.claims.claim_generator import TemporalClaimGenerator

def run():
    db_path = "data/interim/contextbind_timeline.sqlite"
    split_path = "configs/split_primary_20261004.json"
    seed = 20261004

    print("[1/5] Initializing TemporalClaimGenerator...")
    gen = TemporalClaimGenerator(db_path, split_path, seed=seed)

    print("[2/5] Generating curated benchmark partitions...")
    benchmark = gen.generate_curated_benchmark(
        max_train_pairs=2500,
        max_val_id_pairs=750,
        max_val_ood_pairs=750
    )

    train_claims = benchmark["train"]
    val_id_claims = benchmark["val_id"]
    val_ood_claims = benchmark["val_ood"]

    print(f"  Train claims:   {len(train_claims)}")
    print(f"  Val-ID claims:  {len(val_id_claims)}")
    print(f"  Val-OOD claims: {len(val_ood_claims)}")
    print(f"  Total claims:   {len(train_claims) + len(val_id_claims) + len(val_ood_claims)}")

    # Write JSONL files
    os.makedirs("data/processed", exist_ok=True)
    os.makedirs("reports/phases", exist_ok=True)

    files_map = {
        "data/processed/p4_final_train.jsonl": train_claims,
        "data/processed/p4_final_val_id.jsonl": val_id_claims,
        "data/processed/p4_final_val_ood.jsonl": val_ood_claims
    }

    for path, claims in files_map.items():
        with open(path, "w", encoding="utf-8") as f:
            for c in claims:
                f.write(json.dumps(c) + "\n")
        print(f"  Wrote {len(claims)} records to {path}")

    all_claims = train_claims + val_id_claims + val_ood_claims

    # [3/5] Grammar Audit
    print("[3/5] Performing Grammar Audit on final dataset...")
    an_dec_count = 0
    a_inc_count = 0
    an_stable_count = 0

    for c in all_claims:
        t = c["claim_text"].lower()
        if "an decreasing" in t:
            an_dec_count += 1
        if "a increasing" in t:
            a_inc_count += 1
        if "an stable" in t:
            an_stable_count += 1

    print(f"  'an decreasing' count: {an_dec_count}")
    print(f"  'a increasing' count:  {a_inc_count}")
    print(f"  'an stable' count:     {an_stable_count}")
    assert an_dec_count == 0, f"Found {an_dec_count} 'an decreasing' violations!"
    assert a_inc_count == 0, f"Found {a_inc_count} 'a increasing' violations!"

    # [4/5] Diversity Audit
    print("[4/5] Performing Diversity Audit...")
    diversity_rows = []
    
    # Task-level diversity
    by_task = defaultdict(list)
    for c in all_claims:
        by_task[c["task_code"]].append(c)

    for task_code in ["S1", "S2", "S3", "S4"]:
        task_cl = by_task[task_code]
        pairs_set = set(c["pair_id"] for c in task_cl)
        pts_set = set(c["patient_id"] for c in task_cl)
        concepts_set = set(c["clinical_code"] for c in task_cl)
        sup_cnt = sum(1 for c in task_cl if c["ground_truth"] == "SUPPORTED")
        con_cnt = sum(1 for c in task_cl if c["ground_truth"] == "CONTRADICTED")
        
        # Patient contributions
        pt_counts = Counter(c["patient_id"] for c in task_cl)
        max_pt_id, max_pt_count = pt_counts.most_common(1)[0] if pt_counts else ("None", 0)
        max_pt_pct = (max_pt_count / len(task_cl)) * 100 if task_cl else 0.0

        # Patient + Concept contributions
        pt_concept_counts = Counter(f"{c['patient_id']}::{c['clinical_code']}" for c in task_cl)
        max_pt_concept, max_pt_concept_count = pt_concept_counts.most_common(1)[0] if pt_concept_counts else ("None", 0)
        max_pt_concept_pct = (max_pt_concept_count / len(task_cl)) * 100 if task_cl else 0.0

        # Template family breakdown
        tf_counts = Counter(c["template_family"] for c in task_cl)

        diversity_rows.append({
            "task_code": task_code,
            "pairs": len(pairs_set),
            "claims": len(task_cl),
            "unique_patients": len(pts_set),
            "unique_concepts": len(concepts_set),
            "supported": sup_cnt,
            "contradicted": con_cnt,
            "max_patient_contrib_claims": max_pt_count,
            "max_patient_contrib_pct": f"{max_pt_pct:.2f}%",
            "max_patient_concept_contrib_claims": max_pt_concept_count,
            "max_patient_concept_contrib_pct": f"{max_pt_concept_pct:.2f}%",
            "template_families": dict(tf_counts)
        })

    # Overall dataset diversity
    overall_pairs = set(c["pair_id"] for c in all_claims)
    overall_pts = set(c["patient_id"] for c in all_claims)
    overall_concepts = set(c["clinical_code"] for c in all_claims)
    overall_pt_counts = Counter(c["patient_id"] for c in all_claims)
    max_pt_id, max_pt_count = overall_pt_counts.most_common(1)[0]
    max_pt_pct = (max_pt_count / len(all_claims)) * 100

    overall_pt_concept_counts = Counter(f"{c['patient_id']}::{c['clinical_code']}" for c in all_claims)
    max_pt_concept, max_pt_concept_count = overall_pt_concept_counts.most_common(1)[0]
    max_pt_concept_pct = (max_pt_concept_count / len(all_claims)) * 100

    diversity_rows.append({
        "task_code": "OVERALL",
        "pairs": len(overall_pairs),
        "claims": len(all_claims),
        "unique_patients": len(overall_pts),
        "unique_concepts": len(overall_concepts),
        "supported": sum(1 for c in all_claims if c["ground_truth"] == "SUPPORTED"),
        "contradicted": sum(1 for c in all_claims if c["ground_truth"] == "CONTRADICTED"),
        "max_patient_contrib_claims": max_pt_count,
        "max_patient_contrib_pct": f"{max_pt_pct:.2f}%",
        "max_patient_concept_contrib_claims": max_pt_concept_count,
        "max_patient_concept_contrib_pct": f"{max_pt_concept_pct:.2f}%",
        "template_families": dict(Counter(c["template_family"] for c in all_claims))
    })

    # Save Diversity CSV
    with open("reports/phases/P4_FINAL_DIVERSITY.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "task_code", "pairs", "claims", "unique_patients", "unique_concepts",
            "supported", "contradicted", "max_patient_contrib_claims",
            "max_patient_contrib_pct", "max_patient_concept_contrib_claims",
            "max_patient_concept_contrib_pct", "template_families"
        ])
        writer.writeheader()
        for r in diversity_rows:
            writer.writerow(r)

    # Save Manifest JSON
    manifest = {
        "dataset_name": "ContextBind_Curated_Temporal_Claims_P4",
        "seed": seed,
        "splits": {
            "train": {"file": "data/processed/p4_final_train.jsonl", "count": len(train_claims)},
            "val_id": {"file": "data/processed/p4_final_val_id.jsonl", "count": len(val_id_claims)},
            "val_ood": {"file": "data/processed/p4_final_val_ood.jsonl", "count": len(val_ood_claims)}
        },
        "total_claims": len(all_claims),
        "grammar_violations": {
            "an_decreasing": an_dec_count,
            "a_increasing": a_inc_count,
            "an_stable": an_stable_count
        },
        "diversity_summary": diversity_rows
    }
    with open("reports/phases/P4_FINAL_DATASET_MANIFEST.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # [5/5] Sample 50 deterministic claims for qualitative review
    print("[5/5] Sampling 50 deterministic claims for review...")
    rng_sample = random.Random(seed)
    sampled_50 = rng_sample.sample(all_claims, 50)
    with open("reports/phases/P4_50_SAMPLED_CLAIMS_AUDIT.md", "w", encoding="utf-8") as f:
        f.write("# ContextBind — Phase P4 Deterministic Quality Audit (50 Sampled Claims)\n\n")
        f.write(f"Sampled deterministically using seed `{seed}` across Train, Val-ID, and Val-OOD.\n\n")
        f.write("| # | Task | Split | Template Family | Ground Truth | Claim Text |\n")
        f.write("|---|---|---|---|---|---|\n")
        for idx, c in enumerate(sampled_50, 1):
            split_label = "TRAIN" if c in train_claims else ("VAL-ID" if c in val_id_claims else "VAL-OOD")
            clean_text = c["claim_text"].replace("|", "\\|")
            f.write(f"| {idx} | {c['task_code']} | {split_label} | {c['template_family']} | `{c['ground_truth']}` | {clean_text} |\n")

    print("[SUCCESS] Curated benchmark generated and audited.")

if __name__ == "__main__":
    run()
