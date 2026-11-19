"""API tests: the app starts the way the README launches it and runs algorithms.

Run from the repo root:  python -m pytest backend/tests
"""

import os
import tempfile
import unittest
from unittest import mock

_tmp = tempfile.TemporaryDirectory()
os.environ["CODEMAP_DB"] = os.path.join(_tmp.name, "api_test.db")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app import analysis  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.core.engine import db  # noqa: E402


class AnalysisApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project_dir = tempfile.TemporaryDirectory()
        with open(os.path.join(cls.project_dir.name, "a.py"), "w") as f:
            f.write("print('hi')\n")
        cls.local_mode = mock.patch.object(analysis, "is_local_mode", return_value=True)
        cls.local_mode.start()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.local_mode.stop()
        cls.project_dir.cleanup()

    def setUp(self):
        db.init_db()
        self.project_id = self.client.post("/api/projects", json={"name": "demo"}).json()[
            "project_id"
        ]

    def test_lists_registered_algorithms(self):
        body = self.client.get("/api/algorithms").json()
        self.assertIn("file_stats", body["algorithms"])

    def test_analyze_runs_in_background_and_saves_results(self):
        response = self.client.post(
            "/api/analyze",
            json={
                "algorithm": "file_stats",
                "project_id": self.project_id,
                "project_path": self.project_dir.name,
            },
        )
        self.assertEqual(response.status_code, 202)
        run = self.client.get(f"/api/runs/{response.json()['run_id']}").json()
        self.assertEqual(run["status"], "done")
        self.assertEqual([f["path"] for f in run["files"]], ["a.py"])

    def test_unknown_algorithm_is_404(self):
        response = self.client.post(
            "/api/analyze",
            json={"algorithm": "nope", "project_id": self.project_id, "project_path": "."},
        )
        self.assertEqual(response.status_code, 404)

    def test_bad_project_path_is_422_and_saves_nothing(self):
        response = self.client.post(
            "/api/analyze",
            json={
                "algorithm": "file_stats",
                "project_id": self.project_id,
                "project_path": "/definitely/not/a/folder",
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get("/api/runs/999999").status_code, 404)


if __name__ == "__main__":
    unittest.main()
