"""
ContextBind — Phase P3 Patient Partitioning & Balance Audit Engine
Strictly deterministic patient-disjoint partitioning with SHA-256 manifest locking.
"""

import os
import sys
import json
import random
import sqlite3
import hashlib
import csv
import statistics

def generate_patient_disjoint_split(patient_ids, seed, train_ratio=0.60, val_ratio=0.20):
    sorted_ids = sorted(list(patient_ids))
    rng = random.Random(seed)
    shuffled = list(sorted_ids)
    rng.shuffle(shuffled)
    
    n = len(shuffled)
    n_train = int(round(n * train_ratio))
    n_val = int(round(n * val_ratio))
    
    train_ids = sorted(shuffled[:n_train])
    val_ids = sorted(shuffled[n_train:n_train + n_val])
    test_ids = sorted(shuffled[n_train + n_val:])
    
    return {
        "split_seed": seed,
        "train_ratio": train_ratio,
        "val_ratio": val_ratio,
        "test_ratio": round(1.0 - train_ratio - val_ratio, 2),
        "total_patients": n,
        "counts": {
            "train": len(train_ids),
            "val": len(val_ids),
            "test": len(test_ids)
        },
        "train_patient_ids": train_ids,
        "val_patient_ids": val_ids,
        "test_patient_ids": test_ids
    }

def audit_split_balance(conn, split_dict):
    cursor = conn.cursor()
    
    split_stats = {}
    for split_name, pid_list in [
        ("TRAIN", split_dict["train_patient_ids"]),
        ("VALIDATION", split_dict["val_patient_ids"]),
        ("TEST", split_dict["test_patient_ids"])
    ]:
        n_patients = len(pid_list)
        placeholders = ",".join(["?"] * n_patients)
        
        # Deceased count
        cursor.execute(f"SELECT COUNT(*) FROM patients WHERE patient_id IN ({placeholders}) AND deceased_date_norm IS NOT NULL", pid_list)
        deceased_count = cursor.fetchone()[0]
        alive_count = n_patients - deceased_count
        
        # Encounters per patient
        cursor.execute(f"SELECT patient_id, COUNT(*) FROM encounters WHERE patient_id IN ({placeholders}) GROUP BY patient_id", pid_list)
        enc_counts = [row[1] for row in cursor.fetchall()]
        median_enc = statistics.median(enc_counts) if enc_counts else 0
        
        # Observations per patient
        cursor.execute(f"SELECT patient_id, COUNT(*) FROM observations WHERE patient_id IN ({placeholders}) GROUP BY patient_id", pid_list)
        obs_counts = [row[1] for row in cursor.fetchall()]
        median_obs = statistics.median(obs_counts) if obs_counts else 0
        
        # Eligible longitudinal groups (>=2 distinct timestamps, post_death excluded)
        cursor.execute(f"""
        SELECT COUNT(*) FROM (
            SELECT o.patient_id, o.code
            FROM observations o
            LEFT JOIN patients p ON o.patient_id = p.patient_id
            WHERE o.patient_id IN ({placeholders})
              AND o.code != ''
              AND o.effective_norm IS NOT NULL
              AND (p.deceased_date_norm IS NULL OR o.effective_epoch <= (SELECT strftime('%s', p.deceased_date_norm)))
            GROUP BY o.patient_id, o.code
            HAVING COUNT(DISTINCT o.effective_norm) >= 2
        )
        """, pid_list)
        longitudinal_groups = cursor.fetchone()[0]
        
        split_stats[split_name] = {
            "patient_count": n_patients,
            "alive_count": alive_count,
            "deceased_count": deceased_count,
            "median_encounters": median_enc,
            "median_observations": median_obs,
            "longitudinal_obs_groups": longitudinal_groups
        }
        
    return split_stats

def main():
    db_path = r"C:\Users\lenevo\Desktop\contexbind\data\interim\contextbind_timeline.sqlite"
    configs_dir = r"C:\Users\lenevo\Desktop\contexbind\configs"
    reports_dir = r"C:\Users\lenevo\Desktop\contexbind\reports\phases"
    
    os.makedirs(configs_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT patient_id FROM patients")
    all_patients = [row[0] for row in cursor.fetchall()]
    print(f"Total cohort patients extracted: {len(all_patients)}")
    
    seeds = [20261004, 20261005, 20261006]
    split_manifests = {}
    split_sha256 = {}
    
    for s in seeds:
        split_data = generate_patient_disjoint_split(all_patients, seed=s)
        fname = f"split_primary_{s}.json" if s == 20261004 else f"split_robustness_{s}.json"
        fpath = os.path.join(configs_dir, fname)
        
        content = json.dumps(split_data, indent=2)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
            
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        split_sha256[fname] = sha
        split_manifests[fname] = (split_data, fpath, sha)
        print(f"Saved {fname} (SHA256: {sha})")

    # Audit Primary Split Balance
    primary_split = split_manifests["split_primary_20261004.json"][0]
    audit_results = audit_split_balance(conn, primary_split)
    
    csv_path = os.path.join(reports_dir, "P3_SPLIT_AUDIT.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Partition", "Patients", "Alive", "Deceased", "MedianEncounters", "MedianObservations", "EligibleLongitudinalObsGroups"])
        for part, stats in audit_results.items():
            writer.writerow([
                part,
                stats["patient_count"],
                stats["alive_count"],
                stats["deceased_count"],
                stats["median_encounters"],
                stats["median_observations"],
                stats["longitudinal_obs_groups"]
            ])
            
    print(f"Split audit saved to {csv_path}")
    conn.close()
    
    return split_sha256, audit_results

if __name__ == "__main__":
    shas, audit = main()
    print("\n=== SPLIT HASHE & AUDIT SUMMARY ===")
    print("SHA256:", json.dumps(shas, indent=2))
    print("AUDIT:", json.dumps(audit, indent=2))
