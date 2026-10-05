# ContextBind — Test-Set Embargo & Blinded Development Protocol

**Document Status:** FROZEN  
**Phase:** P3 (Specification & Partitioning)

---

## 1. Absolute Test-Set Embargo Protocol

To eliminate all forms of data snooping, hypothesis contamination, and subtle threshold tuning on test distributions:

1. **Zero Access to Test Partitions During Development:**
   - Synthetic perturbation generator development, quality assurance, and distribution audits must be conducted strictly on **TRAIN** and **VALIDATION** partitions.
   - Deterministic rule baseline (**B1**) specification, threshold tuning, and unit validation must operate strictly on **TRAIN** and **VALIDATION** partitions.
   - Machine learning feature engineering, hyper-parameter search, and ablation studies must operate strictly on **TRAIN** (for fitting) and **VALIDATION** (for model selection).

2. **Single-Shot Final Benchmark Evaluation:**
   - The **TEST** split (`split_primary_20261004.json`) will be evaluated exactly once, only after:
     * The B1 baseline implementation has been frozen and committed with a logged SHA256 checksum and Git commit hash,
     * The generator has passed the metadata leakage sentinel test on validation data,
     * All model architectures, decision thresholds, and hyper-parameters are permanently locked.

3. **Robustness Split Embargo:**
   - Multi-seed robustness partitions (`split_robustness_20261005.json` and `split_robustness_20261006.json`) are strictly locked under the same embargo. They cannot be accessed or evaluated until after the primary frozen model is locked.
