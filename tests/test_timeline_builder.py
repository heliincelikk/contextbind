"""
Unit tests for TimelineBuilder, SQLite schema, and longitudinal eligibility calculation.
"""

import unittest
import os
import sqlite3
import tempfile
import json
from src.timeline.timeline_builder import TimelineBuilder

class TestTimelineBuilder(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_timeline.sqlite")
        self.builder = TimelineBuilder(self.db_path)

    def tearDown(self):
        self.builder.close()
        self.temp_dir.cleanup()

    def test_database_initialization(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        expected = {"patients", "encounters", "observations", "medication_requests", "conditions", "provenance", "timeline_events"}
        self.assertTrue(expected.issubset(tables))
        conn.close()

    def test_post_death_flagging(self):
        # Create a mock bundle with an event before death and an event after death
        mock_bundle = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "dead-pat-01",
                        "name": [{"family": "Doe", "given": ["Jane"]}],
                        "gender": "female",
                        "birthDate": "1950-01-01",
                        "deceasedDateTime": "2020-01-01T00:00:00Z"
                    }
                },
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "obs-alive",
                        "subject": {"reference": "urn:uuid:dead-pat-01"},
                        "code": {"coding": [{"code": "1234", "display": "Heart Rate"}]},
                        "effectiveDateTime": "2019-06-01T12:00:00Z",
                        "valueQuantity": {"value": 72.0}
                    }
                },
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "obs-post-mortem",
                        "subject": {"reference": "urn:uuid:dead-pat-01"},
                        "code": {"coding": [{"code": "1234", "display": "Heart Rate"}]},
                        "effectiveDateTime": "2021-06-01T12:00:00Z",
                        "valueQuantity": {"value": 0.0}
                    }
                }
            ]
        }
        
        mock_file = os.path.join(self.temp_dir.name, "mock_dead_pat.json")
        with open(mock_file, "w", encoding="utf-8") as f:
            json.dump(mock_bundle, f)

        res = self.builder.process_cohort_directory(self.temp_dir.name)
        self.assertEqual(res["anomalies"]["post_death_events"], 1)

        cursor = self.builder.conn.cursor()
        cursor.execute("SELECT resource_id, is_post_death_event FROM timeline_events ORDER BY event_time_epoch ASC")
        rows = cursor.fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], "obs-alive")
        self.assertEqual(rows[0][1], 0)
        self.assertEqual(rows[1][0], "obs-post-mortem")
        self.assertEqual(rows[1][1], 1)

if __name__ == "__main__":
    unittest.main()
