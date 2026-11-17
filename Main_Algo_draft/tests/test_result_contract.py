"""The engine boundary: run() returns one JSON-safe dict with everything the algorithm found.
A future engine depends on these keys, so changes here should be deliberate (bump RESULT_SCHEMA_VERSION)."""
import json
import unittest
from datetime import datetime

from _helpers import SEEDED, TYPED

from code_mapper import ALGORITHM, RESULT_SCHEMA_VERSION, run

T1 = datetime(2026, 11, 1, 10, 0, 0)
T2 = datetime(2026, 11, 2, 10, 0, 0)


class ResultContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run(SEEDED, generated_at=T1)

    def test_top_level_keys(self):
        self.assertEqual(sorted(self.r), ["algorithm", "analysis", "diff", "facts", "graphs", "import_issues",
                                          "project", "resolution", "result_schema_version", "run", "snapshot",
                                          "totals", "warnings"])
        self.assertEqual(self.r["result_schema_version"], RESULT_SCHEMA_VERSION)
        self.assertEqual(self.r["algorithm"]["language"], "python")
        self.assertEqual(self.r["algorithm"], ALGORITHM)
        self.assertEqual(self.r["project"]["generated_at"], "2026-11-01 10:00:00")
        self.assertEqual(sorted(self.r["run"]["timings_s"]),
                         ["1_scan_and_parse", "2_resolve", "3_graphs", "4_analyze"])

    def test_json_safe_and_complete(self):
        text = json.dumps(self.r, sort_keys=True)              # no sets, dataclasses or other objects
        self.assertEqual(json.loads(text)["totals"]["modules"], 17)
        facts = self.r["facts"]
        self.assertEqual(len(facts["modules"]), 17)
        self.assertEqual(len(facts["symbols"]), 43)
        orders = next(m for m in facts["modules"] if m["module"] == "shop.orders")
        place = next(f for f in orders["functions"] if f["name"] == "place_order")
        self.assertEqual(place["signature"], "def place_order(items)")
        self.assertEqual(place["loops"], [{"kind": "for", "line": 17, "depth": 1}])
        self.assertEqual(place["calls"][0], {"name": "price_of", "line": 18, "loop_depth": 1, "status": "local",
                                             "target": "shop.orders.price_of"})
        self.assertEqual(orders["imports"][0]["origin"], "stdlib")
        self.assertEqual(self.r["analysis"]["summary"]["findings"]["dead code"]["total"], 9)
        self.assertEqual(len(self.r["graphs"]["call"]["edges"]), 32)

    def test_type_facts(self):
        r = run(TYPED)
        service = next(m for m in r["facts"]["modules"] if m["module"] == "app.service")
        repo = next(c for c in service["classes"] if c["name"] == "Repo")
        self.assertEqual(repo["attr_types"]["db"], "call:Database")
        sub = next(c for c in service["classes"] if c["name"] == "SubRepo")
        self.assertEqual(sub["resolved_bases"], [{"kind": "project", "ref": "app.service.Repo"}])
        self.assertEqual(r["resolution"]["through_inferred_types"], 11)

    def test_previous_snapshot_gives_a_diff(self):
        self.assertIsNone(self.r["diff"])
        again = run(SEEDED, previous=self.r["snapshot"], generated_at=T2)
        self.assertEqual(again["diff"]["from"], "2026-11-01 10:00:00")
        self.assertFalse(any(again["diff"]["summary"].values()))


if __name__ == "__main__":
    unittest.main()
