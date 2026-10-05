# ContextBind — Generator Leakage Sentinel Specification

**Document Status:** FROZEN  
**Phase:** P3 (Attack Formalization & Protocol Specification)

---

## 1. Objective & Threat Model
Synthetic perturbation generators risk introducing non-clinical artifacts (e.g. subtle timestamp formatting differences, payload length shifts, key reordering, missing field anomalies) that allow a model to trivially distinguish clean from corrupted examples without learning clinical or temporal semantics.

To prevent benchmark artifact leakage, a **Metadata-Only Leakage Sentinel Classifier** must be evaluated prior to any downstream modeling.

---

## 2. Feature Policy

### 2.1 Permitted Features (Structural & Metadata Only):
- Missingness and null-value distribution counts across all resource fields,
- Bundle element / resource count distributions,
- Payload serialized byte size and string length statistics,
- Timestamp ISO string formats, string lengths, and precision patterns (e.g., presence of seconds vs milliseconds vs timezone offset formatting),
- Field presence / absence boolean indicators,
- Dictionary key serialization ordering indicators.

### 2.2 Strictly Forbidden Features (Clinical Content Disallowed):
- Observation LOINC/SNOMED codes and their clinical definitions,
- Diagnosis / Condition codes and text,
- Medication names, RxNorm codes, and drug classes,
- Quantitative clinical values and measurements,
- Clinical narrative text, descriptions, and notes.

---

## 3. Evaluation & Passing Criteria
- **Baseline Chance Level:** Under a 50/50 balanced clean vs corrupted sample distribution, random guessing yields $\text{ROC-AUC} \approx 0.50$ and $\text{Accuracy} \approx 0.50$.
- **Passing Criterion:** The leakage classifier must not achieve statistically significant separation above chance. If the 95% non-parametric bootstrap confidence interval of ROC-AUC overlaps with or remains strictly below $0.55$ ($\text{AUC} \le 0.55$), the generator passes the leakage sentinel.
- **Action on Failure:** If the leakage sentinel exceeds $\text{AUC} > 0.55$, generation is halted, the serialization pipeline is refactored to eliminate formatting divergence, and the sentinel is re-evaluated.
