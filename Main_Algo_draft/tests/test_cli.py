"""5.6 command-line options, run end to end: --output, --format, --no-reports, --ignore, --history,
--diff, --from-graph, plus the golden-file test for the markdown report (5.2)."""
import glob
import json
import os
import re
import time
import unittest
from datetime import datetime

from _helpers import EDGE, GOLDEN, SEEDED, captured, temp_dir

from code_mapper import TOOL_VERSION, build_report, run_pipeline
from code_mapper import main


def run(*argv):
    with captured() as (out, err):
        try:
            code = main(list(argv))
        except SystemExit as exc:                     # argparse exits on --version / errors
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class Cli(unittest.TestCase):
    def test_full_run_writes_everything_and_second_run_diffs(self):
        with temp_dir() as out:
            code, stdout, _ = run(SEEDED, "--quiet", "--output", out)
            self.assertEqual(code, 0)
            self.assertIn("Analysis: 3 import cycles", stdout)
            day = glob.glob(os.path.join(out, "20*"))[0]
            self.assertEqual(len(glob.glob(os.path.join(day, "report_*.md"))), 1)
            graphs = glob.glob(os.path.join(day, "graphs_*"))[0]
            self.assertEqual(sorted(os.listdir(graphs)), ["analysis.json", "call_graph.dot", "call_graph.mmd",
                                                          "graph.json", "import_graph.dot", "import_graph.mmd"])
            self.assertTrue(glob.glob(os.path.join(day, "dossier_*", "dossier.md")))
            self.assertEqual(len(glob.glob(os.path.join(out, "history", "*", "snapshot_*.json"))), 1)

            time.sleep(1.1)                            # second run a second later (new file names)
            code, stdout, _ = run(SEEDED, "--quiet", "--output", out)
            self.assertIn("No changes since", stdout)
            self.assertTrue(glob.glob(os.path.join(day, "graphs_*", "diff.json")))
            snaps = sorted(glob.glob(os.path.join(out, "history", "*", "snapshot_*.json")))
            self.assertEqual(len(snaps), 2)

            code, stdout, _ = run(SEEDED, "--history", "--output", out)
            self.assertIn("2 snapshots of", stdout)
            code, stdout, _ = run("--diff", snaps[0], snaps[1])
            self.assertIn("_Nothing changed", stdout)

            graph_json = glob.glob(os.path.join(day, "graphs_*", "graph.json"))[0]
            code, stdout, _ = run("--from-graph", graph_json, "--analyze", "--format", "json")
            self.assertEqual(json.loads(stdout)["summary"]["entry_points"], 8)

    def test_no_reports_writes_nothing(self):
        with temp_dir() as out:
            code, stdout, _ = run(SEEDED, "--quiet", "--no-reports", "--output", out)
            self.assertEqual(code, 0)
            self.assertEqual(os.listdir(out), [])

    def test_json_format(self):
        with temp_dir() as out:
            code, stdout, stderr = run(SEEDED, "--format", "json", "--no-reports", "--output", out)
            data = json.loads(stdout)                  # stdout holds the JSON only; the summary goes to stderr
            self.assertEqual(data["totals"]["modules"], 17)
            self.assertEqual(data["analysis"]["summary"]["findings"]["dead code"]["total"], 9)
            self.assertIn("Resolved", stderr)

    def test_ignore_and_min_confidence(self):
        code, stdout, _ = run(SEEDED, "--no-reports", "--ignore", "tests,web.py", "--min-confidence", "certain")
        self.assertIn("Modules scanned:** 15", stdout)
        self.assertNotIn("tests.test_orders", stdout)
        self.assertIn("_Showing findings at least `certain` only._", stdout)

    def test_errors_and_version(self):
        self.assertEqual(run("--version")[0], 0)
        self.assertEqual(run(os.path.join(SEEDED, "nope"), "--no-reports")[0], 1)
        self.assertEqual(run(SEEDED, "--query", "sideways", "x")[0], 2)
        self.assertEqual(run("--diff", "a", "b", "c")[0], 2)


class GoldenReport(unittest.TestCase):
    """The markdown report of the edge-case project must not change by accident.
    After an intended change, regenerate with:  set CODEMAP_UPDATE_GOLDEN=1  and run the tests again."""

    def test_report_matches_golden_file(self):
        result = run_pipeline(EDGE)
        text = build_report(EDGE, result.modules, datetime(2026, 1, 1), result.resolver, result.graphs,
                            result.analysis, warnings=result.warnings)
        text = re.sub(r"- \*\*Project:\*\* `.*`", "- **Project:** `<edge_project>`", text)
        text = text.replace(f"code_mapper {TOOL_VERSION}", "code_mapper <version>").rstrip("\n") + "\n"
        path = os.path.join(GOLDEN, "edge_project_report.md")
        if os.environ.get("CODEMAP_UPDATE_GOLDEN") or not os.path.exists(path):
            os.makedirs(GOLDEN, exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            if not os.environ.get("CODEMAP_UPDATE_GOLDEN"):
                self.skipTest("golden file created; run again to compare")
        with open(path, encoding="utf-8") as f:
            self.assertEqual(text, f.read())


if __name__ == "__main__":
    unittest.main()
