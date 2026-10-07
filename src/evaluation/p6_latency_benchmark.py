"""
ContextBind — Phase P6 Runtime Latency Benchmark
Measures:
1. Cold Start Initialization Latency (Frozen Artifact Deserialization + Model Weight Loading)
2. Warm Request Latency:
   - Frozen Rule Fast-Path (B_RULE)
   - Frozen Confidence-Gated Semantic AI Binder (DistilBERT)
   - Deterministic Symbolic FHIR Verifier (OracleTemporalVerifier)
   - End-to-End Rule Request (verify_action)
   - End-to-End AI Fallback Request (verify_action)
   - End-to-End Full Guarded EHR Action Execution (execute_guarded_action)

Outputs summary statistics and saves reports/phases/P6_LATENCY.csv.
"""

import os
import sys
import time
import json
import numpy as np
import pandas as pd
from typing import List, Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.runtime.contextbind_runtime import ContextBindRuntime
from src.runtime.guarded_executor import GuardedToolExecutor

def run_latency_benchmark(n_iterations: int = 50, output_csv: str = "reports/phases/P6_LATENCY.csv"):
    print("=== ContextBind Runtime Latency Benchmark ===")
    
    # 1. Measure Cold Start Time
    t_cold_start_0 = time.perf_counter()
    runtime = ContextBindRuntime(
        db_path="data/interim/contextbind_timeline.sqlite",
        rule_artifact_path="artifacts/frozen/rule_binder.json",
        ai_artifact_path="artifacts/frozen/semantic_ai_binder.pkl",
        audit_db_path="data/interim/benchmark_audit_log.sqlite",
        tau=0.70
    )
    executor = GuardedToolExecutor(runtime=runtime, audit_db_path="data/interim/benchmark_audit_log.sqlite")
    cold_start_ms = (time.perf_counter() - t_cold_start_0) * 1000.0
    print(f"Cold Start Initialization Time: {cold_start_ms:.2f} ms ({cold_start_ms/1000.0:.3f} s)")

    # Load canonical demo scenarios
    with open("reports/phases/P6_DEMO_SCENARIOS.json", "r", encoding="utf-8") as f:
        scenarios_data = json.load(f)
    scenarios = scenarios_data["scenarios"]

    rule_req = next(s for s in scenarios if s["id"] == "D1")
    ai_req = next(s for s in scenarios if s["id"] == "D3")
    hold_req = next(s for s in scenarios if s["id"] == "D5")

    # Warmup runs (not included in benchmark metrics)
    print("Performing warmup executions...")
    for req in [rule_req, ai_req, hold_req]:
        runtime.verify_action(req)
        executor.execute_guarded_action(req, guard_enabled=True)

    latencies = {
        "rule_parser_ms": [],
        "ai_binder_ms": [],
        "symbolic_verifier_ms": [],
        "e2e_rule_verify_ms": [],
        "e2e_ai_verify_ms": [],
        "e2e_guarded_exec_ms": []
    }

    print(f"Running {n_iterations} warm benchmark iterations per component...")

    # 1. Rule Parser Alone
    for _ in range(n_iterations):
        t0 = time.perf_counter()
        _ = runtime.rule_binder.parse(rule_req["claim_text"])
        latencies["rule_parser_ms"].append((time.perf_counter() - t0) * 1000.0)

    # 2. AI Binder Alone (DistilBERT contextual inference)
    for _ in range(n_iterations):
        t0 = time.perf_counter()
        _ = runtime.ai_binder.parse(ai_req["claim_text"])
        latencies["ai_binder_ms"].append((time.perf_counter() - t0) * 1000.0)

    # 3. Symbolic Verifier Alone (Direct SQLite timeline verification)
    rule_pred = runtime.rule_binder.parse(rule_req["claim_text"])
    claim_rec = {
        "task_code": rule_pred.get("task_type", "S3"),
        "patient_id": rule_req["patient_id"],
        "claim_text": rule_req["claim_text"],
        "structured_predicate": {
            "concept": rule_pred.get("clinical_concept"),
            "claim_type": rule_pred.get("claim_type"),
            "comparator": rule_pred.get("comparator"),
            "window": rule_pred.get("temporal_window"),
            "claimed_direction": None,
            "claimed_value": rule_pred.get("claimed_value")
        },
        "source_event_ids": ["001cc5e4-71a3-8e4c-8724-a94a0d3249f8", "001cc5e4-71a3-8e4c-80a7-446ed0a1bd63"]
    }
    for _ in range(n_iterations):
        t0 = time.perf_counter()
        _ = runtime.verifier.verify_claim_predicate(claim_rec)
        latencies["symbolic_verifier_ms"].append((time.perf_counter() - t0) * 1000.0)

    # 4. End-to-End Rule Lane Verification
    for _ in range(n_iterations):
        t0 = time.perf_counter()
        _ = runtime.verify_action(rule_req)
        latencies["e2e_rule_verify_ms"].append((time.perf_counter() - t0) * 1000.0)

    # 5. End-to-End AI Fallback Lane Verification
    for _ in range(n_iterations):
        t0 = time.perf_counter()
        _ = runtime.verify_action(ai_req)
        latencies["e2e_ai_verify_ms"].append((time.perf_counter() - t0) * 1000.0)

    # 6. End-to-End Guarded Tool Execution
    for _ in range(n_iterations):
        t0 = time.perf_counter()
        _ = executor.execute_guarded_action(rule_req, guard_enabled=True)
        latencies["e2e_guarded_exec_ms"].append((time.perf_counter() - t0) * 1000.0)

    # Compute Statistics
    rows = []
    # Add Cold Start row
    rows.append({
        "Component / Operation": "cold_start_initialization_ms",
        "N": 1,
        "Mean (ms)": round(cold_start_ms, 3),
        "Std (ms)": 0.0,
        "P50 (ms)": round(cold_start_ms, 3),
        "P95 (ms)": round(cold_start_ms, 3),
        "Min (ms)": round(cold_start_ms, 3),
        "Max (ms)": round(cold_start_ms, 3)
    })

    for component, times in latencies.items():
        arr = np.array(times)
        rows.append({
            "Component / Operation": component,
            "N": len(arr),
            "Mean (ms)": round(float(np.mean(arr)), 3),
            "Std (ms)": round(float(np.std(arr)), 3),
            "P50 (ms)": round(float(np.median(arr)), 3),
            "P95 (ms)": round(float(np.percentile(arr, 95)), 3),
            "Min (ms)": round(float(np.min(arr)), 3),
            "Max (ms)": round(float(np.max(arr)), 3)
        })

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df.to_csv(output_csv, index=False)
    print("\n=== LATENCY BENCHMARK RESULTS (WARM REQUESTS) ===")
    print(df.to_string(index=False))
    print(f"\nSaved benchmark metrics to {output_csv}")
    return df

if __name__ == "__main__":
    run_latency_benchmark()
