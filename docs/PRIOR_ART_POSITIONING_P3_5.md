# ContextBind — Prior Art & Scientific Differentiation (Phase P3.5)

**Document Status:** FROZEN  
**Phase:** P3.5 (Scientific Reframing)

---

## 1. Prior Art Landscape & Boundary Demarcation

ContextBind builds upon and differentiates itself from five distinct subfields in clinical AI, NLP, and biomedical informatics:

| Prior Art Category | Representative Literature / Methods | Fundamental Mechanism | ContextBind Scientific Boundary & Difference |
| :--- | :--- | :--- | :--- |
| **1. Generic Clinical Factuality Checking** | Pugh et al. (PMLR 2026), Clinical Entailment models | Post-hoc NLP verification comparing generated text against reference text notes. | **Runtime Pre-Action Interlock:** Not a post-hoc text editor; ContextBind intercepts high-risk agent *tool calls* before execution and verifies claims against longitudinal *structured FHIR timelines*, not static notes. |
| **2. Longitudinal Temporal Reasoning Benchmarks** | **TIMER** (Nature Digital Medicine 2025/2026), **LongMedBench** (MICCAI 2026), **ClinTraceBench** (arXiv Sept 2026) | Diagnostic benchmarks evaluating LLM capability to answer historical longitudinal medical questions. | **Action-Conditioned Enforcement:** Rather than passively benchmarking QA loss, ContextBind provides an active neuro-symbolic enforcement mechanism to prevent agent decision failure during tool execution. |
| **3. Patient Identity & Entity Resolution** | Standard MPI (Master Patient Index), FHIR Patient Matching | Deterministic string matching and probabilistic record linkage across demographics. | **Orthogonal Dimension:** ContextBind assumes patient identity is already matched; it resolves internal temporal consistency, trend validity, and episode coherence across genuine records of the *same* patient. |
| **4. FHIR Provenance & Audit Logging** | FHIR Provenance Resource, W3C PROV-O | Cryptographic signatures and author attribution metadata tracking data origin. | **Semantic & Trend Verification:** Provenance confirms *who* wrote a record; ContextBind verifies whether an agent's multi-turn clinical deduction *logically follows* from the recorded trajectory. |
| **5. Dual-Stream Agent Memory Architectures** | Long-term memory consolidation, RAG summarization buffers | Compressing past dialogue and clinical history into vector/summary buffers. | **Evidence Grounding Interlock:** ClinTraceBench showed compressed memories lose temporal relations; ContextBind forces agent actions to ground in raw canonical timeline evidence rather than lossy memory summaries. |

---

## 2. Core Defensible Scientific Contribution

ContextBind does not claim to invent generic clinical fact checking, entity resolution, or temporal QA benchmarks. Its precise scientific contribution is:

> **Core Contribution:** Source-verifiable temporal claim binding at the clinical tool-execution boundary (a pre-action runtime interlock enforcing verifiable longitudinal evidence before autonomous agent tool calls execute).

### 2.1 Adjacent Fields & Specific Boundaries
- **Source-Grounded Clinical Proposition Extraction:** Extracting verifiable propositions from clinical text.
- **Clinical Factuality Verification:** Post-hoc summarization consistency checking.
- **Longitudinal Temporal Reasoning Benchmarks:** Passive QA benchmarks (e.g. TIMER, LongMedBench, ClinTraceBench).
- **Generic Pre-Action Agent Verification / Gating:** General tool call security middleware.

**Prior-Art Differentiation:** **MODERATE–STRONG, pending implementation-level comparison** (Differentiated specifically by combining semantic claim parsing with deterministic longitudinal FHIR verification at the pre-action tool call enforcement boundary).

---

## 3. Disallowed Claims & Scientific Governance
- **Strict Prohibition:** Under no circumstances will ContextBind claim to be "world-first", "clinically validated in human trials", or a "medical diagnostic platform".
- **Empirical Standard:** All claims of safety improvement must be quantified via Unsafe Action Release Rate ($\text{UAR}$) and Benign Action Block Rate ($\text{BABR}$) with 95% bootstrap confidence intervals against strong baselines ($B1$, $B2$, $B_{ORACLE}$).
