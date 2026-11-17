"""Stage 3: call / import graphs, reverse edges, export + reload, queries, determinism."""
import json
import os
import unittest

from _helpers import EDGE, SEEDED, TYPED, captured, temp_dir

from code_mapper import (analyze_project, build_graphs, find_import_issues, load_graphs, resolve_project,
                            write_graphs)
from code_mapper import Graph, run_query


def graphs_of(path):
    resolver = resolve_project(analyze_project(path))
    return build_graphs(resolver), resolver


class CallGraph(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g, cls.r = graphs_of(SEEDED)
        cls.cg = cls.g["call"]

    def test_edges_and_reverse_edges(self):
        self.assertEqual(self.cg.successors("shop.orders.place_order"),
                         ["shop.billing.charge", "shop.orders.price_of"])
        self.assertEqual(self.cg.predecessors("shop.orders.place_order"),
                         ["shop.cli.main", "tests.test_orders.test_place_order"])
        edge = self.cg.edge("shop.orders.place_order", "shop.orders.price_of")
        self.assertTrue(edge["in_loop"])
        self.assertEqual(edge["sites"][0]["loop_depth"], 1)

    def test_scope_nodes_and_counters(self):
        main = self.cg.nodes["shop.cli.<main>"]
        self.assertEqual(main["kind"], "main-scope")
        web = self.cg.nodes["shop.web.index"]
        self.assertEqual(web["unresolved_calls"], 1)                  # thing() from a missing module
        self.assertEqual(web["decorators"], ["app.route('/')"])
        self.assertEqual(self.cg.nodes["shop.plugins.Turbo"]["instantiated_from"], ["shop.web.index"])

    def test_reach(self):
        self.assertEqual(self.cg.reach("shop.cli.main", "out", 0),
                         [(1, "shop.orders.place_order"), (2, "shop.billing.charge"), (2, "shop.orders.price_of"),
                          (3, "shop.billing.round_money")])
        self.assertEqual(self.cg.find("Tree.walk"), ["shop.tree.Tree.walk"])

    def test_inferred_sites_are_marked(self):
        g, _ = graphs_of(TYPED)
        edge = g["call"].edge("app.service.use_param", "app.db.Database.save")
        self.assertTrue(edge["sites"][0]["inferred"])


class ImportGraph(unittest.TestCase):
    def test_edges(self):
        g, _ = graphs_of(SEEDED)
        ig = g["import"]
        self.assertTrue(ig.edge("shop.orders", "shop.billing")["top_level"])
        self.assertFalse(ig.edge("shop.cache", "shop.store")["top_level"])         # function-level import
        self.assertTrue(ig.edge("shop.models", "shop.services")["sites"][0]["type_checking"])
        self.assertEqual(ig.predecessors("shop.orders"), ["shop.billing", "shop.cli", "shop.web", "tests.test_orders"])

    def test_namespace_package_node(self):
        g, _ = graphs_of(EDGE)
        ig = g["import"]
        self.assertEqual(ig.nodes["nsdir"]["kind"], "namespace")
        self.assertIsNotNone(ig.edge("app", "nsdir"))
        self.assertIsNotNone(ig.edge("app", "nsdir.mod"))
        self.assertTrue(g["call"].nodes["stubs.fast.speed"]["stub"])


class ExportAndQueries(unittest.TestCase):
    def test_roundtrip_and_determinism(self):
        g, r = graphs_of(SEEDED)
        issues = find_import_issues(r)
        with temp_dir() as a, temp_dir() as b:
            write_graphs(g, "seeded", a, issues)
            g2, r2 = graphs_of(SEEDED)
            write_graphs(g2, "seeded", b, find_import_issues(r2))
            for name in ("graph.json", "call_graph.mmd", "call_graph.dot", "import_graph.mmd", "import_graph.dot"):
                with open(os.path.join(a, name), "rb") as fa, open(os.path.join(b, name), "rb") as fb:
                    self.assertEqual(fa.read(), fb.read(), name)
            loaded = load_graphs(os.path.join(a, "graph.json"))
            self.assertEqual(loaded["call"].to_dict(), g["call"].to_dict())
            self.assertEqual(loaded["import"].to_dict(), g["import"].to_dict())
            with open(os.path.join(a, "graph.json"), encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["schema_version"], 1)
            self.assertEqual(data["import_issues"], issues)
            self.assertNotIn(SEEDED, json.dumps(data))                 # no absolute paths in exports

    def test_mermaid_and_dot(self):
        g = Graph("call")
        g.add_node("a")
        g.add_node("b")
        g.add_node("lonely")
        g.add_edge("a", "b", {"line": 3, "name": "b", "loop_depth": 1})
        g.add_edge("a", "b", {"line": 5, "name": "b", "loop_depth": 0})
        g.finalize()
        self.assertIn("n0 ==>|x2| n1", g.to_mermaid())
        self.assertNotIn("lonely", g.to_mermaid())
        self.assertIn('"a" -> "b" [label="x2", style=bold];', g.to_dot())

    def test_query_output(self):
        g, _ = graphs_of(SEEDED)
        with captured() as (out, err):
            code = run_query(g, "callers", "place_order", 1)
        self.assertEqual(code, 0)
        self.assertIn("[1] shop.cli.main  (line 6)", out.getvalue())
        with captured() as (out, err):
            self.assertEqual(run_query(g, "callees", "run", 1), 1)       # ambiguous name
        self.assertIn("matches", err.getvalue())


if __name__ == "__main__":
    unittest.main()
