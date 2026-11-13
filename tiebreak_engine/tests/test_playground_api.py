"""
API endpoint tests for the Playground server.
"""

import unittest
from fastapi.testclient import TestClient
from tiebreak_engine.playground.run_playground import app


class TestPlaygroundAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_check(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("status"), "healthy")

    def test_sample_data(self):
        res = self.client.get("/api/sample-data")
        self.assertEqual(res.status_code, 200)
        presets = res.json().get("presets", {})
        self.assertIn("saigon_outlier_conflict", presets)
        self.assertIn("hanoi_river_crossing", presets)

    def test_tiebreak_api(self):
        sample_res = self.client.get("/api/sample-data")
        preset = sample_res.json()["presets"]["saigon_outlier_conflict"]

        payload = {
            "participants": preset["participants"],
            "slots": preset["slots"],
            "penalty_exponent": 1.0,
            "fairness_factor": 0.0,
            "enable_osrm": False,
        }

        res = self.client.post("/api/tiebreak", json=payload)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(len(body["selected_combination"]), 1)
        self.assertGreater(body["total_penalty_score"], 0)

    def test_serve_static_index(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Ordered Median Tie-Break Engine", res.text)


if __name__ == "__main__":
    unittest.main()
