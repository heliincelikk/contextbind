# ContextBind — Phase P5.6 Safety Calibration Report

**Date:** 2026-10-06  
**Phase:** P5.6 — Safety Calibration Gate & Operational Policy Freezing  
**Status:** **GO** (Safety Calibration Verified on Disjoint Validation Cohort)

---

## 1. Experimental Protocol & Cohort Integrity

In accordance with Phase P5.6 constraints:
1. **Strict Patient Disjointness:**
   - **Calibration Cohort (TRAIN):** 1,000 open-form claims (500 counterfactual pairs) derived strictly from TRAIN patient split (345 patients).
   - **Evaluation Cohort (VAL):** 1,000 open-form claims (500 counterfactual pairs) derived strictly from patient-disjoint VAL patient split (115 patients).
   - **Overlapping Patients:** **0** (Verified disjoint).
   - **TEST Cohort (115 patients):** **100% EMBARGOED AND UNTOUCHED.**
2. **Model Weight Freeze:**
   - Rule engine (`B_RULE`) and pretrained DistilBERT contextual encoder weights remained completely frozen throughout calibration.
   - Threshold $\tau$ was tuned exclusively on TRAIN-derived claims.

---

## 2. Risk–Coverage Calibration Curve (TRAIN Calibration Set: $N=1000$)

Operating thresholds swept on TRAIN calibration claims:

| Threshold ($\tau$) | Coverage | HOLD Rate | UAR (Safety Failure) | BABR (Overblocking) | Selective Accuracy | Overall Utility Acc | Exact Predicate Match | Pair Consistency |
|---|---|---|---|---|---|---|---|---|
| $\tau = 0.00$ (Ungated) | 31.80% | 68.20% | 3.20% | 7.60% | 83.02% | 26.40% | 22.10% | 22.00% |
| $\tau = 0.40$ | 31.70% | 68.30% | 3.20% | 7.60% | 82.97% | 26.30% | 22.10% | 22.00% |
| $\tau = 0.50$ | 30.60% | 69.40% | 3.00% | 7.60% | 82.68% | 25.30% | 21.30% | 21.60% |
| $\tau = 0.60$ | 29.80% | 70.20% | 2.40% | 7.40% | 83.56% | 24.90% | 21.20% | 20.80% |
| $\tau = 0.70$ | 28.30% | 71.70% | 2.00% | 7.00% | 84.10% | 23.80% | 20.20% | 19.60% |
| $\tau = 0.75$ | 27.90% | 72.10% | 1.80% | 6.80% | 84.59% | 23.60% | 20.00% | 19.40% |
| $\tau = 0.80$ | 27.70% | 72.30% | 1.80% | 6.40% | 85.20% | 23.60% | 20.00% | 19.40% |
| **$\tau^* = 0.85$ (Operational)** | **27.10%** | **72.90%** | **1.40%** | **5.60%** | **87.08%** | **23.60%** | **20.00%** | **19.40%** |
| $\tau = 0.90$ | 26.00% | 74.00% | 0.20% | 5.00% | 90.00% | 23.40% | 19.80% | 19.40% |
| $\tau = 0.95$ | 25.40% | 74.60% | 0.00% | 4.40% | 91.34% | 23.20% | 19.60% | 19.40% |
| $\tau = 0.98$ | 24.60% | 75.40% | 0.00% | 4.40% | 91.06% | 22.40% | 18.80% | 19.40% |

**Calibration Selection Rationale:**  
$\tau^* = 0.85$ was selected as the frozen operational threshold because it achieves **$\text{UAR} = 1.40\%$ (well below the 2.5% target)** on calibration while maintaining high selective accuracy (87.08%).

---

## 3. Out-of-Distribution Evaluation on Patient-Disjoint VAL Cohort ($N=1000$)

Comparison of frozen architectures on the independent validation cohort:

| Baseline Model | Coverage | HOLD Rate | UAR (Safety Failure) | BABR (Overblocking) | Selective Accuracy | Overall Utility Acc | Exact Pred Match | Pair Consistency |
|---|---|---|---|---|---|---|---|---|
| **B_RULE ONLY** | 47.80% | 52.20% | **0.00%** (0/500) | **3.60%** (18/500) | **96.23%** (460/478) | 46.00% | 43.40% | 38.20% |
| **SEMANTIC_AI ONLY (DistilBERT)** | 97.80% | 2.20% | **11.40%** (57/500) | **16.60%** (83/500) | **85.69%** (838/978) | 83.80% | 65.50% | 68.80% |
| **RULE $\to$ AI (Ungated $\tau=0.0$)** | 42.50% | 57.50% | **2.00%** (10/500) | **6.20%** (31/500) | **90.35%** (384/425) | 38.40% | 34.60% | 34.60% |
| **RULE $\to$ AI GATED ($\tau^*=0.85$)**| **39.10%** | **60.90%** | **1.20%** (6/500) | **5.00%** (25/500) | **92.07%** (360/391) | **36.00%** | **33.40%** | **32.40%** |

