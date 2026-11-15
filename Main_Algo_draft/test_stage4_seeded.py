"""Stage 4 "done when": a seeded project with known cycles, recursion, dead functions, loops and
import problems must be detected exactly.  Run:  python -m unittest discover tests   (from the tool folder)
Uses only the public functions of code_mapper; writes no files."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import code_mapper as cm                                              # noqa: E402

FIXTURE = os.path.join(HERE, "fixtures", "seeded_project")


def run_analysis():
    modules = cm.analyze_project(FIXTURE)
    resolver = cm.resolve_project(modules)
    graphs = cm.build_graphs(resolver)
    return cm.analyze_graphs(graphs, cm.find_import_issues(resolver)), graphs


class SeededProject(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a, cls.graphs = run_analysis()

    def test_import_cycles(self):
        got = {(c["kind"], c["confidence"], tuple(c["members"])) for c in self.a["cycles"]["import"]}
        self.assertEqual(got, {
            ("import-time", "certain", ("shop.billing", "shop.orders")),
            ("deferred", "likely", ("shop.cache", "shop.store")),
            ("typing-only", "uncertain", ("shop.models", "shop.services")),
        })

    def test_call_cycles(self):
        got = {tuple(c["members"]) for c in self.a["cycles"]["call"]}
        self.assertEqual(got, {
            ("shop.billing.partial_refund", "shop.billing.refund"),
            ("shop.cache.get", "shop.store.load"),
            ("shop.mathutil.is_even", "shop.mathutil.is_odd"),
        })

    def test_recursion(self):
        direct = {d["id"]: d["confidence"] for d in self.a["recursion"]["direct"]}
        self.assertEqual(direct, {"shop.mathutil.factorial": "certain", "shop.tree.Tree.walk": "likely"})
        indirect = {r["id"]: r["cycle_length"] for r in self.a["recursion"]["indirect"]}
        self.assertEqual(set(indirect.values()), {2})
        self.assertEqual(len(indirect), 6)

    def test_loops(self):
        self.assertEqual([n["id"] for n in self.a["loops"]["nested"]], ["shop.mathutil.grid"])
        got = {(r["caller"], r["callee"], tuple(r["why"]), r["confidence"]) for r in self.a["loops"]["calls_in_loops"]}
        self.assertEqual(got, {
            ("shop.mathutil.sum_factorials", "shop.mathutil.factorial", ("recursive",), "certain"),
            ("shop.orders.place_order", "shop.orders.price_of", ("loops",), "certain"),
            ("shop.orders.total_cost", "shop.orders.quote", ("indirect",), "likely"),
        })

    def test_entry_points(self):
        got = {(e["type"], e["id"]) for e in self.a["entry_points"]}
        self.assertEqual(got, {
            ("exported", "shop.orders.place_order"),
            ("handler", "shop.web.index"),
            ("main-block", "shop.cli.<main>"),
            ("main-function", "shop.cli.main"),
            ("main-module", "shop.__main__.<module>"),
            ("test", "tests.test_orders.TestOrders"),
            ("test", "tests.test_orders.TestOrders.test_total"),
            ("test", "tests.test_orders.test_place_order"),
        })

    def test_dead_code(self):
        got = {f["id"]: f["confidence"] for f in self.a["dead_code"]}
        self.assertEqual(got, {
            "shop.orders._unused_helper": "certain",
            "shop.orders._dead_root": "certain",
            "shop.orders._only_from_dead": "likely",       # only called by dead code: one level lower
            "shop.orders.public_dead": "likely",
            "shop.billing.refund": "likely",               # a call cycle nobody else calls
            "shop.billing.partial_refund": "likely",
            "shop.orphan.Orphan": "likely",
            "shop.hooks.on_done": "uncertain",             # only passed around as a value
            "shop.plugins.Base.run": "uncertain",          # overridden in a subclass
        })
        orphan = next(f for f in self.a["dead_code"] if f["id"] == "shop.orphan.Orphan")
        self.assertEqual(orphan["contains"], ["Orphan.run"])

    def test_things_that_must_not_be_dead(self):
        dead = {f["id"] for f in self.a["dead_code"]}
        for alive in ("shop.cli.main", "shop.web.index", "shop.models.Model", "shop.services.Service",
                      "shop.tree.Tree.walk", "shop.mathutil.parity", "shop.plugins.Child.run",
                      "shop.plugins.Base", "shop.orders.quote", "shop.orders.total_cost",
                      "shop.plugins.Turbo", "shop.plugins.Engine"):      # Turbo() runs the inherited __init__
            self.assertNotIn(alive, dead)

    def test_imports(self):
        unused = {(i["module"], i["name"], i["confidence"]) for i in self.a["imports"]["unused"]}
        self.assertEqual(unused, {
            ("shop.orders", "os", "certain"),
            ("shop.web", "orders", "certain"),
            ("shop", "charge", "uncertain"),               # package __init__: maybe a re-export
            ("shop.optional", "ujson", "uncertain"),       # inside try:
        })
        missing = {(i["module"], i["statement"]) for i in self.a["imports"]["missing"]}
        self.assertEqual(missing, {("shop.web", "from .nonexistent import thing")})

    def test_metrics(self):
        m = self.a["metrics"]["call_graph"]
        self.assertEqual(m["max_chain_depth"], 4)
        self.assertEqual(m["top_fan_out"][0]["id"], "shop.web.index")

    def test_deterministic(self):
        again, _ = run_analysis()
        self.assertEqual(json.dumps(self.a, sort_keys=True), json.dumps(again, sort_keys=True))

    def test_confidence_filter(self):
        only = cm.filter_analysis(self.a, "certain")
        for _, items in cm._confidence_lists(only):
            self.assertTrue(all(i["confidence"] == "certain" for i in items))
        self.assertEqual(sorted(f["id"] for f in only["dead_code"]),
                         ["shop.orders._dead_root", "shop.orders._unused_helper"])

if __name__ == "__main__":
    unittest.main()
