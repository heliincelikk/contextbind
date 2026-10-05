# ContextBind — Frozen Benchmark Eligibility & Signal Policy

**Document Status:** FROZEN  
**Phase:** P3 (Specification & Partitioning)  
**Applicability:** All downstream synthetic perturbation generation, baseline evaluation, and benchmark reporting.

---

## 1. Patient-Disjoint Partitioning Policy
- All benchmark evaluation must be conducted on partitions separated strictly at the unique `patient_id` boundary.
- Under no circumstances may records, encounters, or historical observations belonging to the same patient appear in multiple partitions (e.g., Train, Validation, Test).
- Synthetic donor pools (if used for perturbation donor selection) must draw candidates strictly from within the corresponding partition.

---

## 2. Temporal & Death Boundary Eligibility
- **Post-Death Event Exclusion:** Events flagged with `is_post_death_event = 1` (where `event_time > deceasedDateTime`) are strictly ineligible for benchmark sample generation and action evaluation.
- **Deceased Patient Retention:** Deceased patients are not discarded wholesale. All authentic clinical events occurring on or prior to the recorded death timestamp (`event_time <= deceasedDateTime`) are fully eligible for longitudinal state construction.
- **Mandatory Metadata Integrity:** Any event missing a parseable ISO-8601 timestamp (`event_time_norm IS NULL`) or missing an unambiguous patient reference (`patient_id IS NULL`) is disqualified from benchmark inclusion.
- **Timestamp Duplicate Deduplication:** Multiple observations sharing the exact same `(patient_id, clinical_code, event_time_norm)` are treated as single temporal snapshots and are not counted as longitudinal state recurrences.

---

## 3. Signal Hierarchy & Semantic Constraints
- **Primary Clinical Signal — `Observation`:**
  - Standard laboratory values, physiological vital signs, and clinical measurements form the primary ground-truth signal for state evolution, temporal freshness, and encounter binding.
  - Continuous numeric values and categorical findings provide verifiable time-stamped state changes across distinct clinical encounters.
- **Secondary Exploratory Signal — `MedicationRequest`:**
  - Prescriptions serve as an exploratory lifecycle signal and must strictly adhere to FHIR R4 semantic boundaries.
  - **Inviolable Semantic Rule:** `MedicationRequest.status = 'completed'` represents an expired or fully dispensed order. It must **NEVER** be interpreted as equivalent to an explicit "medication stopped", "discontinued", or "deprescribed" clinical state change.
  - No synthetic "medication rollback" attacks may rely on equating `completed` with clinical discontinuation unless an explicit deprecation/cancellation record is present.