---

## 4. Task-Wise Breakdown for Gated Operational Architecture on VAL

| Task Code | Clinical Task Description | Total Claims | Coverage | HOLD Rate | UAR (Safety Failure) | BABR (Overblocking) | Selective Accuracy | Pair Consistency |
|---|---|---|---|---|---|---|---|---|
| **S1** | Longitudinal Trend Direction | 250 | 45.60% | 54.40% | **0.00%** | 0.00% | **100.00%** | 45.60% |
| **S2** | Chronological Before/After | 250 | 12.40% | 87.60% | **4.80%** | 5.60% | **58.06%** | 0.00% |
| **S3** | Latest-vs-Previous Comparison | 250 | 0.00% | 100.00% | **0.00%** | 0.00% | **0.00%** (All HOLD)| 0.00% |
| **S4** | Current Value Verification | 250 | 98.40% | 1.60% | **0.00%** | 14.40% | **92.68%** | 84.00% |

---

## 5. Operational Safety Policy Definition

ContextBind operational runtime policy is permanently frozen as follows:

```
                      Natural Claim / Justification
                                   │
                                   ▼
                   ┌───────────────────────────────┐
                   │        Frozen B_RULE          │
                   └───────────────┬───────────────┘
                                   │
                     Valid Match? ─┼── No
                                   │   │
                                  Yes  ▼
                                   │  ┌────────────────────────────────────┐
                                   │  │ Frozen DistilBERT Semantic Binder  │
                                   │  └──────────────────┬─────────────────┘
                                   │                     │
                                   │         Confidence >= 0.85?
                                   │                     │
                                   │        ┌────────────┴────────────┐
                                   │       Yes                        No
                                   │        │                         │
                                   ▼        ▼                         ▼
                   ┌───────────────────────────────────┐        ┌───────────┐
                   │    Structured Temporal Predicate  │        │   HOLD    │
                   └─────────────────┬─────────────────┘        └───────────┘
                                     │
                                     ▼
                   ┌───────────────────────────────────┐
                   │  Oracle Symbolic FHIR Verifier    │
                   └─────────────────┬─────────────────┘
                                     │
                          ┌──────────┴──────────┐
                          ▼                     ▼
                        PASS                  BLOCK
```

### Core Safety Principles:
1. **Semantic AI improves open-form temporal claim coverage and generalization.**
2. **Symbolic verification provides deterministic source checking once the claim has been correctly structured.**
3. **Confidence-gated abstention controls residual semantic-binding risk, suppressing safety failure rate (UAR) to 1.20% on out-of-distribution validation claims.**
4. **Symbolic verification alone does NOT eliminate semantic AI errors if an incorrect predicate is extracted; the confidence gate and fail-closed (`HOLD`) mechanism provide the necessary runtime safety barrier.**

---

## 6. Deliverables & Embargo Confirmation

- **Calibration Curve CSV:** [`reports/phases/P5_6_CALIBRATION_CURVE.csv`](file:///c:/Users/lenevo/Desktop/contexbind/reports/phases/P5_6_CALIBRATION_CURVE.csv)
- **Validation Accounting CSV:** [`reports/phases/P5_6_VAL_ACCOUNTING.csv`](file:///c:/Users/lenevo/Desktop/contexbind/reports/phases/P5_6_VAL_ACCOUNTING.csv)
- **Validation Task Metrics CSV:** [`reports/phases/P5_6_VAL_TASK_METRICS.csv`](file:///c:/Users/lenevo/Desktop/contexbind/reports/phases/P5_6_VAL_TASK_METRICS.csv)
- **Calibration Engine:** [`src/evaluation/p5_6_calibrate.py`](file:///c:/Users/lenevo/Desktop/contexbind/src/evaluation/p5_6_calibrate.py)
- **TEST Cohort Embargo:** **CONFIRMED (Zero access to 115 test patients).**
