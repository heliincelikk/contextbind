# ContextBind — Phase P6 Runtime Interlock Integration Tests

**Date:** 2026-10-07  
**Status:** **10/10 PASSED (100%)**  
**Execution Environment:** Python 3.13 (PyTorch 2.14.1+cpu, DistilBERT, Transformers, SQLite)  
**Safety Threshold:** $\tau = 0.70$ (Frozen)  
**Runtime Training:** ZERO (Pre-serialized frozen artifacts loaded from `artifacts/frozen/`)

---

## 1. Test Suite Results (`tests/test_runtime_interlock.py`)

| # | Test Name | Target Invariant / Scenario | Expected Decision | Actual Decision | Execution Allowed | Side Effect Observed | Status |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| 1 | `test_rule_pass_executes` | D1: Rule Fast-Path True (LDL 48.55 < 92.87 mg/dL) | `PASS` | `PASS` | True | Exactly 1 EHR draft commit | **PASS** |
| 2 | `test_rule_block_denies` | D2: Rule Fast-Path Contradicted (LDL 48.55 > 92.87 mg/dL) | `BLOCK` | `BLOCK` | False | 0 (Refused) | **PASS** |
| 3 | `test_ai_fallback_pass_executes` | D3: AI Fallback True ($\tau \ge 0.70$, Calcium 9.82 > 8.84) | `PASS` | `PASS` | True | Exactly 1 EHR handoff commit | **PASS** |
| 4 | `test_ai_fallback_block_denies` | D4: AI Fallback Contradicted ($\tau \ge 0.70$, Calcium 9.82 < 8.84) | `BLOCK` | `BLOCK` | False | 0 (Refused) | **PASS** |
| 5 | `test_low_confidence_holds` | D5: Semantic Claim with $\tau = 0.65 < 0.70$ | `HOLD` | `HOLD` | False | 0 (Held for review) | **PASS** |
| 6 | `test_invalid_schema_holds` | Malformed payload / non-existent patient ID | `HOLD` | `HOLD` | False | 0 (Held for review) | **PASS** |
| 7 | `test_verifier_error_holds` | Verifier SQLite exception / lock simulation | `HOLD` | `HOLD` | False | 0 (Held for review) | **PASS** |
| 8 | `test_no_guard_executes_same_call` | Guard OFF Baseline: Unverified flawed draft | `UNGUARDED` | `UNGUARDED` | True | 1 (Unsafe draft written) | **PASS** |
| 9 | `test_guard_prevents_same_call` | Guard ON Interlock: Same flawed draft intercepted | `BLOCK` | `BLOCK` | False | 0 (Blocked & denied) | **PASS** |
| 10 | `test_single_execution_only` | Idempotency & Single Execution Guarantee | `PASS` | `PASS` | True | Exactly 1 invocation | **PASS** |

---

## 2. Test Fixture Resolution Details

- **Test Cohort Integrity:** Strictly drawn from non-TEST development/training split (`data/processed/p4_final_train.jsonl` & `data/interim/contextbind_timeline.sqlite`).
- **Patient ID:** `001cc5e4-71a3-8e4c-507c-d39178b49be8`
- **Clinical Concept:** `18262-6` (`Cholesterol in LDL [Mass/volume] in Serum or Plasma by Direct assay`)
- **Previous Observation:**
  - Resource ID: `001cc5e4-71a3-8e4c-8724-a94a0d3249f8`
  - Timestamp: `2021-07-13T00:54:59+00:00`
  - Value: `92.87 mg/dL`
- **Latest Observation:**
  - Resource ID: `001cc5e4-71a3-8e4c-80a7-446ed0a1bd63`
  - Timestamp: `2024-07-30T00:54:59+00:00`
  - Value: `48.55 mg/dL`
- **Mathematical Evaluation:**
  - `48.55 < 92.87` $\rightarrow$ **TRUE** (`PASS`)
  - `48.55 > 92.87` $\rightarrow$ **FALSE** (`BLOCK`)

---

## 3. Side Effect Audit Integrity

All tool calls route strictly through `GuardedToolExecutor`. 
- Every decision is logged immutably into `data/interim/runtime_audit_log.sqlite` across two relational tables:
  1. `runtime_audit_log`: Logs `action_id`, `patient_id`, `claim_text`, `semantic_route`, `structured_predicate`, `binder_confidence`, `decision`, `verifier_result`, `reason_codes`, and `tool_executed`.
  2. `clinical_tool_side_effects`: Records tangible side effect commits (`write_clinical_summary_draft`, `commit_handoff_summary`) only when `tool_execution_allowed` is `True`.
- Source FHIR timeline database is **never modified**.
