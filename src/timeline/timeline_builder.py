"""
ContextBind — Longitudinal Timeline Builder & SQLite Storage Engine
Strictly uses Python Standard Library (sqlite3, json, os, glob, hashlib).
Processes canonical FHIR extractions into structured longitudinal patient event timelines.
"""

import os
import glob
import sqlite3
import hashlib
import json
from collections import defaultdict
from typing import Dict, Any, List, Optional
from src.ingestion.fhir_parser import FHIRBundleParser

class TimelineBuilder:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self):
        cursor = self.conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            patient_id TEXT PRIMARY KEY,
            family_name TEXT,
            given_names TEXT,
            gender TEXT,
            birth_date TEXT,
            deceased_date_raw TEXT,
            deceased_date_norm TEXT,
            source_file TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS encounters (
            encounter_id TEXT PRIMARY KEY,
            patient_id TEXT,
            status TEXT,
            class_code TEXT,
            type_code TEXT,
            type_display TEXT,
            start_raw TEXT,
            start_norm TEXT,
            start_epoch REAL,
            end_raw TEXT,
            end_norm TEXT,
            end_epoch REAL,
            source_file TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            observation_id TEXT PRIMARY KEY,
            patient_id TEXT,
            encounter_id TEXT,
            status TEXT,
            code TEXT,
            system TEXT,
            display TEXT,
            effective_raw TEXT,
            effective_norm TEXT,
            effective_epoch REAL,
            effective_type TEXT,
            issued_raw TEXT,
            issued_norm TEXT,
            value_numeric REAL,
            value_text TEXT,
            unit TEXT,
            source_file TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS medication_requests (
            medication_request_id TEXT PRIMARY KEY,
            patient_id TEXT,
            encounter_id TEXT,
            status TEXT,
            intent TEXT,
            code TEXT,
            system TEXT,
            display TEXT,
            authored_raw TEXT,
            authored_norm TEXT,
            authored_epoch REAL,
            source_file TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS conditions (
            condition_id TEXT PRIMARY KEY,
            patient_id TEXT,
            encounter_id TEXT,
            clinical_status TEXT,
            verification_status TEXT,
            code TEXT,
            display TEXT,
            onset_raw TEXT,
            onset_norm TEXT,
            abatement_raw TEXT,
            abatement_norm TEXT,
            source_file TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS provenance (
            provenance_id TEXT PRIMARY KEY,
            target_references TEXT,
            recorded_raw TEXT,
            recorded_norm TEXT,
            recorded_epoch REAL,
            agent_display TEXT,
            source_file TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS timeline_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT,
            resource_type TEXT,
            resource_id TEXT,
            encounter_id TEXT,
            clinical_code TEXT,
            clinical_display TEXT,
            event_time_raw TEXT,
            event_time_norm TEXT,
            event_time_epoch REAL,
            value_numeric REAL,
            value_text TEXT,
            unit TEXT,
            status TEXT,
            source_file TEXT,
            is_post_death_event INTEGER,
            FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
        )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timeline_patient ON timeline_events(patient_id, event_time_epoch)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_obs_patient_code ON observations(patient_id, code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_med_patient_code ON medication_requests(patient_id, code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_enc_patient ON encounters(patient_id)")
        
        self.conn.commit()

    def process_cohort_directory(self, raw_fhir_dir: str) -> Dict[str, Any]:
        parser = FHIRBundleParser()
        json_files = glob.glob(os.path.join(raw_fhir_dir, "**", "*.json"), recursive=True)
        
        patient_files = []
        raw_hashes = []
        
        for fpath in json_files:
            fname = os.path.basename(fpath)
            # Compute SHA-256
            with open(fpath, "rb") as f:
                h = hashlib.sha256(f.read()).hexdigest()
            raw_hashes.append((fname, h, os.path.getsize(fpath)))
            
            if not (fname.startswith("hospitalInformation") or fname.startswith("practitionerInformation")):
                patient_files.append(fpath)

        cursor = self.conn.cursor()
        
        total_patients = 0
        total_encounters = 0
        total_observations = 0
        total_medications = 0
        total_conditions = 0
        total_provenance = 0
        total_timeline_events = 0
        post_death_events_count = 0
        
        orphan_encounters = 0
        orphan_observations = 0
        orphan_medications = 0

        patient_death_epochs = {}

        # Step 1: Parse and insert all patient records first
        parsed_bundles = []
        for pfile in patient_files:
            res = parser.parse_bundle_file(pfile)
            parsed_bundles.append(res)
            
            pat = res.get("patient")
            if pat:
                total_patients += 1
                cursor.execute("""
                INSERT OR REPLACE INTO patients VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pat["patient_id"], pat["family_name"], pat["given_names"],
                    pat["gender"], pat["birth_date"], pat["deceased_date_raw"],
                    pat["deceased_date_norm"], pat["source_file"]
                ))
                
                if pat["deceased_date_norm"]:
                    from src.ingestion.fhir_parser import parse_iso_timestamp
                    _, death_epoch = parse_iso_timestamp(pat["deceased_date_norm"])
                    patient_death_epochs[pat["patient_id"]] = death_epoch

        # Step 2: Insert encounters, observations, medications, and build unified timeline
        for res in parsed_bundles:
            pat = res.get("patient")
            pid = pat["patient_id"] if pat else None
            death_epoch = patient_death_epochs.get(pid)

            # Encounters
            known_enc_ids = set()
            for enc in res.get("encounters", []):
                total_encounters += 1
                known_enc_ids.add(enc["encounter_id"])
                cursor.execute("""
                INSERT OR REPLACE INTO encounters VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    enc["encounter_id"], enc["patient_id"], enc["status"], enc["class_code"],
                    enc["type_code"], enc["type_display"], enc["start_raw"], enc["start_norm"],
                    enc["start_epoch"], enc["end_raw"], enc["end_norm"], enc["end_epoch"],
                    enc["source_file"]
                ))
                
                # Add Encounter Start Event to timeline
                is_post_death = 1 if (death_epoch and enc["start_epoch"] and enc["start_epoch"] > death_epoch) else 0
                if is_post_death:
                    post_death_events_count += 1
                    
                cursor.execute("""
                INSERT INTO timeline_events (patient_id, resource_type, resource_id, encounter_id, clinical_code, clinical_display, event_time_raw, event_time_norm, event_time_epoch, value_numeric, value_text, unit, status, source_file, is_post_death_event)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    enc["patient_id"], "Encounter", enc["encounter_id"], enc["encounter_id"],
                    enc["type_code"], enc["type_display"] or "Encounter", enc["start_raw"],
                    enc["start_norm"], enc["start_epoch"], None, None, None, enc["status"],
                    enc["source_file"], is_post_death
                ))
                total_timeline_events += 1

            # Observations
            for obs in res.get("observations", []):
                total_observations += 1
                if obs["encounter_id"] and obs["encounter_id"] not in known_enc_ids:
                    orphan_observations += 1
                    
                cursor.execute("""
                INSERT OR REPLACE INTO observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    obs["observation_id"], obs["patient_id"], obs["encounter_id"], obs["status"],
                    obs["code"], obs["system"], obs["display"], obs["effective_raw"], obs["effective_norm"],
                    obs["effective_epoch"], obs["effective_type"], obs["issued_raw"], obs["issued_norm"],
                    obs["value_numeric"], obs["value_text"], obs["unit"], obs["source_file"]
                ))
                
                is_post_death = 1 if (death_epoch and obs["effective_epoch"] and obs["effective_epoch"] > death_epoch) else 0
                if is_post_death:
                    post_death_events_count += 1
                    
                cursor.execute("""
                INSERT INTO timeline_events (patient_id, resource_type, resource_id, encounter_id, clinical_code, clinical_display, event_time_raw, event_time_norm, event_time_epoch, value_numeric, value_text, unit, status, source_file, is_post_death_event)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    obs["patient_id"], "Observation", obs["observation_id"], obs["encounter_id"],
                    obs["code"], obs["display"], obs["effective_raw"], obs["effective_norm"],
                    obs["effective_epoch"], obs["value_numeric"], obs["value_text"], obs["unit"],
                    obs["status"], obs["source_file"], is_post_death
                ))
                total_timeline_events += 1

            # Medications
            for med in res.get("medication_requests", []):
                total_medications += 1
                if med["encounter_id"] and med["encounter_id"] not in known_enc_ids:
                    orphan_medications += 1
                    
                cursor.execute("""
                INSERT OR REPLACE INTO medication_requests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    med["medication_request_id"], med["patient_id"], med["encounter_id"], med["status"],
                    med["intent"], med["code"], med["system"], med["display"], med["authored_raw"],
                    med["authored_norm"], med["authored_epoch"], med["source_file"]
                ))
                
                is_post_death = 1 if (death_epoch and med["authored_epoch"] and med["authored_epoch"] > death_epoch) else 0
                if is_post_death:
                    post_death_events_count += 1
                    
                cursor.execute("""
                INSERT INTO timeline_events (patient_id, resource_type, resource_id, encounter_id, clinical_code, clinical_display, event_time_raw, event_time_norm, event_time_epoch, value_numeric, value_text, unit, status, source_file, is_post_death_event)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    med["patient_id"], "MedicationRequest", med["medication_request_id"], med["encounter_id"],
                    med["code"], med["display"], med["authored_raw"], med["authored_norm"],
                    med["authored_epoch"], None, None, None, med["status"], med["source_file"], is_post_death
                ))
                total_timeline_events += 1

            # Conditions
            for cond in res.get("conditions", []):
                total_conditions += 1
                cursor.execute("""
                INSERT OR REPLACE INTO conditions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cond["condition_id"], cond["patient_id"], cond["encounter_id"], cond["clinical_status"],
                    cond["verification_status"], cond["code"], cond["display"], cond["onset_raw"],
                    cond["onset_norm"], cond["abatement_raw"], cond["abatement_norm"], cond["source_file"]
                ))

            # Provenance
            for prov in res.get("provenance", []):
                total_provenance += 1
                cursor.execute("""
                INSERT OR REPLACE INTO provenance VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    prov["provenance_id"], prov["target_references"], prov["recorded_raw"],
                    prov["recorded_norm"], prov["recorded_epoch"], prov["agent_display"],
                    prov["source_file"]
                ))

        self.conn.commit()

        return {
            "total_raw_files": len(json_files),
            "patient_bundles": len(patient_files),
            "raw_hashes": raw_hashes,
            "counts": {
                "patients": total_patients,
                "encounters": total_encounters,
                "observations": total_observations,
                "medication_requests": total_medications,
                "conditions": total_conditions,
                "provenance": total_provenance,
                "timeline_events": total_timeline_events
            },
            "anomalies": {
                "post_death_events": post_death_events_count,
                "orphan_observations": orphan_observations,
                "orphan_medications": orphan_medications,
                "parse_errors": len(parser.parse_errors)
            }
        }

    def compute_eligibility_metrics(self) -> Dict[str, Any]:
        cursor = self.conn.cursor()

        # 1. Observation Longitudinal Eligibility (distinct timestamps per patient & code)
        cursor.execute("""
        SELECT patient_id, code, display, COUNT(DISTINCT effective_norm) as distinct_times, 
               COUNT(*) as total_obs,
               SUM(CASE WHEN value_numeric IS NOT NULL THEN 1 ELSE 0 END) as numeric_obs
        FROM observations
        WHERE code != '' AND effective_norm IS NOT NULL
        GROUP BY patient_id, code
        """)
        obs_groups = cursor.fetchall()

        ge_2_points = sum(1 for g in obs_groups if g[3] >= 2)
        ge_3_points = sum(1 for g in obs_groups if g[3] >= 3)
        ge_5_points = sum(1 for g in obs_groups if g[3] >= 5)
        ge_10_points = sum(1 for g in obs_groups if g[3] >= 10)
        numeric_longitudinal = sum(1 for g in obs_groups if g[3] >= 2 and g[5] > 0)

        # 2. T2 Eligibility: patients with >=2 distinct encounters each having >=1 observation
        cursor.execute("""
        SELECT patient_id, COUNT(DISTINCT encounter_id) as enc_with_obs
        FROM observations
        WHERE encounter_id IS NOT NULL AND encounter_id != ''
        GROUP BY patient_id
        HAVING COUNT(DISTINCT encounter_id) >= 2
        """)
        t2_candidates = cursor.fetchall()
        t2_candidate_count = len(t2_candidates)

        # 3. T3 Eligibility: patients with:
        # - >= 2 distinct encounters
        # - >= 2 distinct clinical observation codes
        # - >= 1 observation code with longitudinal recurrence (>=2 distinct times)
        cursor.execute("""
        SELECT patient_id, COUNT(DISTINCT encounter_id) as num_encs, COUNT(DISTINCT code) as num_codes,
               MAX(distinct_times) as max_recurrence
        FROM (
            SELECT patient_id, encounter_id, code, COUNT(DISTINCT effective_norm) as distinct_times
            FROM observations
            WHERE code != '' AND effective_norm IS NOT NULL
            GROUP BY patient_id, code, encounter_id
        )
        GROUP BY patient_id
        HAVING COUNT(DISTINCT encounter_id) >= 2 AND COUNT(DISTINCT code) >= 2 AND MAX(distinct_times) >= 1
        """)
        t3_candidates = cursor.fetchall()
        t3_candidate_count = len(t3_candidates)

        # 4. Medication Semantics Distribution
        cursor.execute("SELECT status, COUNT(*) FROM medication_requests GROUP BY status")
        med_status_dist = dict(cursor.fetchall())

        cursor.execute("""
        SELECT patient_id, code, display, COUNT(*) as order_count, COUNT(DISTINCT authored_norm) as distinct_dates
        FROM medication_requests
        WHERE code != ''
        GROUP BY patient_id, code
        HAVING COUNT(*) >= 2
        """)
        med_repeated_chains = cursor.fetchall()

        return {
            "observation_eligibility": {
                "total_patient_code_groups": len(obs_groups),
                "ge_2_points_t1_candidates": ge_2_points,
                "ge_3_points": ge_3_points,
                "ge_5_points": ge_5_points,
                "ge_10_points": ge_10_points,
                "numeric_longitudinal_groups": numeric_longitudinal
            },
            "t2_candidate_patients": t2_candidate_count,
            "t3_candidate_patients": t3_candidate_count,
            "medication_semantics": {
                "status_distribution": med_status_dist,
                "repeated_order_chains": len(med_repeated_chains)
            }
        }

    def close(self):
        self.conn.close()
