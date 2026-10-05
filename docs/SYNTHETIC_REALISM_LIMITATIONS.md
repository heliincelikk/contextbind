# ContextBind — Synthetic Realism & Metadata Completeness Limitations

**Document Status:** FROZEN  
**Phase:** P3 (Specification & Solvability Audit)

---

## 1. The Synthetic Metadata Advantage
Empirical audit of the 575-patient Synthea cohort revealed:
- **100.0% Encounter reference coverage** across all observations and medications.
- **100.0% ISO-8601 Timestamp completeness** across all clinical events.
- **0 Orphan references** or dangling entity pointers.

### Implication:
Synthea's unusually complete metadata makes rule-based context validation substantially easier than in real-world clinical EHR systems. In production hospital environments, encounter linkages are often missing from historical records, timestamps vary in precision (date-only vs millisecond), and federated data sources lack unified episode IDs.

---

## 2. Scientific Boundary & Non-Strawman Policy
- **No Artificial Degradation to Fabricate ML Superiority:** We strictly prohibit selectively removing or mangling metadata in benchmark datasets solely to make rule baselines appear weak or to artificially elevate ML models.
- **Degraded Evaluation Rules:** If noise or missingness stress-testing is evaluated in later phases:
  1. The exact same degradation transformations must be applied equally across both clean and corrupted samples.
  2. Any degraded-metadata benchmark must be clearly demarcated and reported in separate stress-testing tables, never substituted for the primary ground-truth benchmark.
