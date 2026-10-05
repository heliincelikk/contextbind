# ContextBind — Frozen Claim Template Families & Held-Out Partitioning

**Document Status:** FROZEN  
**Phase:** P4 (Controlled Claim Generation & Leakage Audit)

---

## 1. Design Principles & Anti-Memorization Protocol
To guarantee that semantic claim binders do not simply memorize specific phrase structures or punctuation patterns:
1. Every task is defined across multiple distinct linguistic realization families.
2. Every template family is symmetrically evaluated across both `SUPPORTED` and `CONTRADICTED` ground truths.
3. For each task, exactly one template family is permanently designated as **HELD-OUT (OOD)**.
4. **Held-Out Embargo:** Held-out templates are strictly excluded from all training datasets and evaluated exclusively during out-of-distribution generalization auditing.

---

## 2. Task S1 — Trend Direction (INCREASING / DECREASING)

- **Ground Truth Definition:** Derived from strict monotonicity across $k \ge 3$ consecutive chronological observations $\mathcal{O}[-k:]$:
  - `INCREASING`: $\forall i \in \{1, \dots, k-1\}, v(\mathcal{O}[-k+i]) > v(\mathcal{O}[-k+i-1])$
  - `DECREASING`: $\forall i \in \{1, \dots, k-1\}, v(\mathcal{O}[-k+i]) < v(\mathcal{O}[-k+i-1])$
- *Note on STABLE:* Excluded from the primary binary benchmark to eliminate arbitrary unit-dependent tolerance thresholds across heterogeneous clinical entities.

### Template Families:
- **`S1_TF1_ACTIVE` (In-Distribution):**  
  `"The {concept} level has {increased/decreased} across the last {count} measurements."`
- **`S1_TF2_TRAJECTORY` (In-Distribution):**  
  `"Over the preceding {count} tests, {concept} shows an {increasing/decreasing} trajectory."`
- **`S1_TF3_COURSE` (In-Distribution):**  
  `"{concept} has exhibited an {upward/downward} course over recent visits."`
- **`S1_TF4_PASSIVE_HELD_OUT` (HELD-OUT OOD):**  
  `"An {increasing/decreasing} progression is demonstrated in the patient's {concept} across the prior {count} evaluations."`

---

## 3. Task S2 — Before/After Temporal Relation

- **Ground Truth Definition:** Derived from exact Unix epoch timestamps $t(e_A), t(e_B)$ of distinct clinical events $e_A, e_B$:
  - `BEFORE`: $\text{epoch}(e_A) < \text{epoch}(e_B)$
  - `AFTER`: $\text{epoch}(e_A) > \text{epoch}(e_B)$

### Template Families:
- **`S2_TF1_STANDARD` (In-Distribution):**  
  `"{event_A} was recorded {before/after} {event_B}."`
- **`S2_TF2_SEQUENCE` (In-Distribution):**  
  `"{event_A} occurred {prior to/following} {event_B}."`
- **`S2_TF3_DOCUMENTATION` (In-Distribution):**  
  `"The documentation of {event_A} {preceded/succeeded} {event_B}."`
- **`S2_TF4_CLAUSAL_HELD_OUT` (HELD-OUT OOD):**  
  `"{event_A} took place {earlier than/subsequent to} {event_B}."`

---

## 4. Task S3 — Latest vs. Previous Comparison

- **Ground Truth Definition:** Derived from comparing the latest eligible observation $o_{latest} = \mathcal{O}[-1]$ against the immediately preceding observation $o_{prev} = \mathcal{O}[-2]$:
  - `HIGHER_THAN_PREVIOUS`: $v(o_{latest}) > v(o_{prev})$
  - `LOWER_THAN_PREVIOUS`: $v(o_{latest}) < v(o_{prev})$

### Template Families:
- **`S3_TF1_COMPARATIVE_ADJ` (In-Distribution):**  
  `"The latest {concept} reading is {higher/lower} than the previous measurement."`
- **`S3_TF2_EXCEEDS_FALLS` (In-Distribution):**  
  `"The most recent {concept} {exceeds/falls below} the prior value."`
- **`S3_TF3_ENCOUNTER_SHIFT` (In-Distribution):**  
  `"Compared to the preceding encounter, the current {concept} is {elevated/reduced}."`
- **`S3_TF4_MAGNITUDE_HELD_OUT` (HELD-OUT OOD):**  
  `"The current measurement of {concept} is {greater than/less than} the value from the prior evaluation."`

---

## 5. Task S4 — Latest/Current Claim

- **Ground Truth Definition:** Evaluates whether an asserted observation value corresponds to the true chronologically latest active measurement as of reference time $t$:
  - `SUPPORTED`: The asserted value equals $v(\arg\max_{o \in \mathcal{O}(p, c, t)} \text{event\_time}(o))$.
  - `CONTRADICTED`: The asserted value corresponds to an authentic historical observation that has been superseded by a newer reading.

### Template Families:
- **`S4_TF1_DIRECT_CURRENT` (In-Distribution):**  
  `"The patient's current {concept} is {value} {unit}."`
- **`S4_TF2_MOST_RECENT` (In-Distribution):**  
  `"The most recently documented {concept} is {value} {unit}."`
- **`S4_TF3_RECORDED_FINDING` (In-Distribution):**  
  `"Latest recorded {concept} stands at {value} {unit}."`
- **`S4_TF4_ACTIVE_STATE_HELD_OUT` (HELD-OUT OOD):**  
  `"As of the current evaluation, the active {concept} measurement is {value} {unit}."`
