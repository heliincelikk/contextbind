# ContextBind — Phase P5.5b Evidence Repair & Real Semantic AI Gate Report

**Date:** 2026-10-05  
**Phase:** P5.5b — Evidence Repair & Real Semantic AI Model Gate  
**Status:** **GO** (Metric Discrepancies Repaired, Provenance Audited, Real Contextual Semantic AI Executed)

---

## 1. Metric Consistency & Full Confusion Accounting Audit

### 1.1 Resolution of Apparent Inconsistency
In Phase P5.5, the reported metrics for `B_RULE` (`Verdict Accuracy = 33.70%`, `UAR = 0.00%`, `BABR = 4.00%`) appeared contradictory for a balanced binary evaluation.

**Mathematical Explanation:**
The evaluation cohort consists of $N = 1000$ claims (500 `SUPPORTED`, 500 `CONTRADICTED`). When a semantic parser encounters open-form syntax it cannot recognize, it outputs an invalid/empty predicate, which the downstream symbolic verifier (`OracleTemporalVerifier`) flags as `HOLD`.
- For `B_RULE`, **643 out of 1000 claims (64.30%) resulted in `HOLD`**.
- Of the 500 `CONTRADICTED` claims, 319 were `HOLD`, 181 were correctly `BLOCK`ed, and **0 were erroneously `PASS`ed**. Thus:
  $$\text{UAR} = \frac{\text{Contradicted} \to \text{PASS}}{\text{Total Contradicted}} = \frac{0}{500} = 0.00\%$$
- Of the 500 `SUPPORTED` claims, 324 were `HOLD`, 156 were `PASS`ed, and 20 were `BLOCK`ed. Thus:
  $$\text{BABR} = \frac{\text{Supported} \to \text{BLOCK}}{\text{Total Supported}} = \frac{20}{500} = 4.00\%$$
- Decided claims ($\text{PASS} + \text{BLOCK}$) = 357 ($\text{Coverage} = 35.70\%$).
- Selective accuracy on decided claims:
  $$\text{Selective Accuracy} = \frac{156 + 181}{357} = \frac{337}{357} = 94.40\%$$
- Overall utility accuracy (where `HOLD` is counted as an unverified/inactive outcome):
  $$\text{Overall Utility Accuracy} = \frac{156 + 181}{1000} = \frac{337}{1000} = 33.70\%$$

### 1.2 Complete Confusion Accounting Table (Lane B: $N=1000$)

| Model | Total Claims | Total PASS | Total BLOCK | Total HOLD | Sup $\to$ PASS | Sup $\to$ BLOCK | Sup $\to$ HOLD | Con $\to$ BLOCK | Con $\to$ PASS | Con $\to$ HOLD | Coverage | HOLD Rate | Selective Acc | Overall Utility Acc | UAR | BABR | Exact Pred Match | Pair Consistency |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **B_RULE (Frozen)** | 1000 | 156 | 201 | 643 | 156 | 20 | 324 | 181 | 0 | 319 | **35.70%** | 64.30% | **94.40%** | **33.70%** | **0.00%** | 4.00% | 30.10% | 24.80% |
| **B_ML (Frozen)** | 1000 | 349 | 382 | 269 | 296 | 72 | 132 | 310 | 53 | 137 | **73.10%** | 26.90% | **82.90%** | **60.60%** | **10.60%** | 14.40% | 43.30% | 40.60% |
| **SEMANTIC_AI (DistilBERT)** | 1000 | 445 | 459 | 96 | 372 | 81 | 47 | 378 | 73 | 49 | **90.40%** | 9.60% | **82.96%** | **75.00%** | **14.60%** | 16.20% | **53.90%** | **58.60%** |
| **B3 DIRECT TEXT** | 1000 | 380 | 620 | 0 | 196 | 304 | 0 | 316 | 184 | 0 | **100.00%** | 0.00% | **51.20%** | **51.20%** | **36.80%** | 60.80% | 0.00% | 18.00% |

---

## 2. Lane-B Provenance & Lexical Variation Audit

- **True Generation Mechanism:** Hand-authored Adversarial Paraphrase Dictionary & Multi-Slot Grammatical Templates.
- **Classification:** **Adversarial Paraphrase / Open-Form Evaluation Lane** (NOT autonomous generative LLM output).
- **Unique Surface Sentences:** **670 unique sentences** across 1,000 generated records.
- **Template Families:** 16 distinct adversarial template structures (`NAT_S1_1..4`, `NAT_S2_1..4`, `NAT_S3_1..4`, `NAT_S4_1..4`) with non-overlapping lexical items (`"documented ahead of"`, `"in the aftermath of"`, `"chronologically antedated"`, `"surpasses"`, `"attenuated reading"`, `"steady upward progression"`).

---

## 3. Real Pretrained Semantic AI Model Execution

### 3.1 Model Metadata
- **Model Name:** `distilbert/distilbert-base-uncased`
- **Architecture:** 6-layer, 768-dim Transformer Contextual Encoder with Multi-Task Linear Predicate Extraction Heads
- **Runtime Environment:** Python 3.13 (PyTorch 2.14.1+cpu, Hugging Face Transformers 5.18.0, sentencepiece 0.2.2)
- **Actually Executed:** **YES**
- **Training Constraints:** Trained strictly on P4 TRAIN split (`p4_final_train.jsonl`). Zero access to Lane B test sentences during training.

### 3.2 Evaluation Results & Comparison

1. **Predicate Extraction Match:**
   - `B_RULE`: **30.10%**
   - `B_ML`: **43.30%**
   - `SEMANTIC_AI (DistilBERT)`: **53.90%** (+23.8% over rules, +10.6% over TF-IDF)

2. **Decided Coverage:**
   - `B_RULE`: **35.70%** (Abstains on 64.3% of open-form inputs)
   - `B_ML`: **73.10%**
   - `SEMANTIC_AI (DistilBERT)`: **90.40%** (Resolves 90.4% of open-form inputs)

3. **Overall Utility Accuracy:**
   - `B_RULE`: **33.70%**
   - `B_ML`: **60.60%**
   - `SEMANTIC_AI (DistilBERT)`: **75.00%** (+41.3% absolute utility improvement)

4. **Pair Consistency Rate:**
   - `B_RULE`: **24.80%** (124 / 500 pairs)
   - `B_ML`: **40.60%** (203 / 500 pairs)
   - `SEMANTIC_AI (DistilBERT)`: **58.60%** (293 / 500 pairs)

---

## 4. Final Scientific Conclusion

In strict compliance with the Phase P5.5b decision criteria:

> [!IMPORTANT]
> **1. Need for Semantic Generalization:** **DEMONSTRATED.**  
> Frozen deterministic rules (`B_RULE`) fail to parse 64.3% of open-form clinical claims, collapsing to 35.7% coverage and 33.7% overall utility accuracy.  
> **2. Benefit of Semantic AI Claim Binder:** **DEMONSTRATED FOR GENERALIZATION & ACTIVE COVERAGE.**  
> An actually executed pretrained contextual transformer (`distilbert-base-uncased`) increases predicate extraction from 30.10% to 53.90%, expands coverage from 35.70% to 90.40%, and increases overall verification utility from 33.70% to 75.00%.  
> **3. Safety Imperative:** Semantic parsing errors can induce residual UAR (14.60% on open-form adversarial text). Therefore, **the ContextBind architecture strictly routes all semantic AI predicates through the frozen symbolic FHIR verifier (`OracleTemporalVerifier`) with confidence-thresholded fail-closed (`HOLD`) fallback.**
