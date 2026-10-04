# ContextBind — System Boundaries & Benchmark Limitations

**Document Version:** 1.0.0  
**Phase:** P0 (Baseline Preflight)

---

## 1. System Scope & Role Boundary
- **Not a Diagnostic or Prescriptive System**: ContextBind is strictly a pre-action runtime safety interlock / middleware layer designed to gate tool calls made by autonomous clinical AI agents. It does not perform clinical diagnosis, triage, disease risk modeling, or drug recommendation.
- **Unverified Clinical Claims**: ContextBind is an algorithmic research prototype under active empirical benchmarking. Terms such as "clinically validated", "production ready", or "world-first" are strictly disallowed in all technical documentation, presentations, and submissions.

---

## 2. Benchmark & Generation Limitations
- **Synthetic Distribution of T3 (Mixed-Time Context)**: The distribution and difficulty profile of mixed-time bundles ($T3$) are constructed algorithmically by our perturbation generator. While designed to simulate realistic agent multi-turn retrieval contamination, synthetic corruptions inherently reflect generator assumptions rather than observed natural EHR failure distributions.
- **Synthea Synthetics vs. Natural EHR Noise**: Initial development and baseline validation leverage Synthea-generated FHIR R4 records. While structurally conformant and clinically plausible, Synthea records exhibit cleaner timestamp continuity and fewer unstructured transcription anomalies than production hospital EHRs.
- **MIMIC Demonstration Scope**: Any external validation on MIMIC-IV FHIR demo data serves solely as an external domain sanity check for timestamp and resource representation, not as formal real-world clinical validation.

---

## 3. Threat Model Boundaries (Phase Scope)
- **Included Attacks (Phase 1–8)**:
  - $T1$: Stale-state replay (same patient, superseded state).
  - $T2$: Wrong encounter (same patient, inactive encounter).
  - $T3$: Mixed-time context (uncoordinated bundle temporal states).
- **Deferred / Out of Scope**:
  - $T4$: Cross-patient relabeling with adversarial identifier injection.
  - Multi-institutional federated ID reconciliation.
  - Natural language parsing of raw unstructured clinical notes without corresponding FHIR structured event metadata.
