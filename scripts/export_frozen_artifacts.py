"""
Exports frozen P5.6 scientific artifacts for P6 zero-training runtime deployment.
"""

import os
import sys
import json
import hashlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.binder.rule_binder import RuleBasedClaimBinder
from src.binder.semantic_ai_binder import SemanticAIBinder

def export_artifacts():
    train_path = "data/processed/p4_final_train.jsonl"
    print(f"Reading training claims from {train_path} for one-time offline artifact export...")
    with open(train_path, "r", encoding="utf-8") as f:
        train_claims = [json.loads(line) for line in f]

    print("Fitting RuleBasedClaimBinder...")
    rule_binder = RuleBasedClaimBinder().fit(train_claims)
    rule_art_path = "artifacts/frozen/rule_binder.json"
    rule_binder.save(rule_art_path)
    print(f"Saved Rule artifact to {rule_art_path}")

    print("Fitting SemanticAIBinder (DistilBERT contextual embeddings)...")
    ai_binder = SemanticAIBinder(model_name="distilbert/distilbert-base-uncased", seed=20261004).fit(train_claims)
    ai_art_path = "artifacts/frozen/semantic_ai_binder.pkl"
    ai_binder.save(ai_art_path)
    print(f"Saved Semantic AI artifact to {ai_art_path}")

    # Compute SHA-256 hashes
    hashes = {}
    for p in [rule_art_path, ai_art_path]:
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        hashes[os.path.basename(p)] = h
        print(f"SHA-256 [{os.path.basename(p)}]: {h}")

    with open("artifacts/frozen/artifact_hashes.json", "w", encoding="utf-8") as f:
        json.dump(hashes, f, indent=2)

    print("Export complete!")

if __name__ == "__main__":
    export_artifacts()
