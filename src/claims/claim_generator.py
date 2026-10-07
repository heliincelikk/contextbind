"""
ContextBind — Controlled Temporal Claim Generation Engine (Phase P4 Curated)
Extracts authentic longitudinal evidence from SQLite and constructs balanced, paired natural-language claims.
Strictly uses Python Standard Library.
"""

import os
import sqlite3
import json
import random
import hashlib
from collections import defaultdict
from typing import Dict, Any, List, Tuple

def get_stable_pair_hash(seed: int, pair_id: str) -> str:
    raw = f"{seed}_{pair_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

class TemporalClaimGenerator:
    def __init__(self, db_path: str, split_config_path: str, seed: int = 20261004):
        self.db_path = db_path
        self.split_config_path = split_config_path
        self.seed = seed
        self.rng = random.Random(seed)
        
        with open(split_config_path, "r", encoding="utf-8") as f:
            self.split_data = json.load(f)
            
        self.train_pids = set(self.split_data["train_patient_ids"])
        self.val_pids = set(self.split_data["val_patient_ids"])
        self.test_pids = set(self.split_data.get("test_patient_ids", []))

    def _connect(self):
        return sqlite3.connect(self.db_path)

    # ==========================================
    # Task S1: Trend Direction (3-point monotonic)
    # ==========================================
    def generate_s1_trend_claims(self, pids: set, max_pairs_per_concept: int = 5) -> List[Dict[str, Any]]:
        conn = self._connect()
        cursor = conn.cursor()
        claims = []

        placeholders = ",".join(["?"] * len(pids))
        query = f"""
        SELECT patient_id, clinical_code, clinical_display, value_numeric, unit, event_time_norm, event_time_epoch, resource_id
        FROM timeline_events
        WHERE patient_id IN ({placeholders})
          AND resource_type = 'Observation'
          AND value_numeric IS NOT NULL
          AND is_post_death_event = 0
          AND clinical_code != ''
          AND clinical_display IS NOT NULL
          AND TRIM(clinical_display) != ''
        ORDER BY patient_id, clinical_code, event_time_epoch ASC, resource_id ASC
        """
        cursor.execute(query, list(pids))
        rows = cursor.fetchall()
        conn.close()

        # Group by (patient_id, clinical_code)
        grouped = {}
        for r in rows:
            key = (r[0], r[1])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(r)

        # Templates with grammatically exact articles
        templates_in = [
            ("S1_TF1_ACTIVE", "The {concept} level has {dir_past} across the last 3 measurements."),
            ("S1_TF2_TRAJECTORY", "Over the preceding 3 tests, {concept} shows {dir_adj_with_art} trajectory."),
            ("S1_TF3_COURSE", "{concept} has exhibited {dir_course_with_art} course over recent visits.")
        ]
        template_ood = ("S1_TF4_PASSIVE_HELD_OUT", "{dir_prog_with_art} progression is demonstrated in the patient's {concept} across the prior 3 evaluations.")
        templates_all = templates_in + [template_ood]

        for (pid, code), obs_list in grouped.items():
            if len(obs_list) < 3:
                continue
            
            pairs_created = 0
            for i in range(len(obs_list) - 2):
                if pairs_created >= max_pairs_per_concept:
                    break
                w = obs_list[i:i+3]
                v1, v2, v3 = w[0][3], w[1][3], w[2][3]
                
                # Check strict monotonicity
                true_trend = None
                if v1 < v2 < v3:
                    true_trend = "INCREASING"
                elif v1 > v2 > v3:
                    true_trend = "DECREASING"
                else:
                    continue

                display_name = w[0][2] or "Observation"
                concept_clean = display_name.split("[")[0].strip()

                tf_name, tf_str = self.rng.choice(templates_all)
                is_held_out = (tf_name == "S1_TF4_PASSIVE_HELD_OUT")

                # Direction mappings with exact grammatical articles (guaranteeing 0 "an decreasing" or "a increasing")
                lex_map = {
                    "INCREASING": {
                        "dir_past": "increased",
                        "dir_adj_with_art": "an increasing",
                        "dir_course_with_art": "a rising",
                        "dir_prog_with_art": "An increasing"
                    },
                    "DECREASING": {
                        "dir_past": "decreased",
                        "dir_adj_with_art": "a decreasing",
                        "dir_course_with_art": "a downward",
                        "dir_prog_with_art": "A decreasing"
                    }
                }
                false_trend = "DECREASING" if true_trend == "INCREASING" else "INCREASING"
                pair_id = f"S1_{pid}_{code}_{i}"

                # 1. Supported Claim
                text_sup = tf_str.format(concept=concept_clean, **lex_map[true_trend])
                claims.append({
                    "task_code": "S1",
                    "pair_id": pair_id,
                    "patient_id": pid,
                    "clinical_code": code,
                    "clinical_display": display_name,
                    "template_family": tf_name,
                    "is_held_out_template": is_held_out,
                    "claim_text": text_sup,
                    "ground_truth": "SUPPORTED",
                    "structured_predicate": {
                        "concept": code,
                        "claim_type": f"TREND_{true_trend}",
                        "window": "LAST_3",
                        "comparator": "GT" if true_trend == "INCREASING" else "LT",
                        "claimed_direction": true_trend
                    },
                    "source_event_ids": [w[0][7], w[1][7], w[2][7]],
                    "source_values": [v1, v2, v3],
                    "source_timestamps": [w[0][5], w[1][5], w[2][5]]
                })

                # 2. Contradicted Counterfactual Claim
                text_con = tf_str.format(concept=concept_clean, **lex_map[false_trend])
                claims.append({
                    "task_code": "S1",
                    "pair_id": pair_id,
                    "patient_id": pid,
                    "clinical_code": code,
                    "clinical_display": display_name,
                    "template_family": tf_name,
                    "is_held_out_template": is_held_out,
                    "claim_text": text_con,
                    "ground_truth": "CONTRADICTED",
                    "structured_predicate": {
                        "concept": code,
                        "claim_type": f"TREND_{false_trend}",
                        "window": "LAST_3",
                        "comparator": "GT" if false_trend == "INCREASING" else "LT",
                        "claimed_direction": false_trend
                    },
                    "source_event_ids": [w[0][7], w[1][7], w[2][7]],
                    "source_values": [v1, v2, v3],
                    "source_timestamps": [w[0][5], w[1][5], w[2][5]]
                })

                pairs_created += 1

        return claims

    # ==========================================
    # Task S2: Before / After Temporal Relation
    # ==========================================
    def generate_s2_relation_claims(self, pids: set, max_pairs_per_patient: int = 8) -> List[Dict[str, Any]]:
        conn = self._connect()
        cursor = conn.cursor()
        claims = []

        placeholders = ",".join(["?"] * len(pids))
        query = f"""
        SELECT patient_id, resource_type, resource_id, clinical_code, clinical_display, event_time_norm, event_time_epoch
        FROM timeline_events
        WHERE patient_id IN ({placeholders})
          AND is_post_death_event = 0
          AND clinical_display IS NOT NULL
          AND TRIM(clinical_display) != ''
        ORDER BY patient_id, event_time_epoch ASC
        """
        cursor.execute(query, list(pids))
        rows = cursor.fetchall()
        conn.close()

        by_patient = {}
        for r in rows:
            pid = r[0]
            if pid not in by_patient:
                by_patient[pid] = []
            by_patient[pid].append(r)

        templates_in = [
            ("S2_TF1_STANDARD", "{event_A} was recorded {rel} {event_B}."),
            ("S2_TF2_SEQUENCE", "{event_A} occurred {rel_seq} {event_B}."),
            ("S2_TF3_DOCUMENTATION", "The documentation of {event_A} {rel_verb} {event_B}.")
        ]
        template_ood = ("S2_TF4_CLAUSAL_HELD_OUT", "{event_A} took place {rel_clausal} {event_B}.")
        templates_all = templates_in + [template_ood]

        for pid, ev_list in by_patient.items():
            if len(ev_list) < 2:
                continue
            
            pairs_created = 0
            for i in range(len(ev_list) - 1):
                if pairs_created >= max_pairs_per_patient:
                    break
                eA, eB = ev_list[i], ev_list[i+1]
                if eA[6] == eB[6] or eA[4] == eB[4] or eA[2] == eB[2]:
                    continue

                nameA = eA[4].split("[")[0].strip() if eA[4] else ""
                nameB = eB[4].split("[")[0].strip() if eB[4] else ""
                if not nameA or not nameB or nameA == nameB:
                    continue

                tf_name, tf_str = self.rng.choice(templates_all)
                is_held_out = (tf_name == "S2_TF4_CLAUSAL_HELD_OUT")

                lex_before = {"rel": "before", "rel_seq": "prior to", "rel_verb": "preceded", "rel_clausal": "earlier than"}
                lex_after = {"rel": "after", "rel_seq": "following", "rel_verb": "succeeded", "rel_clausal": "subsequent to"}
                pair_id = f"S2_{pid}_{i}"

                # Deterministically balance direction (A before B vs B after A) to eliminate lexical shortcut
                if i % 2 == 0:
                    # 1. Supported (A before B)
                    text_sup = tf_str.format(event_A=nameA, event_B=nameB, **lex_before)
                    claims.append({
                        "task_code": "S2",
                        "pair_id": pair_id,
                        "patient_id": pid,
                        "clinical_code": f"{eA[3]}_vs_{eB[3]}",
                        "clinical_display": f"{nameA} vs {nameB}",
                        "template_family": tf_name,
                        "is_held_out_template": is_held_out,
                        "claim_text": text_sup,
                        "ground_truth": "SUPPORTED",
                        "structured_predicate": {
                            "event_A_id": eA[2],
                            "event_B_id": eB[2],
                            "claim_type": "BEFORE",
                            "comparator": "LT"
                        },
                        "source_event_ids": [eA[2], eB[2]],
                        "source_values": [None, None],
                        "source_timestamps": [eA[5], eB[5]]
                    })

                    # 2. Contradicted (A after B)
                    text_con = tf_str.format(event_A=nameA, event_B=nameB, **lex_after)
                    claims.append({
                        "task_code": "S2",
                        "pair_id": pair_id,
                        "patient_id": pid,
                        "clinical_code": f"{eA[3]}_vs_{eB[3]}",
                        "clinical_display": f"{nameA} vs {nameB}",
                        "template_family": tf_name,
                        "is_held_out_template": is_held_out,
                        "claim_text": text_con,
                        "ground_truth": "CONTRADICTED",
                        "structured_predicate": {
                            "event_A_id": eA[2],
                            "event_B_id": eB[2],
                            "claim_type": "AFTER",
                            "comparator": "GT"
                        },
                        "source_event_ids": [eA[2], eB[2]],
                        "source_values": [None, None],
                        "source_timestamps": [eA[5], eB[5]]
                    })
                else:
                    # 1. Supported (B after A)
                    text_sup = tf_str.format(event_A=nameB, event_B=nameA, **lex_after)
                    claims.append({
                        "task_code": "S2",
                        "pair_id": pair_id,
                        "patient_id": pid,
                        "clinical_code": f"{eB[3]}_vs_{eA[3]}",
                        "clinical_display": f"{nameB} vs {nameA}",
                        "template_family": tf_name,
                        "is_held_out_template": is_held_out,
                        "claim_text": text_sup,
                        "ground_truth": "SUPPORTED",
                        "structured_predicate": {
                            "event_A_id": eB[2],
                            "event_B_id": eA[2],
                            "claim_type": "AFTER",
                            "comparator": "GT"
                        },
                        "source_event_ids": [eB[2], eA[2]],
                        "source_values": [None, None],
                        "source_timestamps": [eB[5], eA[5]]
                    })

                    # 2. Contradicted (B before A)
                    text_con = tf_str.format(event_A=nameB, event_B=nameA, **lex_before)
                    claims.append({
                        "task_code": "S2",
                        "pair_id": pair_id,
                        "patient_id": pid,
                        "clinical_code": f"{eB[3]}_vs_{eA[3]}",
                        "clinical_display": f"{nameB} vs {nameA}",
                        "template_family": tf_name,
                        "is_held_out_template": is_held_out,
                        "claim_text": text_con,
                        "ground_truth": "CONTRADICTED",
                        "structured_predicate": {
                            "event_A_id": eB[2],
                            "event_B_id": eA[2],
                            "claim_type": "BEFORE",
                            "comparator": "LT"
                        },
                        "source_event_ids": [eB[2], eA[2]],
                        "source_values": [None, None],
                        "source_timestamps": [eB[5], eA[5]]
                    })

                pairs_created += 1

        return claims

    # ==========================================
    # Task S3: Latest vs Previous Comparison
    # ==========================================
    def generate_s3_comparison_claims(self, pids: set, max_pairs_per_concept: int = 5) -> List[Dict[str, Any]]:
        conn = self._connect()
        cursor = conn.cursor()
        claims = []

        placeholders = ",".join(["?"] * len(pids))
        query = f"""
        SELECT patient_id, clinical_code, clinical_display, value_numeric, unit, event_time_norm, event_time_epoch, resource_id
        FROM timeline_events
        WHERE patient_id IN ({placeholders})
          AND resource_type = 'Observation'
          AND value_numeric IS NOT NULL
          AND is_post_death_event = 0
          AND clinical_code != ''
          AND clinical_display IS NOT NULL
          AND TRIM(clinical_display) != ''
        ORDER BY patient_id, clinical_code, event_time_epoch ASC, resource_id ASC
        """
        cursor.execute(query, list(pids))
        rows = cursor.fetchall()
        conn.close()

        grouped = {}
        for r in rows:
            key = (r[0], r[1])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(r)

        templates_in = [
            ("S3_TF1_COMPARATIVE_ADJ", "The latest {concept} reading is {comp_adj} than the previous measurement."),
            ("S3_TF2_EXCEEDS_FALLS", "The most recent {concept} {comp_verb} the prior value."),
            ("S3_TF3_ENCOUNTER_SHIFT", "Compared to the preceding encounter, the current {concept} is {comp_shift}.")
        ]
        template_ood = ("S3_TF4_MAGNITUDE_HELD_OUT", "The current measurement of {concept} is {comp_mag} the value from the prior evaluation.")
        templates_all = templates_in + [template_ood]

        for (pid, code), obs_list in grouped.items():
            if len(obs_list) < 2:
                continue
            
            pairs_created = 0
            for i in range(len(obs_list) - 1):
                if pairs_created >= max_pairs_per_concept:
                    break
                o_prev, o_latest = obs_list[i], obs_list[i+1]
                v_prev, v_latest = o_prev[3], o_latest[3]

                if v_latest == v_prev:
                    continue

                true_rel = "HIGHER" if v_latest > v_prev else "LOWER"
                false_rel = "LOWER" if true_rel == "HIGHER" else "HIGHER"

                display_name = o_latest[2] or "Observation"
                concept_clean = display_name.split("[")[0].strip()
                if not concept_clean:
                    continue

                tf_name, tf_str = self.rng.choice(templates_all)
                is_held_out = (tf_name == "S3_TF4_MAGNITUDE_HELD_OUT")

                lex_map = {
                    "HIGHER": {"comp_adj": "higher", "comp_verb": "exceeds", "comp_shift": "elevated", "comp_mag": "greater than"},
                    "LOWER": {"comp_adj": "lower", "comp_verb": "falls below", "comp_shift": "reduced", "comp_mag": "less than"}
                }
                pair_id = f"S3_{pid}_{code}_{i}"

                # 1. Supported
                text_sup = tf_str.format(concept=concept_clean, **lex_map[true_rel])
                claims.append({
                    "task_code": "S3",
                    "pair_id": pair_id,
                    "patient_id": pid,
                    "clinical_code": code,
                    "clinical_display": display_name,
                    "template_family": tf_name,
                    "is_held_out_template": is_held_out,
                    "claim_text": text_sup,
                    "ground_truth": "SUPPORTED",
                    "structured_predicate": {
                        "concept": code,
                        "claim_type": f"{true_rel}_THAN_PREVIOUS",
                        "comparator": "GT" if true_rel == "HIGHER" else "LT"
                    },
                    "source_event_ids": [o_prev[7], o_latest[7]],
                    "source_values": [v_prev, v_latest],
                    "source_timestamps": [o_prev[5], o_latest[5]]
                })

                # 2. Contradicted
                text_con = tf_str.format(concept=concept_clean, **lex_map[false_rel])
                claims.append({
                    "task_code": "S3",
                    "pair_id": pair_id,
                    "patient_id": pid,
                    "clinical_code": code,
                    "clinical_display": display_name,
                    "template_family": tf_name,
                    "is_held_out_template": is_held_out,
                    "claim_text": text_con,
                    "ground_truth": "CONTRADICTED",
                    "structured_predicate": {
                        "concept": code,
                        "claim_type": f"{false_rel}_THAN_PREVIOUS",
                        "comparator": "GT" if false_rel == "HIGHER" else "LT"
                    },
                    "source_event_ids": [o_prev[7], o_latest[7]],
                    "source_values": [v_prev, v_latest],
                    "source_timestamps": [o_prev[5], o_latest[5]]
                })

                pairs_created += 1

        return claims

    # ==========================================
    # Task S4: Latest / Current Claim
    # ==========================================
    def generate_s4_current_claims(self, pids: set, max_pairs_per_concept: int = 5) -> List[Dict[str, Any]]:
        conn = self._connect()
        cursor = conn.cursor()
        claims = []

        placeholders = ",".join(["?"] * len(pids))
        query = f"""
        SELECT patient_id, clinical_code, clinical_display, value_numeric, unit, event_time_norm, event_time_epoch, resource_id
        FROM timeline_events
        WHERE patient_id IN ({placeholders})
          AND resource_type = 'Observation'
          AND value_numeric IS NOT NULL
          AND is_post_death_event = 0
          AND clinical_code != ''
          AND clinical_display IS NOT NULL
          AND TRIM(clinical_display) != ''
        ORDER BY patient_id, clinical_code, event_time_epoch ASC, resource_id ASC
        """
        cursor.execute(query, list(pids))
        rows = cursor.fetchall()
        conn.close()

        grouped = {}
        for r in rows:
            key = (r[0], r[1])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(r)

        templates_in = [
            ("S4_TF1_DIRECT_CURRENT", "The patient's current {concept} is {val} {unit}."),
            ("S4_TF2_MOST_RECENT", "The most recently documented {concept} is {val} {unit}."),
            ("S4_TF3_RECORDED_FINDING", "Latest recorded {concept} stands at {val} {unit}.")
        ]
        template_ood = ("S4_TF4_ACTIVE_STATE_HELD_OUT", "As of the current evaluation, the active {concept} measurement is {val} {unit}.")
        templates_all = templates_in + [template_ood]

        for (pid, code), obs_list in grouped.items():
            if len(obs_list) < 2:
                continue
            
            pairs_created = 0
            for i in range(len(obs_list) - 1):
                if pairs_created >= max_pairs_per_concept:
                    break
                o_stale = obs_list[i]
                o_latest = obs_list[-1]
                
                if o_stale[3] == o_latest[3]:
                    continue

                display_name = o_latest[2] or "Observation"
                concept_clean = display_name.split("[")[0].strip()
                unit_str = o_latest[4] or ""

                tf_name, tf_str = self.rng.choice(templates_all)
                is_held_out = (tf_name == "S4_TF4_ACTIVE_STATE_HELD_OUT")
                pair_id = f"S4_{pid}_{code}_{i}"

                # 1. Supported (Asserts latest)
                text_sup = tf_str.format(concept=concept_clean, val=o_latest[3], unit=unit_str)
                claims.append({
                    "task_code": "S4",
                    "pair_id": pair_id,
                    "patient_id": pid,
                    "clinical_code": code,
                    "clinical_display": display_name,
                    "template_family": tf_name,
                    "is_held_out_template": is_held_out,
                    "claim_text": text_sup,
                    "ground_truth": "SUPPORTED",
                    "structured_predicate": {
                        "concept": code,
                        "claim_type": "CURRENT_VALUE",
                        "claimed_value": o_latest[3]
                    },
                    "source_event_ids": [o_stale[7], o_latest[7]],
                    "source_values": [o_stale[3], o_latest[3]],
                    "source_timestamps": [o_stale[5], o_latest[5]]
                })

                # 2. Contradicted (Asserts stale historical value)
                text_con = tf_str.format(concept=concept_clean, val=o_stale[3], unit=unit_str)
                claims.append({
                    "task_code": "S4",
                    "pair_id": pair_id,
                    "patient_id": pid,
                    "clinical_code": code,
                    "clinical_display": display_name,
                    "template_family": tf_name,
                    "is_held_out_template": is_held_out,
                    "claim_text": text_con,
                    "ground_truth": "CONTRADICTED",
                    "structured_predicate": {
                        "concept": code,
                        "claim_type": "CURRENT_VALUE",
                        "claimed_value": o_stale[3]
                    },
                    "source_event_ids": [o_stale[7], o_latest[7]],
                    "source_values": [o_stale[3], o_latest[3]],
                    "source_timestamps": [o_stale[5], o_latest[5]]
                })

                pairs_created += 1

        return claims

    # ==========================================
    # Curated Partition Subsampler
    # ==========================================
    def sample_counterfactual_pairs(self, raw_claims: List[Dict[str, Any]], max_pairs: int, seed_suffix: str = "") -> List[Dict[str, Any]]:
        # Group by pair_id
        pairs = defaultdict(list)
        for c in raw_claims:
            pairs[c["pair_id"]].append(c)
        
        # Valid pairs must have exactly 1 SUPPORTED and 1 CONTRADICTED
        valid_pair_ids = [pid for pid, cl in pairs.items() if len(cl) == 2 and {cl[0]["ground_truth"], cl[1]["ground_truth"]} == {"SUPPORTED", "CONTRADICTED"}]
        
        # Stable deterministic sort by hash(seed + pair_id)
        valid_pair_ids.sort(key=lambda pid: get_stable_pair_hash(self.seed, pid))
        
        selected_pids = valid_pair_ids[:max_pairs]
        curated_claims = []
        for pid in selected_pids:
            curated_claims.extend(pairs[pid])
            
        return curated_claims

    def generate_curated_benchmark(self, max_train_pairs: int = 2500, max_val_id_pairs: int = 750, max_val_ood_pairs: int = 750) -> Dict[str, List[Dict[str, Any]]]:
        train_claims_final = []
        val_id_claims_final = []
        val_ood_claims_final = []

        for task_code, task_func in [
            ("S1", self.generate_s1_trend_claims),
            ("S2", self.generate_s2_relation_claims),
            ("S3", self.generate_s3_comparison_claims),
            ("S4", self.generate_s4_current_claims)
        ]:
            # 1. Train
            raw_t = task_func(self.train_pids)
            raw_t_in = [c for c in raw_t if not c["is_held_out_template"]]
            sampled_t = self.sample_counterfactual_pairs(raw_t_in, max_train_pairs, seed_suffix=f"{task_code}_TRN")
            train_claims_final.extend(sampled_t)

            # 2. Validation
            raw_v = task_func(self.val_pids)
            raw_v_in = [c for c in raw_v if not c["is_held_out_template"]]
            raw_v_ood = [c for c in raw_v if c["is_held_out_template"]]

            sampled_v_id = self.sample_counterfactual_pairs(raw_v_in, max_val_id_pairs, seed_suffix=f"{task_code}_VID")
            sampled_v_ood = self.sample_counterfactual_pairs(raw_v_ood, max_val_ood_pairs, seed_suffix=f"{task_code}_VOD")

            val_id_claims_final.extend(sampled_v_id)
            val_ood_claims_final.extend(sampled_v_ood)

        return {
            "train": train_claims_final,
            "val_id": val_id_claims_final,
            "val_ood": val_ood_claims_final
        }
