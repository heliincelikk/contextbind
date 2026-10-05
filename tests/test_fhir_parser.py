"""
Unit tests for FHIRBundleParser and canonical timestamp parsing.
"""

import unittest
import json
from src.ingestion.fhir_parser import FHIRBundleParser, parse_iso_timestamp, clean_reference_id

class TestFHIRBundleParser(unittest.TestCase):
    def setUp(self):
        self.parser = FHIRBundleParser()

    def test_parse_iso_timestamp(self):
        # Timezone offset handling
        iso_str, epoch = parse_iso_timestamp("2026-10-04T15:30:00+03:00")
        self.assertIsNotNone(iso_str)
        self.assertIsNotNone(epoch)
        self.assertTrue(iso_str.startswith("2026-10-04T12:30:00"))

        # UTC format (Z)
        iso_str_z, epoch_z = parse_iso_timestamp("2026-10-04T12:30:00Z")
        self.assertEqual(iso_str, iso_str_z)
        self.assertEqual(epoch, epoch_z)

        # Date-only fallback
        iso_str_d, epoch_d = parse_iso_timestamp("2026-10-04")
        self.assertIsNotNone(iso_str_d)
        self.assertEqual(iso_str_d, "2026-10-04T00:00:00+00:00")

        # Invalid string
        iso_bad, epoch_bad = parse_iso_timestamp("invalid-date")
        self.assertIsNone(iso_bad)
        self.assertIsNone(epoch_bad)

    def test_clean_reference_id(self):
        self.assertEqual(clean_reference_id("urn:uuid:6aab5c5e-3a2f-fea1-ca8d-5586ecaee400"), "6aab5c5e-3a2f-fea1-ca8d-5586ecaee400")
        self.assertEqual(clean_reference_id("Patient/12345"), "12345")
        self.assertEqual(clean_reference_id("12345"), "12345")
        self.assertIsNone(clean_reference_id(None))

    def test_parse_bundle_dict(self):
        mock_bundle = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "pat-001",
                        "name": [{"family": "Smith", "given": ["John"]}],
                        "gender": "male",
                        "birthDate": "1980-01-01",
                        "deceasedDateTime": "2025-05-01T10:00:00Z"
                    }
                },
                {
                    "resource": {
                        "resourceType": "Encounter",
                        "id": "enc-001",
                        "status": "finished",
                        "subject": {"reference": "urn:uuid:pat-001"},
                        "period": {
                            "start": "2024-01-10T09:00:00Z",
                            "end": "2024-01-10T10:00:00Z"
                        },
                        "class": {"code": "AMB"}
                    }
                },
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "obs-001",
                        "status": "final",
                        "subject": {"reference": "urn:uuid:pat-001"},
                        "encounter": {"reference": "urn:uuid:enc-001"},
                        "code": {
                            "coding": [{"code": "883-9", "system": "http://loinc.org", "display": "ABO group"}]
                        },
                        "effectiveDateTime": "2024-01-10T09:15:00Z",
                        "valueQuantity": {"value": 120.0, "unit": "mmHg"}
                    }
                },
                {
                    "resource": {
                        "resourceType": "MedicationRequest",
                        "id": "med-001",
                        "status": "completed",
                        "intent": "order",
                        "subject": {"reference": "urn:uuid:pat-001"},
                        "encounter": {"reference": "urn:uuid:enc-001"},
                        "authoredOn": "2024-01-10T09:30:00Z",
                        "medicationCodeableConcept": {
                            "coding": [{"code": "314076", "display": "Lisinopril 10mg"}]
                        }
                    }
                }
            ]
        }

        parsed = self.parser.parse_bundle_dict(mock_bundle, source_file="mock.json")
        self.assertIsNotNone(parsed["patient"])
        self.assertEqual(parsed["patient"]["patient_id"], "pat-001")
        self.assertEqual(parsed["patient"]["deceased_date_raw"], "2025-05-01T10:00:00Z")
        self.assertEqual(len(parsed["encounters"]), 1)
        self.assertEqual(len(parsed["observations"]), 1)
        self.assertEqual(len(parsed["medication_requests"]), 1)
        
        # Verify Observation fields
        obs = parsed["observations"][0]
        self.assertEqual(obs["code"], "883-9")
        self.assertEqual(obs["value_numeric"], 120.0)
        self.assertEqual(obs["unit"], "mmHg")
        self.assertEqual(obs["encounter_id"], "enc-001")

        # Verify MedicationRequest fields
        med = parsed["medication_requests"][0]
        self.assertEqual(med["code"], "314076")
        self.assertEqual(med["status"], "completed")

if __name__ == "__main__":
    unittest.main()
