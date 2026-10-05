"""
ContextBind — Canonical FHIR R4 Ingestion Parser
Strictly uses Python Standard Library (no external dependencies).
Extracts and normalizes Patient, Encounter, Observation, MedicationRequest, Provenance, and Condition.
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

def parse_iso_timestamp(ts_str: Optional[str]) -> Tuple[Optional[str], Optional[float]]:
    """
    Parses ISO-8601 timestamp string into (normalized_iso_utc, utc_epoch_seconds).
    Preserves exact chronology across timezones.
    """
    if not ts_str or not isinstance(ts_str, str):
        return None, None
    try:
        # Standard library datetime.fromisoformat handles offsets like +03:00, -04:00, Z
        clean_ts = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.isoformat(), dt_utc.timestamp()
    except Exception:
        # Fallback for date-only formats (YYYY-MM-DD)
        try:
            dt = datetime.strptime(ts_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return dt.isoformat(), dt.timestamp()
        except Exception:
            return None, None

def clean_reference_id(ref: Optional[str]) -> Optional[str]:
    """
    Strips 'urn:uuid:', 'Patient/', 'Encounter/' prefixes to extract canonical ID.
    """
    if not ref or not isinstance(ref, str):
        return None
    ref = ref.strip()
    if ref.startswith("urn:uuid:"):
        return ref[9:]
    if "/" in ref:
        return ref.split("/")[-1]
    return ref

class FHIRBundleParser:
    """
    Robust FHIR R4 Bundle Parser with non-silent error tracking and strict semantic isolation.
    """
    def __init__(self):
        self.parse_errors: List[Dict[str, Any]] = []

    def parse_bundle_file(self, file_path: str) -> Dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                bundle = json.load(f)
            except Exception as e:
                self.parse_errors.append({
                    "file": file_path,
                    "resource_type": "Bundle",
                    "resource_id": None,
                    "reason": f"JSON decode error: {str(e)}"
                })
                return {
                    "patient": None,
                    "encounters": [],
                    "observations": [],
                    "medication_requests": [],
                    "conditions": [],
                    "provenance": [],
                    "unsupported_resources": 0,
                    "errors": self.parse_errors
                }

        return self.parse_bundle_dict(bundle, source_file=os.path.basename(file_path))

    def parse_bundle_dict(self, bundle: Dict[str, Any], source_file: str = "") -> Dict[str, Any]:
        entries = bundle.get("entry", [])
        
        patient_record = None
        encounters = []
        observations = []
        medication_requests = []
        conditions = []
        provenance_records = []
        unsupported_count = 0

        # First pass: find Patient resource to resolve default subject
        patient_id = None
        patient_deceased_dt_raw = None
        patient_deceased_dt_norm = None
        patient_birth_date = None
        patient_gender = None

        for entry in entries:
            res = entry.get("resource", {})
            if res.get("resourceType") == "Patient":
                patient_id = res.get("id")
                patient_birth_date = res.get("birthDate")
                patient_gender = res.get("gender")
                
                # Check deceased status
                if "deceasedDateTime" in res:
                    patient_deceased_dt_raw = res.get("deceasedDateTime")
                    patient_deceased_dt_norm, _ = parse_iso_timestamp(patient_deceased_dt_raw)
                elif res.get("deceasedBoolean") is True:
                    patient_deceased_dt_raw = "TRUE_WITHOUT_DATE"
                    patient_deceased_dt_norm = None
                
                name_list = res.get("name", [{}])
                name_dict = name_list[0] if name_list else {}
                family_name = name_dict.get("family", "")
                given_names = " ".join(name_dict.get("given", []))

                patient_record = {
                    "patient_id": patient_id,
                    "family_name": family_name,
                    "given_names": given_names,
                    "gender": patient_gender,
                    "birth_date": patient_birth_date,
                    "deceased_date_raw": patient_deceased_dt_raw,
                    "deceased_date_norm": patient_deceased_dt_norm,
                    "source_file": source_file
                }
                break

        # Second pass: parse clinical and provenance resources
        for entry in entries:
            res = entry.get("resource", {})
            rtype = res.get("resourceType", "Unknown")
            rid = res.get("id")

            if rtype == "Patient":
                continue # Already handled in pass 1

            elif rtype == "Encounter":
                subj_ref = clean_reference_id(res.get("subject", {}).get("reference")) or patient_id
                period = res.get("period", {})
                start_raw = period.get("start")
                end_raw = period.get("end")
                start_norm, start_epoch = parse_iso_timestamp(start_raw)
                end_norm, end_epoch = parse_iso_timestamp(end_raw)
                
                enc_class = res.get("class", {}).get("code")
                type_list = res.get("type", [{}])
                enc_type_text = type_list[0].get("text") if type_list else None
                enc_type_code = type_list[0].get("coding", [{}])[0].get("code") if type_list and "coding" in type_list[0] else None

                encounters.append({
                    "encounter_id": rid,
                    "patient_id": subj_ref,
                    "status": res.get("status"),
                    "class_code": enc_class,
                    "type_code": enc_type_code,
                    "type_display": enc_type_text,
                    "start_raw": start_raw,
                    "start_norm": start_norm,
                    "start_epoch": start_epoch,
                    "end_raw": end_raw,
                    "end_norm": end_norm,
                    "end_epoch": end_epoch,
                    "source_file": source_file
                })

            elif rtype == "Observation":
                subj_ref = clean_reference_id(res.get("subject", {}).get("reference")) or patient_id
                enc_ref = clean_reference_id(res.get("encounter", {}).get("reference"))
                
                # Check effective[x]
                effective_raw = res.get("effectiveDateTime")
                effective_type = "effectiveDateTime"
                if not effective_raw and "effectivePeriod" in res:
                    effective_raw = res.get("effectivePeriod", {}).get("start")
                    effective_type = "effectivePeriod"
                elif not effective_raw and "effectiveInstant" in res:
                    effective_raw = res.get("effectiveInstant")
                    effective_type = "effectiveInstant"
                    
                eff_norm, eff_epoch = parse_iso_timestamp(effective_raw)
                
                issued_raw = res.get("issued")
                issued_norm, issued_epoch = parse_iso_timestamp(issued_raw)

                # Code concept
                codeable = res.get("code", {})
                codings = codeable.get("coding", [{}])
                code_val = codings[0].get("code", "") if codings else ""
                code_system = codings[0].get("system", "") if codings else ""
                code_display = codings[0].get("display", codeable.get("text", "")) if codings else codeable.get("text", "")

                # Value extraction
                val_num = None
                val_text = None
                val_unit = None

                if "valueQuantity" in res:
                    vq = res["valueQuantity"]
                    val_num = vq.get("value")
                    val_unit = vq.get("unit") or vq.get("code")
                elif "valueCodeableConcept" in res:
                    vc = res["valueCodeableConcept"]
                    v_codings = vc.get("coding", [{}])
                    val_text = v_codings[0].get("display", vc.get("text")) if v_codings else vc.get("text")
                elif "valueString" in res:
                    val_text = res["valueString"]
                elif "valueBoolean" in res:
                    val_text = str(res["valueBoolean"])

                observations.append({
                    "observation_id": rid,
                    "patient_id": subj_ref,
                    "encounter_id": enc_ref,
                    "status": res.get("status"),
                    "code": code_val,
                    "system": code_system,
                    "display": code_display,
                    "effective_raw": effective_raw,
                    "effective_norm": eff_norm,
                    "effective_epoch": eff_epoch,
                    "effective_type": effective_type,
                    "issued_raw": issued_raw,
                    "issued_norm": issued_norm,
                    "value_numeric": val_num,
                    "value_text": val_text,
                    "unit": val_unit,
                    "source_file": source_file
                })

            elif rtype == "MedicationRequest":
                subj_ref = clean_reference_id(res.get("subject", {}).get("reference")) or patient_id
                enc_ref = clean_reference_id(res.get("encounter", {}).get("reference"))
                
                authored_raw = res.get("authoredOn")
                authored_norm, authored_epoch = parse_iso_timestamp(authored_raw)

                # Medication concept
                med_codeable = res.get("medicationCodeableConcept", {})
                med_codings = med_codeable.get("coding", [{}])
                med_code = med_codings[0].get("code", "") if med_codings else ""
                med_system = med_codings[0].get("system", "") if med_codings else ""
                med_display = med_codings[0].get("display", med_codeable.get("text", "")) if med_codings else med_codeable.get("text", "")

                medication_requests.append({
                    "medication_request_id": rid,
                    "patient_id": subj_ref,
                    "encounter_id": enc_ref,
                    "status": res.get("status"),
                    "intent": res.get("intent"),
                    "code": med_code,
                    "system": med_system,
                    "display": med_display,
                    "authored_raw": authored_raw,
                    "authored_norm": authored_norm,
                    "authored_epoch": authored_epoch,
                    "source_file": source_file
                })

            elif rtype == "Condition":
                subj_ref = clean_reference_id(res.get("subject", {}).get("reference")) or patient_id
                enc_ref = clean_reference_id(res.get("encounter", {}).get("reference"))
                
                onset_raw = res.get("onsetDateTime")
                onset_norm, onset_epoch = parse_iso_timestamp(onset_raw)
                abatement_raw = res.get("abatementDateTime")
                abatement_norm, abatement_epoch = parse_iso_timestamp(abatement_raw)
                
                codeable = res.get("code", {})
                codings = codeable.get("coding", [{}])
                cond_code = codings[0].get("code", "") if codings else ""
                cond_display = codings[0].get("display", codeable.get("text", "")) if codings else codeable.get("text", "")
                
                conditions.append({
                    "condition_id": rid,
                    "patient_id": subj_ref,
                    "encounter_id": enc_ref,
                    "clinical_status": res.get("clinicalStatus", {}).get("coding", [{}])[0].get("code"),
                    "verification_status": res.get("verificationStatus", {}).get("coding", [{}])[0].get("code"),
                    "code": cond_code,
                    "display": cond_display,
                    "onset_raw": onset_raw,
                    "onset_norm": onset_norm,
                    "abatement_raw": abatement_raw,
                    "abatement_norm": abatement_norm,
                    "source_file": source_file
                })

            elif rtype == "Provenance":
                target_refs = [clean_reference_id(t.get("reference")) for t in res.get("target", [])]
                recorded_raw = res.get("recorded")
                rec_norm, rec_epoch = parse_iso_timestamp(recorded_raw)
                
                provenance_records.append({
                    "provenance_id": rid,
                    "target_references": json.dumps(target_refs),
                    "recorded_raw": recorded_raw,
                    "recorded_norm": rec_norm,
                    "recorded_epoch": rec_epoch,
                    "agent_display": res.get("agent", [{}])[0].get("who", {}).get("display", ""),
                    "source_file": source_file
                })

            else:
                unsupported_count += 1

        return {
            "patient": patient_record,
            "encounters": encounters,
            "observations": observations,
            "medication_requests": medication_requests,
            "conditions": conditions,
            "provenance": provenance_records,
            "unsupported_resources": unsupported_count,
            "errors": self.parse_errors
        }
