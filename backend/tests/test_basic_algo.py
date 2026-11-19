"""Tests for the basic_algo_1 static analysis algorithm."""

import os
import tempfile
import unittest
from unittest import mock

_tmp = tempfile.TemporaryDirectory()
os.environ["CODEMAP_DB"] = os.path.join(_tmp.name, "basic_algo_test.db")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app import analysis  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.core import analyzers  # noqa: E402, F401
from backend.core.engine import db, list_algorithms, run_now  # noqa: E402


class BasicAlgo1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()
        cls.pid = db.create_project("basic_algo_demo", "Test Project", None)

        cls.sample_dir = tempfile.TemporaryDirectory()
        # Create a mini multi-module python project
        mod_a = os.path.join(cls.sample_dir.name, "pkg_a")
        os.makedirs(mod_a, exist_ok=True)

        with open(os.path.join(cls.sample_dir.name, "pkg_a", "__init__.py"), "w") as f:
            f.write("# pkg_a\n")

        with open(os.path.join(cls.sample_dir.name, "pkg_a", "models.py"), "w") as f:
            f.write(
                "class Base:\n"
                "    pass\n\n"
                "class User(Base):\n"
                "    def __init__(self, name: str, age: int = 0) -> None:\n"
                "        self.name = name\n"
                "        self.age = age\n"
            )

        with open(os.path.join(cls.sample_dir.name, "pkg_a", "service.py"), "w") as f:
            f.write(
                "import os\n"
                "from .models import User\n\n"
                "def create_user(name: str) -> User:\n"
                "    u = User(name=name)\n"
                "    return u\n\n"
                "def helper() -> None:\n"
                "    create_user('alice')\n"
            )

        cls.local_mode = mock.patch.object(analysis, "is_local_mode", return_value=True)
        cls.local_mode.start()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.local_mode.stop()
        cls.sample_dir.cleanup()
        _tmp.cleanup()

    def test_registered(self):
        algos = list_algorithms()
        self.assertIn("basic_algo_1", algos)

    def test_run_now_engine(self):
        run_id = run_now(
            "basic_algo_1",
            self.pid,
            {"project_path": self.sample_dir.name},
            commit_hash="c0ffee",
        )
        run = db.get_run(run_id)
        self.assertIsNotNone(run)
        self.assertEqual(run["status"], "done")
        self.assertEqual(run["commit_hash"], "c0ffee")

        # Verify files
        file_paths = [f["path"] for f in run["files"]]
        self.assertTrue(any("models.py" in p for p in file_paths))
        self.assertTrue(any("service.py" in p for p in file_paths))

        # Verify symbols
        symbol_names = [s["name"] for s in run["symbols"]]
        self.assertIn("User", symbol_names)
        self.assertIn("Base", symbol_names)
        self.assertIn("create_user", symbol_names)
        self.assertIn("__init__", symbol_names)

        # Verify edges
        kinds = {e["kind"] for e in run["edges"]}
        self.assertIn("inherits", kinds)
        self.assertIn("imports", kinds)
        self.assertIn("calls", kinds)

    def test_api_analyze_and_get_run(self):
        # Trigger through API
        response = self.client.post(
            "/api/analyze",
            json={
                "algorithm": "basic_algo_1",
                "project_id": self.pid,
                "project_path": self.sample_dir.name,
            },
        )
        self.assertEqual(response.status_code, 202)
        run_id = response.json()["run_id"]

        run_data = self.client.get(f"/api/runs/{run_id}").json()
        self.assertEqual(run_data["status"], "done")
        self.assertGreater(len(run_data["symbols"]), 0)
        self.assertGreater(len(run_data["files"]), 0)
