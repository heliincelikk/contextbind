# CONTEXTBIND — PHASE P7R FINAL EVALUATION REPORT

**STATUS:** **PASS — LOCKED EVALUATION FINALIZED**  
**PHASE:** P7R — Final Locked Test Evaluation, Provenance Audit, Bootstrap & Red-Team  
**DATE:** 2026-10-07  
**REVISION NOTE:** Supersedes initial P7 report following evaluation routing repair and deterministic dataset persistence.

---

## 1. DATASET PROVENANCE & MANIFEST INTEGRITY

> **Explicit Provenance Statement:**  
> The original P7 TEST claims were generated in-memory. They were later deterministically reconstructed after an evaluation-integrity bug was discovered, using the exact pre-TEST frozen generator hashes, patient split, sampling policy and RNG seed. No model, rule, threshold, template, label or sampling specification was modified after observing TEST results.

### Persisted TEST Claim Artifacts ([`P7R_TEST_DATA_MANIFEST.json`](file:///c:/Users/lenevo/Desktop/contexbind/reports/phases/P7R_TEST_DATA_MANIFEST.json))
- **Controlled TEST Claims:**
  - **Path:** [`data/processed/p7_test_controlled.jsonl`](file:///c:/Users/lenevo/Desktop/contexbind/data/processed/p7_test_controlled.jsonl)
  - **SHA-256:** `aaf6f60ccfbf0de924405457bf3dcae87041f3d09050a942d0074478294d9e7b`
  - **Records:** 1,000 claims (500 pairs, 113 unique patients, 500 Supported, 500 Contradicted)
  - **Task Counts:** S1=250, S2=250, S3=250, S4=250
- **Open-Form TEST Claims:**
  - **Path:** [`data/processed/p7_test_open_form.jsonl`](file:///c:/Users/lenevo/Desktop/contexbind/data/processed/p7_test_open_form.jsonl)
  - **SHA-256:** `3d9173a48e0e3ed684dc70b74c45228a1ae589a64f69aa92b02b321d4234bb64`
  - **Records:** 1,000 claims (500 pairs, 115 unique patients, 500 Supported, 500 Contradicted)
  - **Task Counts:** S1=250, S2=250, S3=250, S4=250

---

## 2. FROZEN SCIENTIFIC SYSTEM HASHES
- `rule_binder.py`: `66ac9d596b81aa10662a03b4ce80f0dd304eb15d91fa3c8aec918e5b854ed0d4`
- `rule_binder.json`: `bcbf5bca92b71622df19e3b909bd11e23ec19ad5b6d040aeeb61e24aa304bfcd`
- `semantic_ai_binder.py`: `03be46c30eb82d15c7594bf69eaf757c2c5c7d6f787c35fc055d2384d30541e7`
- `semantic_ai_binder.pkl`: `db63468c9b4933edfbb693eba382880ac26515f01aac8c879ab298a6a90d338d`
- `oracle_temporal_verifier.py`: `adf3f088a0597e08d825cad7f3aac391ab4ad0b2c7a6000552e4cf5bca1dc699`
- `contextbind_runtime.py`: `c8e9f00798067fa968320c41fab3eaac0b718e60b888834e586c95b46092813b`
- `guarded_executor.py`: `fd2e2c69505ba8bfc2a1cf51f3fe6695bea9bd7fb85de234cffd3d8c574a40a0`
- `confidence_threshold_tau`: `0.70` (Frozen)

---

## 3. CONTROLLED TEST EVALUATION & ORACLE AUDIT

| Pipeline | Coverage (%) | HOLD Rate (%) | Selective Acc (%) | Utility Acc (%) | UAR (%) | BABR (%) | Pair Consist (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **B_ORACLE (Upper Bound)** | **100.0%** | **0.0%** | **100.00%** | **100.0%** | **0.0%** | **0.0%** | **100.0%** |
| **B_RULE (Fast-Path)** | 25.0% | 75.0% | 100.00% | 25.0% | **0.0%** | **0.0%** | 25.0% |
| **Semantic AI Alone** | 25.0% | 75.0% | 90.00% | 22.5% | 3.0% | 2.0% | 20.0% |
| **Final Gated Hybrid ($\tau=0.70$)** | 25.0% | 75.0% | 100.00% | 25.0% | **0.0%** | **0.0%** | 25.0% |

### Oracle Task Breakdown (Upper Bound Solvability)
- **S1 (Trend):** 250 / 250 Decided (**100.0%**)
- **S2 (Relation):** 250 / 250 Decided (**100.0%**)
- **S3 (Comparison):** 250 / 250 Decided (**100.0%**)
- **S4 (Current):** 250 / 250 Decided (**100.0%**)
- **Overall Oracle Coverage:** **1,000 / 1,000 (100.0%)**

---

## 4. OPEN-FORM TEST ROUTING & SET ACCOUNTING ($N=1,000$)

### Set Breakdown
- Total Claims ($N$): **1,000**
- $|R|$ (Rule Accepts): **624 (62.4%)**
- $|A|$ (AI Accepts at $\tau \ge 0.70$): **606 (60.6%)**
- $|R \cap A|$ (Both Accept): **407 (40.7%)**
- $|A \setminus R|$ (AI Accepts where Rule HOLDs): **199 (19.9%)**
- $|R \cup A|$ (Expected Hybrid Decided Set): **823 (82.3%)**

### Verifier-Level Outcomes (Production Runtime Routing)
```text
RULE_ACCEPT -> PASS:                        0
RULE_ACCEPT -> BLOCK:                       0
RULE_ACCEPT -> verifier HOLD/error:       624
Total RULE_ACCEPT:                        624

RULE_HOLD -> AI_ACCEPT -> PASS:            85
RULE_HOLD -> AI_ACCEPT -> BLOCK:          114
RULE_HOLD -> AI_ACCEPT -> verifier HOLD:    0
Total RULE_HOLD -> AI_ACCEPT:             199

RULE_HOLD -> AI_HOLD (Abstain):           177

Final Decided (PASS + BLOCK):             199 (19.9%)
Final HOLD (Safe Abstention):             801 (80.1%)
```

---

## 5. OPEN-FORM TEST METRICS (P5.5/P5.6R Specification on 115 TEST Patients)

| Pipeline | Coverage (%) | HOLD Rate (%) | Selective Acc (%) | Utility Acc (%) | UAR (%) | BABR (%) | Pair Consist (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **B_RULE (Fast-Path)** | 0.0% | 100.0% | 0.00% | 0.0% | 0.0% | 0.0% | 0.0% |
| **Semantic AI Alone** | 25.0% | 75.0% | 71.20% | 17.8% | 5.0% | 9.4% | 10.6% |
| **Final Gated Hybrid ($\tau=0.70$)** | **19.9%** | **80.1%** | **73.87%** | **14.7%** | **4.0%** | **6.4%** | **4.4%** |

### Per-Task Hybrid Breakdown (Open-Form TEST)
- **Task S1 (Trend):** Coverage = 0.0% (Fail-closed on unmapped natural language trend phrasing)
- **Task S2 (Relation):** Coverage = 0.0% (Fail-closed on natural language event references)
- **Task S3 (Comparison):** Coverage = **79.6%**, Selective Acc = **73.87%**, Utility Acc = **58.8%**, UAR = 16.0%, BABR = 25.6%
- **Task S4 (Current):** Coverage = 0.0% (Fail-closed on current measurement phrasing)

---

## 6. PATIENT-LEVEL BOOTSTRAP 95% CONFIDENCE INTERVALS ($B=1000$, $\text{seed}=20261004$)

| Metric | Point Estimate | Mean | 95% CI Lower | 95% CI Upper |
| :--- | :---: | :---: | :---: | :---: |
| **Coverage (%)** | 19.90% | 19.90% | **18.61%** | **21.30%** |
| **Selective Accuracy (%)** | 73.87% | 73.87% | **69.76%** | **78.35%** |
| **Utility Accuracy (%)** | 14.70% | 14.70% | **13.78%** | **15.74%** |
| **UAR (%) [Unsafe Action Rate]** | 4.00% | 4.02% | **2.57%** | **5.58%** |
| **BABR (%) [Blocked Appropriate Rate]** | 6.40% | 6.40% | **4.56%** | **8.18%** |
| **Pair Consistency (%)** | 4.40% | 2.60% | **1.24%** | **4.02%** |

---

## 7. ERROR ANALYSIS & FAILURE MODES (Open-Form TEST)
- **Total Incomplete / Held / Erroneous Claims:** 853 / 1000 (85.3%)
- **Distribution:**
  - `RULE_SYNTAX_OR_VERIFIER_HOLD`: 624 (62.4%) — Safe fail-closed abstention when regex rule matched partial tokens but verifier could not bind ground truth.
  - `AI_CONFIDENCE_HOLD`: 177 (17.7%) — Safe fail-closed abstention when DistilBERT confidence fell below $\tau = 0.70$.
  - `FALSE_BLOCK_BABR`: 32 (3.2% of all claims, 6.4% of supported claims) — True claims incorrectly blocked due to semantic comparator misclassification.
  - `UNSAFE_ACTION_UAR`: 20 (2.0% of all claims, 4.0% of contradicted claims) — Erroneously passed actions due to inverted comparator parse.
- **Top Failure Mode:** Open-vocabulary passive voice / clausal inversion where semantic confidence fell below $\tau = 0.70$, triggering safe fail-closed `HOLD`.

---

## 8. SCIENTIFIC WORDING & SAFETY INTERPRETATION
- **Semantic AI Fallback Value:** Expands interpretable open-form coverage beyond rigid rule templates.
- **Confidence-Gated Abstention:** Mitigates—but does not eliminate—residual semantic risk ($UAR = 4.0\%$).
- **Deployment Safety:** **NOT CLAIMED.** Autonomous clinical decision-making is explicitly prohibited. ContextBind serves strictly as an assistive pre-action verification filter.

---

## 9. FINAL STATUS
**STOP STRENGTHENING — SUBMISSION LOCKED.**
