"""
ContextBind — Oracle Symbolic Temporal Verifier (B_ORACLE)
Executes deterministic verification of structured temporal predicates directly against SQLite timeline.
Strictly uses Python Standard Library.
"""

import sqlite3
from typing import Dict, Any, Tuple

class OracleTemporalVerifier:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def verify_claim_predicate(self, claim_record: Dict[str, Any]) -> Tuple[str, str]:
        """
        Verifies a claim record using its structured_predicate against the SQLite database.
        Returns (decision: 'PASS' | 'BLOCK' | 'HOLD', explanation: str).
        """
        task_code = claim_record["task_code"]
        pred = claim_record["structured_predicate"]
        pid = claim_record["patient_id"]
        source_ev_ids = claim_record.get("source_event_ids", [])

        conn = self._connect()
        cursor = conn.cursor()

        try:
            if task_code == "S1":
                # S1: Trend Direction
                # Retrieve source observations by ID in chronological order
                placeholders = ",".join(["?"] * len(source_ev_ids))
                cursor.execute(f"""
                SELECT resource_id, value_numeric, event_time_epoch
                FROM timeline_events
                WHERE resource_id IN ({placeholders})
                ORDER BY event_time_epoch ASC
                """, source_ev_ids)
                rows = cursor.fetchall()
                if len(rows) < 3:
                    return "HOLD", "Insufficient source observations located in canonical timeline."
                
                vals = [r[1] for r in rows]
                claimed_dir = pred.get("claimed_direction")
                
                is_inc = (vals[0] < vals[1] < vals[2])
                is_dec = (vals[0] > vals[1] > vals[2])

                if claimed_dir == "INCREASING":
                    return ("PASS", f"Verified monotonic increase: {vals}") if is_inc else ("BLOCK", f"Contradicted increase: actual series is {vals}")
                elif claimed_dir == "DECREASING":
                    return ("PASS", f"Verified monotonic decrease: {vals}") if is_dec else ("BLOCK", f"Contradicted decrease: actual series is {vals}")
                else:
                    return "HOLD", f"Unknown trend direction: {claimed_dir}"

            elif task_code == "S2":
                # S2: Before / After Temporal Relation
                ev_A_id = pred.get("event_A_id")
                ev_B_id = pred.get("event_B_id")
                comp = pred.get("comparator") # LT for BEFORE, GT for AFTER
                
                cursor.execute("""
                SELECT resource_id, event_time_epoch, event_time_norm
                FROM timeline_events
                WHERE resource_id IN (?, ?)
                """, (ev_A_id, ev_B_id))
                rows = cursor.fetchall()
                if len(rows) < 2:
                    return "HOLD", "One or both events missing from canonical timeline."

                epochs = {r[0]: r[1] for r in rows}
                t_A = epochs.get(ev_A_id)
                t_B = epochs.get(ev_B_id)

                if comp == "LT": # BEFORE
                    return ("PASS", f"Event A ({t_A}) strictly preceded Event B ({t_B})") if t_A < t_B else ("BLOCK", f"Contradicted BEFORE: t_A ({t_A}) >= t_B ({t_B})")
                elif comp == "GT": # AFTER
                    return ("PASS", f"Event A ({t_A}) succeeded Event B ({t_B})") if t_A > t_B else ("BLOCK", f"Contradicted AFTER: t_A ({t_A}) <= t_B ({t_B})")
                else:
                    return "HOLD", f"Unknown comparator: {comp}"

            elif task_code == "S3":
                # S3: Latest vs Previous Comparison
                placeholders = ",".join(["?"] * len(source_ev_ids))
                cursor.execute(f"""
                SELECT resource_id, value_numeric, event_time_epoch
                FROM timeline_events
                WHERE resource_id IN ({placeholders})
                ORDER BY event_time_epoch ASC
                """, source_ev_ids)
                rows = cursor.fetchall()
                if len(rows) < 2:
                    return "HOLD", "Insufficient observation points."
                
                v_prev = rows[0][1]
                v_latest = rows[1][1]
                comp = pred.get("comparator") # GT for HIGHER, LT for LOWER

                if comp == "GT":
                    return ("PASS", f"Latest ({v_latest}) > Prev ({v_prev}) verified.") if v_latest > v_prev else ("BLOCK", f"Contradicted HIGHER: Latest ({v_latest}) <= Prev ({v_prev})")
                elif comp == "LT":
                    return ("PASS", f"Latest ({v_latest}) < Prev ({v_prev}) verified.") if v_latest < v_prev else ("BLOCK", f"Contradicted LOWER: Latest ({v_latest}) >= Prev ({v_prev})")
                else:
                    return "HOLD", f"Unknown comparator: {comp}"

            elif task_code == "S4":
                # S4: Latest / Current Claim
                code = pred.get("concept")
                claimed_val = pred.get("claimed_value")

                cursor.execute("""
                SELECT value_numeric, event_time_norm
                FROM timeline_events
                WHERE patient_id = ? AND clinical_code = ? AND resource_type = 'Observation' AND value_numeric IS NOT NULL AND is_post_death_event = 0
                ORDER BY event_time_epoch DESC
                LIMIT 1
                """, (pid, code))
                row = cursor.fetchone()
                if not row:
                    return "HOLD", "No eligible observations found for code."

                true_latest_val = row[0]
                if abs(true_latest_val - claimed_val) < 1e-5:
                    return "PASS", f"Claimed value ({claimed_val}) matches true latest reading ({true_latest_val})."
                else:
                    return "BLOCK", f"Contradicted current state: Claimed ({claimed_val}) is superseded by latest active ({true_latest_val})."

            else:
                return "HOLD", f"Unknown task code: {task_code}"

        finally:
            conn.close()

    def verify_batch(self, claims: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
        """
        Verifies a list of claim records using in-memory preloaded lookup for maximum throughput.
        """
        conn = self._connect()
        cursor = conn.cursor()

        # 1. Preload event map: resource_id -> (value_numeric, event_time_epoch, event_time_norm)
        cursor.execute("""
        SELECT resource_id, value_numeric, event_time_epoch, event_time_norm
        FROM timeline_events
        WHERE is_post_death_event = 0
        """)
        res_map = {r[0]: (r[1], r[2], r[3]) for r in cursor.fetchall()}

        # 2. Preload latest observations for S4: (patient_id, clinical_code) -> latest value_numeric
        cursor.execute("""
        SELECT patient_id, clinical_code, value_numeric, event_time_epoch
        FROM timeline_events
        WHERE resource_type = 'Observation' 
          AND value_numeric IS NOT NULL 
          AND is_post_death_event = 0
          AND clinical_code != ''
          AND clinical_display IS NOT NULL
          AND TRIM(clinical_display) != ''
        ORDER BY event_time_epoch ASC, resource_id ASC
        """)
        latest_obs_map = {}
        for r in cursor.fetchall():
            latest_obs_map[(r[0], r[1])] = r[2]

        conn.close()

        results = []
        for claim_record in claims:
            task_code = claim_record["task_code"]
            pred = claim_record["structured_predicate"]
            pid = claim_record["patient_id"]
            source_ev_ids = claim_record.get("source_event_ids", [])

            if task_code == "S1":
                evs = [res_map.get(eid) for eid in source_ev_ids if eid in res_map]
                if len(evs) < 3:
                    results.append(("HOLD", "Insufficient source observations located in canonical timeline."))
                    continue
                
                # Sort by event_time_epoch
                evs.sort(key=lambda x: x[1])
                vals = [e[0] for e in evs]
                claimed_dir = pred.get("claimed_direction")
                is_inc = (vals[0] < vals[1] < vals[2])
                is_dec = (vals[0] > vals[1] > vals[2])

                if claimed_dir == "INCREASING":
                    results.append(("PASS", f"Verified monotonic increase: {vals}") if is_inc else ("BLOCK", f"Contradicted increase: actual series is {vals}"))
                elif claimed_dir == "DECREASING":
                    results.append(("PASS", f"Verified monotonic decrease: {vals}") if is_dec else ("BLOCK", f"Contradicted decrease: actual series is {vals}"))
                else:
                    results.append(("HOLD", f"Unknown trend direction: {claimed_dir}"))

            elif task_code == "S2":
                ev_A_id = pred.get("event_A_id")
                ev_B_id = pred.get("event_B_id")
                comp = pred.get("comparator")
                
                eA = res_map.get(ev_A_id)
                eB = res_map.get(ev_B_id)
                if not eA or not eB:
                    results.append(("HOLD", "One or both events missing from canonical timeline."))
                    continue

                t_A = eA[1]
                t_B = eB[1]

                if comp == "LT":
                    results.append(("PASS", f"Event A ({t_A}) strictly preceded Event B ({t_B})") if t_A < t_B else ("BLOCK", f"Contradicted BEFORE: t_A ({t_A}) >= t_B ({t_B})"))
                elif comp == "GT":
                    results.append(("PASS", f"Event A ({t_A}) succeeded Event B ({t_B})") if t_A > t_B else ("BLOCK", f"Contradicted AFTER: t_A ({t_A}) <= t_B ({t_B})"))
                else:
                    results.append(("HOLD", f"Unknown comparator: {comp}"))

            elif task_code == "S3":
                evs = [res_map.get(eid) for eid in source_ev_ids if eid in res_map]
                if len(evs) < 2:
                    results.append(("HOLD", "Insufficient observation points."))
                    continue
                
                evs.sort(key=lambda x: x[1])
                v_prev = evs[0][0]
                v_latest = evs[1][0]
                comp = pred.get("comparator")

                if comp == "GT":
                    results.append(("PASS", f"Latest ({v_latest}) > Prev ({v_prev}) verified.") if v_latest > v_prev else ("BLOCK", f"Contradicted HIGHER: Latest ({v_latest}) <= Prev ({v_prev})"))
                elif comp == "LT":
                    results.append(("PASS", f"Latest ({v_latest}) < Prev ({v_prev}) verified.") if v_latest < v_prev else ("BLOCK", f"Contradicted LOWER: Latest ({v_latest}) >= Prev ({v_prev})"))
                else:
                    results.append(("HOLD", f"Unknown comparator: {comp}"))

            elif task_code == "S4":
                code = pred.get("concept")
                claimed_val = pred.get("claimed_value")
                true_latest_val = latest_obs_map.get((pid, code))

                if true_latest_val is None or claimed_val is None:
                    results.append(("HOLD", "Missing eligible observation or claimed value."))
                    continue

                if abs(true_latest_val - claimed_val) < 1e-5:
                    results.append(("PASS", f"Claimed value ({claimed_val}) matches true latest reading ({true_latest_val})."))
                else:
                    results.append(("BLOCK", f"Contradicted current state: Claimed ({claimed_val}) is superseded by latest active ({true_latest_val})."))

            else:
                results.append(("HOLD", f"Unknown task code: {task_code}"))

        return results
