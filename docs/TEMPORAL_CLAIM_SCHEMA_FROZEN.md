# ContextBind — Frozen Temporal Claim Schema & Predicate Grammar

**Document Status:** FROZEN  
**Phase:** P3.5 (Scientific Reframing)  
**Applicability:** Neuro-symbolic claim extraction, structured verification, and pre-action runtime gating.

---

## 1. Core Schema Specification

Every natural language clinical justification provided by an AI agent prior to executing a tool call is parsed into an instantiated `TemporalClaim` tuple:

$$\mathcal{C} = \langle \text{patient\_id}, \text{concept}, \text{claim\_type}, \mathcal{W}_{temporal}, \mathcal{R}_{comparator}, \mathcal{V}_{claimed}, \mathcal{S}_{scope}, \mathcal{A}_{target} \rangle$$

### 1.1 Field Definitions & Types

| Field Name | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `patient_id` | `String` | Canonical target patient identifier. | `urn:uuid:6aab5c5e-...` |
| `concept` | `ConceptCode` | Standardized clinical entity code (LOINC, SNOMED, RxNorm) or canonical concept string. | `2823-3` (Potassium) / `2160-0` (Creatinine) |
| `claim_type` | `Enum` | Semantic assertion category (see §1.2). | `TREND_DECREASING` |
| `temporal_window` | `WindowSpec` | Bounded reference period or longitudinal index constraint. | `LAST_3_OBSERVATIONS`, `CURRENT_ENCOUNTER`, `INTERVAL[t1, t2]` |
| `comparator_relation`| `Enum` | Mathematical or chronological comparator. | `LT`, `GT`, `EQ`, `MONOTONIC_INC`, `MONOTONIC_DEC`, `BEFORE`, `AFTER` |
| `claimed_value_state`| `Any` | Quantitative threshold, directionality, or discrete clinical state asserted by the agent. | `IMPROVING`, `4.5 mmol/L`, `ACTIVE` |
| `source_scope` | `Enum` | Source boundary required by the action context. | `ENCOUNTER_LOCAL`, `CROSS_ENCOUNTER_LONGITUDINAL` |
| `action_type` | `String` | High-risk tool call being intercepted. | `write_discharge_summary`, `update_medication_order` |

---

## 2. Canonical Claim Types & FHIR Verification Predicates

| Claim Type | Natural Language Agent Pattern | Formal Structured Predicate | Objective FHIR Verification Rule |
| :--- | :--- | :--- | :--- |
| **`TREND_DECREASING`** | *"Creatinine has been steadily decreasing over the last 3 measurements."* | $\text{Trend}(\mathcal{O}[-3:], c) = \downarrow$ | $\forall i \in \{1, 2\}, v(\mathcal{O}[-3+i]) < v(\mathcal{O}[-3+i-1])$ |
| **`TREND_INCREASING`** | *"Blood pressure has been rising across the last 3 visits."* | $\text{Trend}(\mathcal{O}[-3:], c) = \uparrow$ | $\forall i \in \{1, 2\}, v(\mathcal{O}[-3+i]) > v(\mathcal{O}[-3+i-1])$ |
| **`TREND_STABLE`** | *"Potassium levels remained stable across recent tests."* | $|\Delta v(\mathcal{O}[-k:])| \le \epsilon$ | $\max(v) - \min(v) \le \epsilon \cdot \text{std}(v)$ |
| **`HIGHER_THAN_PREVIOUS`**| *"Latest glucose is higher than the previous encounter reading."* | $v(o_{latest}) > v(o_{prev})$ | $v(\mathcal{O}[-1]) > v(\mathcal{O}[-2])$ |
| **`LOWER_THAN_PREVIOUS`** | *"Latest eGFR is lower than previous reading."* | $v(o_{latest}) < v(o_{prev})$ | $v(\mathcal{O}[-1]) < v(\mathcal{O}[-2])$ |
| **`BEFORE`** | *"Antibiotic was administered before blood culture draw."* | $t(e_A) < t(e_B)$ | $\text{epoch}(e_A) < \text{epoch}(e_B)$ |
| **`AFTER`** | *"Creatinine spiked after starting ACE inhibitor."* | $t(e_A) > t(e_B)$ | $\text{epoch}(e_A) > \text{epoch}(e_B)$ |
| **`CURRENT_VALUE`** | *"Patient's current potassium is 4.1 mmol/L."* | $v(o_{latest}) = 4.1$ | $|v(\mathcal{O}[-1]) - 4.1| \le \delta$ |
| **`LATEST_VALUE`** | *"Latest hemoglobin recorded is 13.5 g/dL."* | $v(o_{latest}) = 13.5$ | $|v(\mathcal{O}[-1]) - 13.5| \le \delta$ |
| **`PRESENT_IN_CURRENT_ENCOUNTER`** | *"Condition was confirmed during today's visit."* | $o_{source}.enc = e_{target}$ | $o.encounter\_id == e_{target}$ |

---

## 3. Ambiguity & Missing Ground Truth Policy
If a natural language claim cannot be mapped to an objective, mathematically verifiable FHIR predicate (e.g., subjective clinical assertions without structured parameters such as *"patient looks healthier"*), the Semantic Binder outputs an ungroundable state:

$$\text{Decision} = \text{HOLD} \quad (\text{Reason: Unverifiable Subjective Assertion in High-Risk Context})$$
