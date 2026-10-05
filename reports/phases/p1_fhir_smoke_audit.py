"""
ContextBind — Phase P1 FHIR R4 Smoke Dataset Feasibility Audit
Strictly uses Python standard library only (no external dependencies).
"""

import os
import glob
import json
import csv
from collections import defaultdict, Counter
import statistics

def audit_fhir_smoke_data(data_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    
    json_files = glob.glob(os.path.join(data_dir, "**", "*.json"), recursive=True)
    
    patient_files = []
    other_files = []
    
    # Classify files
    for fpath in json_files:
        fname = os.path.basename(fpath)
        if fname.startswith("hospitalInformation") or fname.startswith("practitionerInformation"):
            other_files.append(fpath)
        else:
            patient_files.append(fpath)
            
    print(f"Total JSON files: {len(json_files)}")
    print(f"Patient bundle files: {len(patient_files)}")
    print(f"Other institution files: {len(other_files)}")

    resource_type_counts = Counter()
    total_resources = 0
    
    patient_ids = set()
    encounters_by_patient = defaultdict(list)
    medications_by_patient = defaultdict(list)
    observations_by_patient = defaultdict(list)
    
    # Metrics accumulators
    encounter_start_count = 0
    encounter_end_count = 0
    total_encounters = 0
    
    med_status_counts = Counter()
    med_has_subject = 0
    med_has_encounter = 0
    med_has_authored_on = 0
    med_has_code = 0
    total_medications = 0
    
    obs_has_effective = 0
    obs_has_encounter = 0
    total_observations = 0

    for fpath in patient_files:
        with open(fpath, "r", encoding="utf-8") as f:
            bundle = json.load(f)
            
        entries = bundle.get("entry", [])
        for entry in entries:
            res = entry.get("resource", {})
            rtype = res.get("resourceType", "Unknown")
            resource_type_counts[rtype] += 1
            total_resources += 1
            
            if rtype == "Patient":
                pid = res.get("id")
                if pid:
                    patient_ids.add(pid)
                    
            elif rtype == "Encounter":
                total_encounters += 1
                enc_id = res.get("id")
                subj_ref = res.get("subject", {}).get("reference", "")
                pid = subj_ref.split("/")[-1] if "/" in subj_ref else subj_ref
                
                period = res.get("period", {})
                start_t = period.get("start")
                end_t = period.get("end")
                if start_t:
                    encounter_start_count += 1
                if end_t:
                    encounter_end_count += 1
                    
                encounters_by_patient[pid].append({
                    "id": enc_id,
                    "start": start_t,
                    "end": end_t,
                    "class": res.get("class", {}).get("code"),
                    "type": res.get("type", [{}])[0].get("text", "")
                })
                
            elif rtype == "MedicationRequest":
                total_medications += 1
                status = res.get("status", "unknown")
                med_status_counts[status] += 1
                
                subj_ref = res.get("subject", {}).get("reference", "")
                if subj_ref:
                    med_has_subject += 1
                pid = subj_ref.split("/")[-1] if "/" in subj_ref else subj_ref
                
                enc_ref = res.get("encounter", {}).get("reference", "")
                if enc_ref:
                    med_has_encounter += 1
                    
                authored_on = res.get("authoredOn")
                if authored_on:
                    med_has_authored_on += 1
                    
                # Extract medication code/concept
                med_codeable = res.get("medicationCodeableConcept", {})
                coding = med_codeable.get("coding", [{}])[0]
                code_val = coding.get("code", "")
                display_val = coding.get("display", med_codeable.get("text", "Unknown Med"))
                if code_val or display_val != "Unknown Med":
                    med_has_code += 1
                    
                medications_by_patient[pid].append({
                    "id": res.get("id"),
                    "code": code_val,
                    "display": display_val,
                    "status": status,
                    "authoredOn": authored_on,
                    "encounter_ref": enc_ref
                })
                
            elif rtype == "Observation":
                total_observations += 1
                subj_ref = res.get("subject", {}).get("reference", "")
                pid = subj_ref.split("/")[-1] if "/" in subj_ref else subj_ref
                
                enc_ref = res.get("encounter", {}).get("reference", "")
                if enc_ref:
                    obs_has_encounter += 1
                    
                eff_dt = res.get("effectiveDateTime") or res.get("effectivePeriod", {}).get("start")
                if eff_dt:
                    obs_has_effective += 1
                    
                obs_codeable = res.get("code", {})
                coding = obs_codeable.get("coding", [{}])[0]
                code_val = coding.get("code", "")
                display_val = coding.get("display", obs_codeable.get("text", "Unknown Obs"))
                
                observations_by_patient[pid].append({
                    "id": res.get("id"),
                    "code": code_val,
                    "display": display_val,
                    "effectiveDateTime": eff_dt,
                    "encounter_ref": enc_ref,
                    "value": res.get("valueQuantity", {}).get("value", res.get("valueString", ""))
                })

    # Encounter Distribution per patient
    enc_counts_per_patient = [len(enc_list) for enc_list in encounters_by_patient.values()]
    if enc_counts_per_patient:
        enc_min = min(enc_counts_per_patient)
        enc_max = max(enc_counts_per_patient)
        enc_mean = statistics.mean(enc_counts_per_patient)
        enc_median = statistics.median(enc_counts_per_patient)
    else:
        enc_min = enc_max = enc_mean = enc_median = 0
        
    pts_ge_2_enc = sum(1 for c in enc_counts_per_patient if c >= 2)
    pts_ge_3_enc = sum(1 for c in enc_counts_per_patient if c >= 3)
    
    # Longitudinal Medication Analysis
    med_longitudinal_groups = []
    for pid, meds in medications_by_patient.items():
        # group by medication code
        by_code = defaultdict(list)
        for m in meds:
            if m["code"]:
                by_code[m["code"]].append(m)
        for code, group in by_code.items():
            if len(group) >= 2:
                # Sort chronologically by authoredOn
                sorted_group = sorted(group, key=lambda x: x["authoredOn"] or "")
                med_longitudinal_groups.append({
                    "patient_id": pid,
                    "medication_code": code,
                    "medication_display": group[0]["display"],
                    "count": len(group),
                    "statuses": [m["status"] for m in sorted_group],
                    "authoredOns": [m["authoredOn"] for m in sorted_group],
                    "encounter_refs": [m["encounter_ref"] for m in sorted_group]
                })

    # Longitudinal Observation Analysis
    obs_groups_ge_2 = 0
    obs_groups_ge_3 = 0
    total_obs_code_groups = 0
    
    for pid, obs_list in observations_by_patient.items():
        by_code = defaultdict(list)
        for o in obs_list:
            if o["code"]:
                by_code[o["code"]].append(o)
        for code, group in by_code.items():
            total_obs_code_groups += 1
            if len(group) >= 2:
                obs_groups_ge_2 += 1
            if len(group) >= 3:
                obs_groups_ge_3 += 1

    # Save CSV 1: Resource Counts
    csv1_path = os.path.join(output_dir, "P1_RESOURCE_COUNTS.csv")
    with open(csv1_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ResourceType", "Count", "Percentage"])
        for rtype, count in resource_type_counts.most_common():
            pct = (count / total_resources * 100) if total_resources else 0
            writer.writerow([rtype, count, f"{pct:.2f}%"])
            
    # Save CSV 2: Medication Status Counts
    csv2_path = os.path.join(output_dir, "P1_MEDICATION_STATUS_COUNTS.csv")
    with open(csv2_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Status", "Count", "Percentage"])
        for status, count in med_status_counts.most_common():
            pct = (count / total_medications * 100) if total_medications else 0
            writer.writerow([status, count, f"{pct:.2f}%"])
            
    # Save CSV 3: Longitudinal Feasibility Summary
    csv3_path = os.path.join(output_dir, "P1_LONGITUDINAL_FEASIBILITY.csv")
    with open(csv3_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "Value", "Description"])
        writer.writerow(["Total Patients Generated", len(patient_ids), "Unique patient IDs in cohort"])
        writer.writerow(["Patients with >=2 Encounters", pts_ge_2_enc, f"{pts_ge_2_enc/len(patient_ids)*100:.1f}% of cohort"])
        writer.writerow(["Patients with >=3 Encounters", pts_ge_3_enc, f"{pts_ge_3_enc/len(patient_ids)*100:.1f}% of cohort"])
        writer.writerow(["Encounter Count Min", enc_min, "Min encounters per patient"])
        writer.writerow(["Encounter Count Median", enc_median, "Median encounters per patient"])
        writer.writerow(["Encounter Count Mean", f"{enc_mean:.1f}", "Mean encounters per patient"])
        writer.writerow(["Encounter Count Max", enc_max, "Max encounters per patient"])
        writer.writerow(["Encounter Start Coverage", f"{encounter_start_count/total_encounters*100:.1f}%", f"{encounter_start_count}/{total_encounters}"])
        writer.writerow(["Encounter End Coverage", f"{encounter_end_count/total_encounters*100:.1f}%", f"{encounter_end_count}/{total_encounters}"])
        writer.writerow(["Medication Subject Coverage", f"{med_has_subject/total_medications*100:.1f}%", f"{med_has_subject}/{total_medications}"])
        writer.writerow(["Medication Encounter Coverage", f"{med_has_encounter/total_medications*100:.1f}%", f"{med_has_encounter}/{total_medications}"])
        writer.writerow(["Medication AuthoredOn Coverage", f"{med_has_authored_on/total_medications*100:.1f}%", f"{med_has_authored_on}/{total_medications}"])
        writer.writerow(["Medication Repeated Code Groups", len(med_longitudinal_groups), "Pairs/sequences of same medication per patient"])
        writer.writerow(["Observation EffectiveDate Coverage", f"{obs_has_effective/total_observations*100:.1f}%", f"{obs_has_effective}/{total_observations}"])
        writer.writerow(["Observation Encounter Coverage", f"{obs_has_encounter/total_observations*100:.1f}%", f"{obs_has_encounter}/{total_observations}"])
        writer.writerow(["Observation Groups with >=2 Points", obs_groups_ge_2, f"Total (patient, obs_code) with >=2 points"])
        writer.writerow(["Observation Groups with >=3 Points", obs_groups_ge_3, f"Total (patient, obs_code) with >=3 points"])

    # Save JSON: Example Timelines
    json_path = os.path.join(output_dir, "P1_EXAMPLE_TIMELINES.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "sample_medication_transitions": med_longitudinal_groups[:10],
            "total_med_longitudinal_candidates": len(med_longitudinal_groups),
            "total_obs_ge_2_candidates": obs_groups_ge_2,
            "total_obs_ge_3_candidates": obs_groups_ge_3
        }, f, indent=2)

    return {
        "total_files": len(patient_files),
        "total_resources": total_resources,
        "resource_types": dict(resource_type_counts),
        "patient_count": len(patient_ids),
        "total_encounters": total_encounters,
        "encounter_stats": {
            "min": enc_min,
            "median": enc_median,
            "mean": enc_mean,
            "max": enc_max,
            "pts_ge_2": pts_ge_2_enc,
            "pts_ge_3": pts_ge_3_enc,
            "start_cov": encounter_start_count / total_encounters if total_encounters else 0,
            "end_cov": encounter_end_count / total_encounters if total_encounters else 0
        },
        "medication_stats": {
            "total": total_medications,
            "status_dist": dict(med_status_counts),
            "subject_cov": med_has_subject / total_medications if total_medications else 0,
            "encounter_cov": med_has_encounter / total_medications if total_medications else 0,
            "authored_cov": med_has_authored_on / total_medications if total_medications else 0,
            "longitudinal_groups": len(med_longitudinal_groups),
            "examples": med_longitudinal_groups[:5]
        },
        "observation_stats": {
            "total": total_observations,
            "effective_cov": obs_has_effective / total_observations if total_observations else 0,
            "encounter_cov": obs_has_encounter / total_observations if total_observations else 0,
            "groups_ge_2": obs_groups_ge_2,
            "groups_ge_3": obs_groups_ge_3
        }
    }

if __name__ == "__main__":
    raw_dir = r"C:\Users\lenevo\Desktop\contexbind\data\raw\synthea_smoke\fhir"
    out_dir = r"C:\Users\lenevo\Desktop\contexbind\reports\phases"
    results = audit_fhir_smoke_data(raw_dir, out_dir)
    print("\n=== AUDIT COMPLETE ===")
    print(json.dumps(results, indent=2))
