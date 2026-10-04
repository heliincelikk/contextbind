# ContextBind — Frozen Scientific Methodology & Protocol

**Document Status:** FROZEN  
**Target:** ML Empowerment Build Challenge 3.0  
**Domain:** Clinical AI Pre-Action Runtime Safety Interlock  

---

## 1. Project Hypothesis & Core Principle
Standard FHIR resource validation and identity-only security gates (e.g., verifying `patient.id` match) fail to prevent high-risk clinical actions when the retrieved evidence is factually true for the correct patient but originates from an outdated clinical state, an inactive encounter, or a temporally inconsistent evidence bundle. 

**ContextBind** hypothesizes that explicit pre-action binding across four orthogonal axes—**Identity**, **Encounter**, **Chronology/Temporal Validity**, and **State Coherence**—provides a provable, deterministic reduction in unsafe tool execution without unacceptably degrading benign action throughput.

---

## 2. Attack Family Definitions (First-Stage Scope)

| Attack Code | Threat Name | Formal Definition | Safety Rationale |
| :--- | :--- | :--- | :--- |
| **`T1`** | **Stale-State Replay** | Clinical evidence belongs to the correct patient and encounter history, but has been superseded by a newer, conflicting state (e.g., medication discontinued, allergy status changed, condition resolved). | Tests temporal state-machine awareness. |
| **`T2`** | **Wrong Encounter** | Clinical evidence belongs to the correct patient but was generated during a distinct, inactive encounter/admission episode. | Tests episode and encounter binding boundaries. |
| **`T3`** | **Mixed-Time Context** | An aggregated evidence bundle containing both valid current clinical state and uncoordinated historical/superseded records presented simultaneously to an action planner. | Tests multi-source bundle temporal coherence. |

*Note on T4 / Cross-patient attack*: Relabeled cross-patient perturbations are deferred to subsequent phases to maintain strict focus on temporal and encounter binding.

---

## 3. Mandatory & Inviolable Scientific Rules

### Rule 1: Zero Test-Set Contamination (Validation-Only Tuning)
- Under no circumstances may hyper-parameters, rule thresholds, corruption generator dynamics, or feature engineering choices be tuned or modified based on observations from the **TEST** split.
- All exploratory analysis, parameter adjustments, and calibration must be conducted strictly on the **TRAIN** and **VALIDATION** splits.
- The test split is evaluated exactly once for final benchmark reporting.

### Rule 2: Frozen B1 Deterministic Rule Baseline
- The deterministic baseline rule engine (**B1**) must be fully specified, unit-tested, and frozen prior to running benchmark evaluations on the test set.
- The Git commit hash, SHA256 file checksums, and freeze timestamp will be permanently documented in `reports/phases/B1_FREEZE.md`.
- B1 must implement robust deterministic checks across:
  1. Patient reference consistency,
  2. Encounter reference consistency,
  3. Timestamp chronology and temporal validity windows,
  4. Newer conflicting clinical state detection,
  5. Available provenance / audit trail consistency.
- B1 must NOT be artificially weakened as a straw-man baseline.

### Rule 3: Generator Leakage Sentinel Classifier
- To prevent synthetic benchmark artifacts from leaking class labels, a metadata-only binary classifier must be trained to discriminate between clean and corrupted bundles.
- **Strict Prohibition**: The leakage classifier is prohibited from accessing any clinical codes, diagnoses, medication names, clinical text, or lab values.
- **Permitted Features Only**:
  - Missingness and null-value distributions,
  - Resource count distributions,
  - Timestamp ISO string formats and precision,
  - Serialization ordering and schema key ordering,
  - Bundle payload byte length and string length statistics,
  - Field presence / absence boolean indicators.
- **Passing Criterion**: If the leakage classifier achieves performance significantly above random chance (e.g., ROC-AUC $> 0.55$), the corruption generator is deemed invalid, and generation must be refactored before proceeding to model training or baseline evaluation.

### Rule 4: Multi-Seed Execution & Statistical Rigor
- No scientific claims may be asserted from single-seed runs.
- A minimum of **3 independent random seeds** (5 seeds preferred where computationally viable) must be executed across all experimental pipelines.
- All reported metrics must include:
  - Mean ($\mu$),
  - Standard deviation ($\sigma$),
  - Non-parametric 95% Bootstrap Confidence Intervals ($B = 10,000$ iterations).
- Performance gains overlapping within confidence intervals will not be reported as statistically significant improvements.

### Rule 5: Strict Patient-Disjoint Partitioning
- Data splits (**Train / Validation / Test**) must be strictly partitioned at the unique `patient_id` level.
- No patient's records, encounters, or historical events may appear across multiple partitions.
- Any donor pool used for synthetic corruption construction must draw donor candidates exclusively from within the same patient partition to prevent partition bleeding.

---

## 4. Evaluation Metrics

| Metric | Formula / Definition | Optimization Direction |
| :--- | :--- | :--- |
| **Unsafe Action Release Rate (UAR)** | $\frac{\text{Unsafe Actions Permitted (PASS)}}{\text{Total Unsafe Action Attempts}}$ | **Minimize** ($\downarrow$) |
| **Benign Action Block Rate (BABR)** | $\frac{\text{Safe Actions Incorrectly Blocked (BLOCK)}}{\text{Total Safe Action Attempts}}$ | **Minimize** ($\downarrow$) |
| **Attack-Family Recall & Precision** | Per-family ($T1, T2, T3$) detection rates | **Maximize** ($\uparrow$) |
| **Decision Distribution** | Proportions of discrete `PASS`, `HOLD`, `BLOCK` | Diagnostic |

---

## 5. Decision Governance & Phase Protocol
1. Every phase executes only its bounded scope.
2. An exhaustive phase report is produced at the completion of each phase.
3. Every phase concludes with the mandatory human checkpoint:
   `DURDUM — SONRAKİ FAZA GEÇMEDEN ÖNCE ONAY BEKLİYORUM.`
4. Execution halts until explicit user authorization ("DEVAM") is granted.
