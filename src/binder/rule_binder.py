"""
ContextBind — Rule-Based Semantic Claim Binder (Baseline B_RULE)
Deterministic parsing of natural language temporal claims into structured predicates.
Strictly uses Python Standard Library.
"""

import re
from typing import Dict, Any, Optional, List, Tuple

class RuleBasedClaimBinder:
    def __init__(self, concept_vocab: Optional[Dict[str, str]] = None):
        """
        concept_vocab: Mapping from concept clean string (lowercase) -> LOINC / SNOMED code
        """
        self.concept_vocab = concept_vocab or {}
        # Sort concept strings by length descending for longest prefix matching
        self._sorted_concepts = sorted(self.concept_vocab.keys(), key=len, reverse=True)

    def fit(self, train_claims: List[Dict[str, Any]]) -> "RuleBasedClaimBinder":
        """
        Builds concept vocabulary and display dictionaries strictly from training split.
        """
        vocab = {}
        for c in train_claims:
            code = c.get("clinical_code")
            disp = c.get("clinical_display", "")
            if code and disp:
                # Clean concept name by removing bracketed descriptors
                clean = disp.split("[")[0].strip().lower()
                if clean and clean not in vocab:
                    vocab[clean] = code
                # Also store individual event names for S2
                if c.get("task_code") == "S2" and " vs " in disp:
                    parts = disp.split(" vs ")
                    for p in parts:
                        p_clean = p.split("[")[0].strip().lower()
                        if p_clean and p_clean not in vocab:
                            vocab[p_clean] = p_clean

        self.concept_vocab = vocab
        self._sorted_concepts = sorted(self.concept_vocab.keys(), key=len, reverse=True)
        return self

    def parse(self, claim_text: str, candidate_events: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Parses claim_text into a structured temporal predicate.
        """
        text_lower = claim_text.lower().strip()

        # 1. Identify Task Type
        task_type = self._detect_task_type(text_lower)

        # 2. Extract Slot Values
        concept_code = None
        claim_type = None
        comparator = None
        temporal_window = None
        claimed_value = None
        event_A_id = None
        event_B_id = None

        if task_type == "S1":
            temporal_window = "LAST_3"
            # Extract concept
            concept_code = self._extract_concept(text_lower)
            # Extract trend direction
            if any(w in text_lower for w in ["increased", "increasing", "rising", "rise"]):
                claim_type = "TREND_INCREASING"
                comparator = "GT"
            elif any(w in text_lower for w in ["decreased", "decreasing", "downward", "drop", "fall"]):
                claim_type = "TREND_DECREASING"
                comparator = "LT"
            else:
                claim_type = "TREND_INCREASING"
                comparator = "GT"

        elif task_type == "S2":
            # Detect temporal relation
            # Check for BEFORE keywords
            is_before = False
            is_after = False
            split_keyword = None

            for kw in ["prior to", "preceded", "earlier than", "before"]:
                if kw in text_lower:
                    is_before = True
                    split_keyword = kw
                    break

            if not is_before:
                for kw in ["following", "succeeded", "subsequent to", "after"]:
                    if kw in text_lower:
                        is_after = True
                        split_keyword = kw
                        break

            if is_before:
                claim_type = "BEFORE"
                comparator = "LT"
            elif is_after:
                claim_type = "AFTER"
                comparator = "GT"
            else:
                claim_type = "BEFORE"
                comparator = "LT"

            # Extract event A and event B references
            if candidate_events and len(candidate_events) >= 2:
                # Resolve using candidate events displays against claim text
                # We identify which event is mentioned first vs second
                ev1, ev2 = candidate_events[0], candidate_events[1]
                name1 = (ev1.get("clinical_display") or "").split("[")[0].strip().lower()
                name2 = (ev2.get("clinical_display") or "").split("[")[0].strip().lower()

                pos1 = text_lower.find(name1) if name1 else -1
                pos2 = text_lower.find(name2) if name2 else -1

                if pos1 != -1 and pos2 != -1:
                    if pos1 < pos2:
                        event_A_id = ev1.get("resource_id")
                        event_B_id = ev2.get("resource_id")
                    else:
                        event_A_id = ev2.get("resource_id")
                        event_B_id = ev1.get("resource_id")
                else:
                    event_A_id = ev1.get("resource_id")
                    event_B_id = ev2.get("resource_id")

        elif task_type == "S3":
            concept_code = self._extract_concept(text_lower)
            # Detect comparison
            if any(w in text_lower for w in ["higher", "exceeds", "elevated", "greater than", "above"]):
                claim_type = "HIGHER_THAN_PREVIOUS"
                comparator = "GT"
            elif any(w in text_lower for w in ["lower", "falls below", "reduced", "less than", "below"]):
                claim_type = "LOWER_THAN_PREVIOUS"
                comparator = "LT"
            else:
                claim_type = "HIGHER_THAN_PREVIOUS"
                comparator = "GT"

        elif task_type == "S4":
            claim_type = "CURRENT_VALUE"
            concept_code = self._extract_concept(text_lower)
            # Extract numeric value
            # Regex for numbers (float or integer)
            matches = re.findall(r"[-+]?\d*\.?\d+", claim_text)
            if matches:
                try:
                    # In S4, the claimed numeric value is the primary number
                    # Filter out any known LOINC-like dashes if matched, take the last or most plausible number
                    for m in reversed(matches):
                        val = float(m)
                        claimed_value = val
                        break
                except ValueError:
                    claimed_value = None

        return {
            "task_type": task_type,
            "clinical_concept": concept_code,
            "claim_type": claim_type,
            "temporal_window": temporal_window,
            "comparator": comparator,
            "claimed_value": claimed_value,
            "event_A_id": event_A_id,
            "event_B_id": event_B_id
        }

    def _detect_task_type(self, text_lower: str) -> str:
        # S1: Trend indicators
        if any(w in text_lower for w in ["last 3", "preceding 3", "prior 3", "trajectory", "course over recent"]):
            return "S1"
        # S2: Relation indicators
        if any(w in text_lower for w in ["was recorded", "occurred", "documentation of", "took place", "succeeded", "preceded", "prior to", "following", "subsequent to", "earlier than"]):
            return "S2"
        # S3: Comparison to previous indicators
        if any(w in text_lower for w in ["than the previous", "prior value", "preceding encounter", "prior evaluation", "exceeds", "falls below"]):
            return "S3"
        # S4: Current / Latest state indicators
        if any(w in text_lower for w in ["current", "most recently", "latest recorded", "active", "stands at"]):
            return "S4"
        # Fallback heuristic
        if any(c.isdigit() for c in text_lower):
            return "S4"
        return "S3"

    def _extract_concept(self, text_lower: str) -> Optional[str]:
        # Longest match against known concept dictionary
        for clean_str in self._sorted_concepts:
            if clean_str in text_lower:
                return self.concept_vocab[clean_str]
        return None
