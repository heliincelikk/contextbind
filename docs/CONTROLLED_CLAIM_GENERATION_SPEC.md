# ContextBind — Controlled Temporal Claim Generation Specification

**Document Status:** FROZEN  
**Phase:** P4 (Controlled Dataset Construction & Leakage Audit)

---

## 1. Pipeline Overview & Counterfactual Pairing
The claim generation engine extracts authentic longitudinal sub-sequences from `data/interim/contextbind_timeline.sqlite` and constructs paired natural-language claims.

### 1.1 Invariant Properties
1. **Zero Partition Leakage:** Claims are partitioned strictly by `patient_id` following `configs/split_primary_20261004.json` (TRAIN = 345 patients, VALIDATION = 115 patients). TEST (115 patients) is completely omitted.
2. **Strict Counterfactual Pairing:** Every extracted evidence slice generates an identical pair:
   - One `SUPPORTED` claim (verifiable mathematical truth).
   - One `CONTRADICTED` claim (inverted relation or superseded state).
3. **Lexical Saliency Neutralization:** Directional vocabulary (`increased`, `decreased`, `before`, `after`, `higher`, `lower`) occurs in equal frequencies across `SUPPORTED` and `CONTRADICTED` ground truths.

---

## 2. Extraction & Perturbation Algorithms

### Task S1 — Trend Direction
- **Source Selection:** Query continuous numeric observations for patient $p$ and code $c$ where count $\ge 3$.
- **Window:** Take 3 consecutive readings $[v_1, v_2, v_3]$ with timestamps $[t_1, t_2, t_3]$ ($t_1 < t_2 < t_3$).
- **Monotonic Filter:** If $v_1 < v_2 < v_3 \implies \text{True Trend} = \text{INCREASING}$. If $v_1 > v_2 > v_3 \implies \text{True Trend} = \text{DECREASING}$.
- **Pair Construction:**
  - `SUPPORTED`: Render true trend direction with template family $TF_i$.
  - `CONTRADICTED`: Render opposite trend direction with same template family $TF_i$.

### Task S2 — Before / After Temporal Relation
- **Source Selection:** Query pairs of distinct clinical events $(e_A, e_B)$ for patient $p$ where $t(e_A) \ne t(e_B)$.
- **Pair Construction:**
  - Let $t(e_A) < t(e_B)$ (True: $e_A \text{ BEFORE } e_B$ and $e_B \text{ AFTER } e_A$).
  - `SUPPORTED`: $e_A \text{ before } e_B$ (or $e_B \text{ after } e_A$).
  - `CONTRADICTED`: $e_A \text{ after } e_B$ (or $e_B \text{ before } e_A$).

### Task S3 — Latest vs. Previous Comparison
- **Source Selection:** Query observation trajectories with $\ge 2$ measurements where $v(o_{latest}) \ne v(o_{prev})$.
- **Pair Construction:**
  - If $v(o_{latest}) > v(o_{prev})$: `SUPPORTED` asserts *higher/exceeds*; `CONTRADICTED` asserts *lower/falls below*.
  - If $v(o_{latest}) < v(o_{prev})$: `SUPPORTED` asserts *lower/falls below*; `CONTRADICTED` asserts *higher/exceeds*.

### Task S4 — Latest / Current Claim
- **Source Selection:** Query observation trajectories with $\ge 2$ distinct measurement dates.
- **Pair Construction:**
  - `SUPPORTED`: Asserts the true latest measurement $v(o_{latest})$ as current.
  - `CONTRADICTED`: Asserts an authentic historical superseded measurement $v(o_{stale})$ ($t(o_{stale}) < t(o_{latest})$) as current.

---

## 3. Storage & Artifact Format
Generated claims are persisted to:
- `data/processed/p4_claims_train.jsonl`
- `data/processed/p4_claims_val_id.jsonl` (In-Distribution template families)
- `data/processed/p4_claims_val_ood.jsonl` (Held-Out template families)

Each record stores:
```json
{
  "claim_id": "S1_TRN_000123",
  "task_code": "S1",
  "patient_id": "urn:uuid:...",
  "clinical_code": "2823-3",
  "clinical_display": "Potassium [Moles/volume] in Blood",
  "template_family": "S1_TF1_ACTIVE",
  "is_held_out_template": false,
  "claim_text": "The Potassium level has increased across the last 3 measurements.",
  "ground_truth": "SUPPORTED",
  "structured_predicate": {
    "concept": "2823-3",
    "claim_type": "TREND_INCREASING",
    "window": "LAST_3",
    "comparator": "GT",
    "claimed_direction": "INCREASING"
  },
  "source_event_ids": ["obs_1", "obs_2", "obs_3"],
  "source_values": [4.1, 4.4, 4.8],
  "source_timestamps": ["2023-01-10T10:00:00Z", "2023-05-12T10:00:00Z", "2023-11-04T10:00:00Z"]
}
```
