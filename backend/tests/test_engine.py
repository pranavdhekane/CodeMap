"""Engine tests. Run from the repo root:  python -m pytest backend/tests"""

import os
import tempfile
import unittest

# Use a throwaway database for tests (must be set before the engine is used).
_tmp = tempfile.TemporaryDirectory()
os.environ["CODEMAP_DB"] = os.path.join(_tmp.name, "test.db")

from backend.core import analyzers  # noqa: E402,F401
from backend.core import engine  # noqa: E402
from backend.core.engine import (  # noqa: E402
    Algorithm, AlgorithmOutput, EdgeOut, FileOut, FindingOut, SymbolOut, db, register,
)


def _out(name, files=(), edges=(), findings=()):
    return AlgorithmOutput(
        algorithm=name, version="1", files=list(files), edges=list(edges),
        findings=list(findings),
    )


@register
class BadFormatAlgo(Algorithm):
    """Returns a dict with an unknown field."""
    name = "bad_format_test"

    def run(self, data):
        return {"algorithm": self.name, "version": "1", "surprise": 1}


@register
class BadReferenceAlgo(Algorithm):
    """Edge points to a symbol that does not exist."""
    name = "bad_reference_test"

    def run(self, data):
        return {
            "algorithm": self.name, "version": "1",
            "files": [{"path": "a.py", "symbols": [
                {"stable_key": "a", "name": "a", "kind": "module"}]}],
            "edges": [{"source_key": "a", "target_key": "missing", "kind": "calls"}],
        }


@register
class CrashAlgo(Algorithm):
    name = "crash_test"

    def run(self, data):
        raise RuntimeError("boom")


@register
class FullAlgo(Algorithm):
    """Uses every table: files, symbols, parent, signature, metric, edge, finding."""
    name = "full_test"

    def run(self, data):
        mod = SymbolOut(stable_key="m", name="m", kind="module")
        func = SymbolOut(
            stable_key="m.f", name="f", kind="function", parent_key="m",
            signature=[{"role": "parameter", "name": "x", "type": "int", "position": 0},
                       {"role": "return", "name": "", "type": "str", "position": 0}],
            metrics={"complexity": 3.0},
        )
        return _out(
            self.name,
            files=[FileOut(path="m.py", symbols=[mod, func])],
            edges=[EdgeOut(source_key="m", target_key="m.f", kind="calls", confidence=0.9),
                   EdgeOut(source_key="m.f", kind="calls", target_reference="os.path")],
            findings=[FindingOut(type="dead_code", severity="medium", certainty="likely",
                                 description="unused", symbol_keys=["m.f"])],
        )


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()
        cls.pid = db.create_project("demo", None, None)
        cls.project = tempfile.TemporaryDirectory()
        with open(os.path.join(cls.project.name, "a.py"), "w") as f:
            f.write("x = 1\ny = 2\n")
        cls.inp = {"project_path": cls.project.name}

    def run_algo(self, name):
        return db.get_run(engine.run_now(name, self.pid, self.inp, "abc123"))

    def test_success_saves_results(self):
        run = self.run_algo("file_stats")
        self.assertEqual(run["status"], "done")
        self.assertEqual(run["commit_hash"], "abc123")
        self.assertEqual(run["files"][0]["path"], "a.py")
        self.assertEqual(run["symbols"][0]["metrics"], {"lines": 2.0})

    def test_all_tables_saved(self):
        run = self.run_algo("full_test")
        self.assertEqual(run["status"], "done")
        func = [s for s in run["symbols"] if s["stable_key"] == "m.f"][0]
        self.assertEqual(func["parent_key"], "m")
        self.assertEqual(len(func["signature"]), 2)
        self.assertEqual(func["metrics"], {"complexity": 3.0})
        self.assertEqual(run["edges"][0]["target"], "m.f")
        self.assertIsNone(run["edges"][1]["target"])  # unresolved edge
        self.assertEqual(run["findings"][0]["symbols"], ["m.f"])

    def test_bad_path_rejected_before_run(self):
        with self.assertRaises(engine.ValidationError):
            engine.submit("file_stats", self.pid, {"project_path": "/no/such/folder"})

    def test_missing_field_rejected(self):
        with self.assertRaises(engine.ValidationError):
            engine.submit("file_stats", self.pid, {})

    def test_unknown_project_rejected(self):
        with self.assertRaises(engine.ValidationError):
            engine.submit("file_stats", 9999, self.inp)

    def test_unknown_algorithm(self):
        with self.assertRaises(KeyError):
            engine.submit("nope", self.pid, self.inp)

    def test_wrong_output_format_fails_run(self):
        run = self.run_algo("bad_format_test")
        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["files"], [])

    def test_bad_reference_fails_run_and_saves_nothing(self):
        run = self.run_algo("bad_reference_test")
        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["files"], [])

    def test_crash_marks_run_failed(self):
        self.assertEqual(self.run_algo("crash_test")["status"], "failed")

    def test_after_run_hook_called(self):
        called = []
        engine.AFTER_RUN_HOOKS.append(called.append)
        try:
            run_id = engine.run_now("file_stats", self.pid, self.inp)
        finally:
            engine.AFTER_RUN_HOOKS.clear()
        self.assertEqual(called, [run_id])

    def test_same_input_same_output(self):
        keys = ("files", "symbols", "edges", "findings")
        a, b = self.run_algo("file_stats"), self.run_algo("file_stats")
        self.assertEqual([a[k] for k in keys][1:], [b[k] for k in keys][1:])


if __name__ == "__main__":
    unittest.main()
