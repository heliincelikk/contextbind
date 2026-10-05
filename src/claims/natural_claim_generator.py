"""
ContextBind — Natural / Open-Vocabulary Claim Generator (Lane B Evaluation)
Constructs open-vocabulary, multi-clause clinical agent justifications from authentic timeline events.
Strictly uses Python Standard Library.
"""

import os
import json
import random
import hashlib
from typing import Dict, Any, List, Tuple
from collections import defaultdict

class NaturalClaimGenerator:
    def __init__(self, db_path: str, split_config_path: str, seed: int = 20261004):
        self.db_path = db_path
        self.split_config_path = split_config_path
        self.seed = seed
        self.rng = random.Random(seed)

        with open(split_config_path, "r", encoding="utf-8") as f:
            self.split_data = json.load(f)

        self.train_pids = set(self.split_data["train_patient_ids"])
        self.val_pids = set(self.split_data["val_patient_ids"])
        # TEST is strictly embargoed

    def generate_lane_b_dataset(self, pairs_per_task: int = 125) -> Dict[str, Any]:
        """
        Generates Lane B natural claims using rich, open-vocabulary clinical justifications.
        """
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        all_pids = list(self.train_pids | self.val_pids)
        placeholders = ",".join(["?"] * len(all_pids))

        # ----------------------------------------------------
        # S1: Natural Trend Direction
        # ----------------------------------------------------
        cursor.execute(f"""
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
        """, all_pids)
        obs_rows = cursor.fetchall()

        grouped_obs = defaultdict(list)
        for r in obs_rows:
            grouped_obs[(r[0], r[1])].append(r)

        s1_natural_templates = [
            # Natural agent justifications asserting trend
            ("NAT_S1_1", "The patient's longitudinal EHR chart reveals a {dir_adj} trajectory in {concept} across three recent clinical evaluations."),
            ("NAT_S1_2", "Serial laboratory testing indicates that {concept} levels have {dir_verb} over the patient's past 3 recorded outpatient encounters."),
            ("NAT_S1_3", "Review of consecutive diagnostic workups demonstrates a {dir_noun} in {concept} across the prior three visits."),
            ("NAT_S1_4", "Longitudinal monitoring confirms that {concept} measurements have been {dir_part} over the course of the last 3 checkups.")
        ]

        s1_claims = []
        s1_pairs_count = 0
        for (pid, code), obs_list in grouped_obs.items():
            if s1_pairs_count >= pairs_per_task:
                break
            if len(obs_list) < 3:
                continue

            for i in range(len(obs_list) - 2):
                if s1_pairs_count >= pairs_per_task:
                    break
                w = obs_list[i:i+3]
                v1, v2, v3 = w[0][3], w[1][3], w[2][3]

                if v1 < v2 < v3:
                    true_trend = "INCREASING"
                elif v1 > v2 > v3:
                    true_trend = "DECREASING"
                else:
                    continue

                false_trend = "DECREASING" if true_trend == "INCREASING" else "INCREASING"
                display_name = w[0][2] or "Observation"
                concept_clean = display_name.split("[")[0].strip()
                if not concept_clean:
                    continue

                tf_id, tmpl = self.rng.choice(s1_natural_templates)
                lex = {
                    "INCREASING": {
                        "dir_adj": "progressively rising",
                        "dir_verb": "consistently increased",
                        "dir_noun": "steady upward progression",
                        "dir_part": "trending upward"
                    },
                    "DECREASING": {
                        "dir_adj": "downward",
                        "dir_verb": "consistently decreased",
                        "dir_noun": "steady decline",
                        "dir_part": "trending downward"
                    }
                }

                pair_id = f"LANE_B_S1_{pid}_{code}_{i}"
                split_tag = "TRAIN" if pid in self.train_pids else "VAL"

                # Supported
                text_sup = tmpl.format(concept=concept_clean, **lex[true_trend])
                s1_claims.append({
                    "task_code": "S1",
                    "lane": "LANE_B_NATURAL",
                    "pair_id": pair_id,
                    "patient_id": pid,
                    "split": split_tag,
                    "clinical_code": code,
                    "clinical_display": display_name,
                    "template_family": tf_id,
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

                # Contradicted
                text_con = tmpl.format(concept=concept_clean, **lex[false_trend])
                s1_claims.append({
                    "task_code": "S1",
                    "lane": "LANE_B_NATURAL",
                    "pair_id": pair_id,
                    "patient_id": pid,
                    "split": split_tag,
                    "clinical_code": code,
                    "clinical_display": display_name,
                    "template_family": tf_id,
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

                s1_pairs_count += 1

        # ----------------------------------------------------
        # S2: Natural Before/After Relation
        # ----------------------------------------------------
        cursor.execute(f"""
        SELECT patient_id, resource_type, resource_id, clinical_code, clinical_display, event_time_norm, event_time_epoch
        FROM timeline_events
        WHERE patient_id IN ({placeholders})
          AND is_post_death_event = 0
          AND clinical_display IS NOT NULL
          AND TRIM(clinical_display) != ''
        ORDER BY patient_id, event_time_epoch ASC, resource_id ASC
        """, all_pids)
        ev_rows = cursor.fetchall()

        by_patient = defaultdict(list)
        for r in ev_rows:
            by_patient[r[0]].append(r)

        s2_natural_templates = [
            ("NAT_S2_1", "Clinical records verify that {event_A} was documented {rel_adv} {event_B}."),
            ("NAT_S2_2", "According to the encounter timeline, {event_A} took place {rel_prep} {event_B}."),
            ("NAT_S2_3", "Longitudinal documentation establishes that {event_A} chronologically {rel_verb} {event_B}."),
            ("NAT_S2_4", "In the patient's care sequence, {event_A} is registered as {rel_part} {event_B}.")
        ]

        s2_claims = []
        s2_pairs_count = 0
        for pid, ev_list in by_patient.items():
            if s2_pairs_count >= pairs_per_task:
                break
            if len(ev_list) < 2:
                continue

            for i in range(len(ev_list) - 1):
                if s2_pairs_count >= pairs_per_task:
                    break
                eA, eB = ev_list[i], ev_list[i+1]
                if eA[6] == eB[6] or eA[4] == eB[4] or eA[2] == eB[2]:
                    continue

                nameA = eA[4].split("[")[0].strip() if eA[4] else ""
                nameB = eB[4].split("[")[0].strip() if eB[4] else ""
                if not nameA or not nameB or nameA == nameB:
                    continue

                tf_id, tmpl = self.rng.choice(s2_natural_templates)
                lex_before = {"rel_adv": "ahead of", "rel_prep": "prior to the start of", "rel_verb": "antedated", "rel_part": "preceding"}
                lex_after = {"rel_adv": "in the aftermath of", "rel_prep": "subsequent to the completion of", "rel_verb": "succeeded", "rel_part": "following"}

                pair_id = f"LANE_B_S2_{pid}_{i}"
                split_tag = "TRAIN" if pid in self.train_pids else "VAL"

                if i % 2 == 0:
                    text_sup = tmpl.format(event_A=nameA, event_B=nameB, **lex_before)
                    s2_claims.append({
                        "task_code": "S2",
                        "lane": "LANE_B_NATURAL",
                        "pair_id": pair_id,
                        "patient_id": pid,
                        "split": split_tag,
                        "clinical_code": f"{eA[3]}_vs_{eB[3]}",
                        "clinical_display": f"{nameA} vs {nameB}",
                        "template_family": tf_id,
                        "claim_text": text_sup,
                        "ground_truth": "SUPPORTED",
                        "structured_predicate": {"event_A_id": eA[2], "event_B_id": eB[2], "claim_type": "BEFORE", "comparator": "LT"},
                        "source_event_ids": [eA[2], eB[2]],
                        "source_values": [None, None],
                        "source_timestamps": [eA[5], eB[5]]
                    })
                    text_con = tmpl.format(event_A=nameA, event_B=nameB, **lex_after)
                    s2_claims.append({
                        "task_code": "S2",
                        "lane": "LANE_B_NATURAL",
                        "pair_id": pair_id,
                        "patient_id": pid,
                        "split": split_tag,
                        "clinical_code": f"{eA[3]}_vs_{eB[3]}",
                        "clinical_display": f"{nameA} vs {nameB}",
                        "template_family": tf_id,
                        "claim_text": text_con,
                        "ground_truth": "CONTRADICTED",
                        "structured_predicate": {"event_A_id": eA[2], "event_B_id": eB[2], "claim_type": "AFTER", "comparator": "GT"},
                        "source_event_ids": [eA[2], eB[2]],
                        "source_values": [None, None],
                        "source_timestamps": [eA[5], eB[5]]
                    })
                else:
                    text_sup = tmpl.format(event_A=nameB, event_B=nameA, **lex_after)
                    s2_claims.append({
                        "task_code": "S2",
                        "lane": "LANE_B_NATURAL",
                        "pair_id": pair_id,
                        "patient_id": pid,
                        "split": split_tag,
                        "clinical_code": f"{eB[3]}_vs_{eA[3]}",
                        "clinical_display": f"{nameB} vs {nameA}",
                        "template_family": tf_id,
                        "claim_text": text_sup,
                        "ground_truth": "SUPPORTED",
                        "structured_predicate": {"event_A_id": eB[2], "event_B_id": eA[2], "claim_type": "AFTER", "comparator": "GT"},
                        "source_event_ids": [eB[2], eA[2]],
                        "source_values": [None, None],
                        "source_timestamps": [eB[5], eA[5]]
                    })
                    text_con = tmpl.format(event_A=nameB, event_B=nameA, **lex_before)
                    s2_claims.append({
                        "task_code": "S2",
                        "lane": "LANE_B_NATURAL",
                        "pair_id": pair_id,
                        "patient_id": pid,
                        "split": split_tag,
                        "clinical_code": f"{eB[3]}_vs_{eA[3]}",
                        "clinical_display": f"{nameB} vs {nameA}",
                        "template_family": tf_id,
                        "claim_text": text_con,
                        "ground_truth": "CONTRADICTED",
                        "structured_predicate": {"event_A_id": eB[2], "event_B_id": eA[2], "claim_type": "BEFORE", "comparator": "LT"},
                        "source_event_ids": [eB[2], eA[2]],
                        "source_values": [None, None],
                        "source_timestamps": [eB[5], eA[5]]
                    })

                s2_pairs_count += 1

        # ----------------------------------------------------
        # S3: Natural Latest vs Previous Comparison
        # ----------------------------------------------------
        s3_natural_templates = [
            ("NAT_S3_1", "Compared against baseline measurements from the preceding visit, the patient's current {concept} demonstrates an {comp_desc} reading."),
            ("NAT_S3_2", "Diagnostic assessment shows that the most recently documented {concept} {comp_verb} the prior encounter's result."),
            ("NAT_S3_3", "Evaluating recent trends reveals that current {concept} levels are {comp_adj} relative to the earlier measurement."),
            ("NAT_S3_4", "The active reading for {concept} reflects a {comp_noun} compared to the previous clinical record.")
        ]

        s3_claims = []
        s3_pairs_count = 0
        for (pid, code), obs_list in grouped_obs.items():
            if s3_pairs_count >= pairs_per_task:
                break
            if len(obs_list) < 2:
                continue

            for i in range(len(obs_list) - 1):
                if s3_pairs_count >= pairs_per_task:
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

                tf_id, tmpl = self.rng.choice(s3_natural_templates)
                lex_map = {
                    "HIGHER": {"comp_desc": "elevated", "comp_verb": "surpasses", "comp_adj": "higher", "comp_noun": "rise in value"},
                    "LOWER": {"comp_desc": "attenuated", "comp_verb": "drops below", "comp_adj": "lower", "comp_noun": "reduction in value"}
                }

                pair_id = f"LANE_B_S3_{pid}_{code}_{i}"
                split_tag = "TRAIN" if pid in self.train_pids else "VAL"

                text_sup = tmpl.format(concept=concept_clean, **lex_map[true_rel])
                s3_claims.append({
                    "task_code": "S3",
                    "lane": "LANE_B_NATURAL",
                    "pair_id": pair_id,
                    "patient_id": pid,
                    "split": split_tag,
                    "clinical_code": code,
                    "clinical_display": display_name,
                    "template_family": tf_id,
                    "claim_text": text_sup,
                    "ground_truth": "SUPPORTED",
                    "structured_predicate": {"concept": code, "claim_type": f"{true_rel}_THAN_PREVIOUS", "comparator": "GT" if true_rel == "HIGHER" else "LT"},
                    "source_event_ids": [o_prev[7], o_latest[7]],
                    "source_values": [v_prev, v_latest],
                    "source_timestamps": [o_prev[5], o_latest[5]]
                })

                text_con = tmpl.format(concept=concept_clean, **lex_map[false_rel])
                s3_claims.append({
                    "task_code": "S3",
                    "lane": "LANE_B_NATURAL",
                    "pair_id": pair_id,
                    "patient_id": pid,
                    "split": split_tag,
                    "clinical_code": code,
                    "clinical_display": display_name,
                    "template_family": tf_id,
                    "claim_text": text_con,
                    "ground_truth": "CONTRADICTED",
                    "structured_predicate": {"concept": code, "claim_type": f"{false_rel}_THAN_PREVIOUS", "comparator": "GT" if false_rel == "HIGHER" else "LT"},
                    "source_event_ids": [o_prev[7], o_latest[7]],
                    "source_values": [v_prev, v_latest],
                    "source_timestamps": [o_prev[5], o_latest[5]]
                })

                s3_pairs_count += 1

        # ----------------------------------------------------
        # S4: Natural Current Value
        # ----------------------------------------------------
        s4_natural_templates = [
            ("NAT_S4_1", "Based on active chart documentation, the patient's current {concept} is confirmed at {val} {unit}."),
            ("NAT_S4_2", "The most recent laboratory panel documents active {concept} at {val} {unit}."),
            ("NAT_S4_3", "According to the EHR summary, the active recorded finding for {concept} is {val} {unit}."),
            ("NAT_S4_4", "The latest clinical evaluation confirms {concept} measuring {val} {unit}.")
        ]

        s4_claims = []
        s4_pairs_count = 0
        for (pid, code), obs_list in grouped_obs.items():
            if s4_pairs_count >= pairs_per_task:
                break
            if len(obs_list) < 2:
                continue

            for i in range(len(obs_list) - 1):
                if s4_pairs_count >= pairs_per_task:
                    break
                o_stale = obs_list[i]
                o_latest = obs_list[-1]

                if o_stale[3] == o_latest[3]:
                    continue

                display_name = o_latest[2] or "Observation"
                concept_clean = display_name.split("[")[0].strip()
                unit_str = o_latest[4] or ""

                tf_id, tmpl = self.rng.choice(s4_natural_templates)
                pair_id = f"LANE_B_S4_{pid}_{code}_{i}"
                split_tag = "TRAIN" if pid in self.train_pids else "VAL"

                text_sup = tmpl.format(concept=concept_clean, val=o_latest[3], unit=unit_str)
                s4_claims.append({
                    "task_code": "S4",
                    "lane": "LANE_B_NATURAL",
                    "pair_id": pair_id,
                    "patient_id": pid,
                    "split": split_tag,
                    "clinical_code": code,
                    "clinical_display": display_name,
                    "template_family": tf_id,
                    "claim_text": text_sup,
                    "ground_truth": "SUPPORTED",
                    "structured_predicate": {"concept": code, "claim_type": "CURRENT_VALUE", "claimed_value": o_latest[3]},
                    "source_event_ids": [o_stale[7], o_latest[7]],
                    "source_values": [o_stale[3], o_latest[3]],
                    "source_timestamps": [o_stale[5], o_latest[5]]
                })

                text_con = tmpl.format(concept=concept_clean, val=o_stale[3], unit=unit_str)
                s4_claims.append({
                    "task_code": "S4",
                    "lane": "LANE_B_NATURAL",
                    "pair_id": pair_id,
                    "patient_id": pid,
                    "split": split_tag,
                    "clinical_code": code,
                    "clinical_display": display_name,
                    "template_family": tf_id,
                    "claim_text": text_con,
                    "ground_truth": "CONTRADICTED",
                    "structured_predicate": {"concept": code, "claim_type": "CURRENT_VALUE", "claimed_value": o_stale[3]},
                    "source_event_ids": [o_stale[7], o_latest[7]],
                    "source_values": [o_stale[3], o_latest[3]],
                    "source_timestamps": [o_stale[5], o_latest[5]]
                })

                s4_pairs_count += 1

        conn.close()

        all_lane_b_claims = s1_claims + s2_claims + s3_claims + s4_claims
        return {
            "all_claims": all_lane_b_claims,
            "counts": {
                "S1": len(s1_claims),
                "S2": len(s2_claims),
                "S3": len(s3_claims),
                "S4": len(s4_claims),
                "total": len(all_lane_b_claims),
                "pairs": len(all_lane_b_claims) // 2
            }
        }
