# ContextBind

**Pre-Action Runtime Safety Interlock for Clinical AI Agents**

ContextBind validates whether the clinical evidence supporting a high-risk AI agent tool call is genuinely bound to the **correct patient**, **correct encounter**, **correct time frame**, and **current active clinical state** before that action is executed.

---

## Core Problem
Clinical AI agents can retrieve a real, factually correct piece of information about the right patient and still cause serious clinical harm if that evidence originates from the wrong encounter, an outdated historical state, or an uncoordinated mixed-time context bundle.

ContextBind acts as a pre-action runtime interlock returning one of three discrete outcomes:
- **`PASS`**: Evidence is temporally and contextually coherent with the active clinical state and target encounter.
- **`HOLD`**: Ambiguities or missing timestamps require clinical clarification/human confirmation.
- **`BLOCK`**: Explicit contradiction detected (superseded state, wrong encounter, or stale replay).

> **Disclaimer**: ContextBind is a pre-action safety interlock, not a medical diagnosis or treatment recommendation system. No unverified claims ("clinically validated", "world-first") are made.

---

## Targeted Threat Model (Attack Families)
- **`T1 — Stale-State Replay`**: Evidence is authentic and belongs to the correct patient, but has been superseded by a newer clinical state (e.g., discontinued medication, resolved condition).
- **`T2 — Wrong Encounter`**: Evidence belongs to the correct patient but was recorded during a distinct past or unrelated clinical encounter/admission.
- **`T3 — Mixed-Time Context`**: Evidence bundle contains a mixture of active and historical/superseded records, testing context coherence.

---

## Repository Structure
```
contextbind/
├── README.md
├── docs/
│   ├── METHODOLOGY_FROZEN.md   # Frozen scientific rules, protocols, and constraints
│   └── LIMITATIONS.md          # Synthetic benchmark and runtime boundary limitations
├── data/
│   ├── raw/                    # Raw FHIR R4 bundles (Synthea / MIMIC demo)
│   ├── interim/                # Canonical timeline extractions
│   └── processed/              # Evaluation datasets & split manifests
├── src/
│   ├── ingestion/              # FHIR R4 parsers and event extractors
│   ├── timeline/               # Canonical timeline synthesis & state tracking
│   ├── attacks/                # T1/T2/T3 corruption generators
│   ├── baselines/              # B1 deterministic rule baseline & LLM baselines
│   ├── leakage/                # Metadata-only generator leakage sentinel
│   ├── models/                 # Context coherence models (if warranted by B1 gap)
│   └── evaluation/             # Metrics (UAR, BABR, Bootstrap CI, multi-seed)
├── reports/
│   └── phases/                 # Phase execution and gate reports
├── tests/                      # Unit and integration test suite
├── configs/                    # Reproducible experiment configurations
└── .gitignore
```

---

## Scientific Rigor & Protocol
1. **B1 Rule Baseline Frozen Before Test Evaluation**: The deterministic baseline rules and implementation are committed and hash-locked prior to viewing any test split results.
2. **Patient-Disjoint Partitions**: All dataset splits (Train / Validation / Test) and corruption donor pools are partitioned strictly at the patient identifier level.
3. **Metadata Leakage Sentinel**: Controlled validation ensuring corruption generators do not introduce non-clinical metadata/formatting artifacts detectable above chance.
4. **Multi-Seed & Bootstrap Confidence Intervals**: All benchmark metrics report mean, standard deviation, and 95% bootstrap confidence intervals across $\ge 3$ independent runs.
