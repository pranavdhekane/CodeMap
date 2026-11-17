"""Stage 2: symbol table and call resolution (aliases, re-exports, star imports, inheritance, super(),
shadowing, circular aliases, relative imports, namespace folders) and 2.9 light type inference."""
import unittest

from _helpers import EDGE, TYPED, calls_by_scope

from code_mapper import analyze_project, resolve_project


def resolved(path):
    modules = analyze_project(path)
    resolver = resolve_project(modules)
    return resolver, calls_by_scope(modules)


class Resolution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r, cls.calls = resolved(EDGE)

    def check(self, scope, call, status, target=None, reason=None):
        c = self.calls[scope][call]
        self.assertEqual((c.status, c.target, c.reason), (status, target, reason), f"{scope}: {call}")
        return c

    def test_symbol_table(self):
        sym = self.r.symbols
        self.assertEqual(sym["core.engine.Engine"].kind, "class")
        self.assertEqual(sym["core.engine.Engine.build"].kind, "method")
        self.assertEqual(sym["core.engine.outer.inner"].kind, "function")
        self.assertNotIn("broken.oops", sym)                       # files with syntax errors add nothing

    def test_reexport_star_import_and_alias(self):
        self.check("app.run", "Engine.build", "internal", "core.engine.Engine.build")   # `as Engine` re-export
        self.check("app.run", "core.helper", "internal", "core.util.helper")             # star import in __init__
        self.check("app.run", "alias_helper", "internal", "core.util.helper")            # module-level alias
        self.check("app.run", "mod.ns_func", "internal", "nsdir.mod.ns_func")            # namespace folder

    def test_instances_and_inheritance(self):
        c = self.check("app.run", "Engine", "internal", "core.engine.Engine.__init__")
        self.assertEqual(c.instantiates, "core.engine.Engine")
        self.check("app.run", "Engine().step", "internal", "core.engine.Engine.step")
        self.check("core.engine.Base.start", "self.step", "local", "core.engine.Base.step")
        c = self.check("core.engine.Engine.step", "super().step", "local", "core.engine.Base.step")
        self.assertIn("super()", c.note)
        self.check("core.engine.Engine.__init__", "super().__init__", "external", "builtins.object.__init__")
        c = self.check("core.engine.Engine.build", "cls", "local", "core.engine.Engine.__init__")
        self.assertEqual(c.instantiates, "core.engine.Engine")

    def test_nested_function(self):
        self.check("core.engine.outer", "inner", "local", "core.engine.outer.inner")
        self.check("core.engine.outer.inner", "helper", "internal", "core.util.helper")

    def test_unresolved_reasons(self):
        self.check("app.shadow", "helper", "unresolved", reason="variable")             # parameter shadows import
        self.check("app.deep_relative", "nowhere", "unresolved", reason="relative-import")
        self.check("core.loop_a.use_x", "x", "unresolved", reason="cycle")              # circular alias
        self.check("app.run", "engine.start", "unresolved", reason="variable")          # build() has no annotation

    def test_import_origins(self):
        app = next(m for m in self.r.modules if m.module_name == "app")
        origins = {i.describe(): (i.origin, i.abs_module) for i in app.imports}
        self.assertEqual(origins["import core"], ("internal", "core"))
        self.assertEqual(origins["import nsdir"], ("internal", "nsdir"))
        self.assertEqual(origins["from nsdir import mod"], ("internal", "nsdir.mod"))
        self.assertEqual(origins["from .. import nowhere"], ("unresolved", None))

    def test_stats(self):
        st = self.r.stats
        self.assertEqual(st.total, sum(st.by_status.values()))
        self.assertGreater(st.percent(), 50)


class TypeInference(unittest.TestCase):
    """2.9: x = Foo(), annotations, typed self attributes, return annotations, with-blocks."""

    @classmethod
    def setUpClass(cls):
        cls.r, cls.calls = resolved(TYPED)

    def inferred(self, scope, call, target):
        c = self.calls[f"app.service.{scope}"][call]
        self.assertEqual((c.status, c.target, c.inferred), ("internal", target, True), f"{scope}: {call}")

    def unresolved(self, scope, call, reason="variable"):
        c = self.calls[f"app.service.{scope}"][call]
        self.assertEqual((c.status, c.reason, c.inferred), ("unresolved", reason, False), f"{scope}: {call}")

    def test_inferred(self):
        save = "app.db.Database.save"
        self.inferred("Repo.put", "self.db.save", save)                # self.db = Database()
        self.inferred("Repo.put", "self.backup.save", save)            # self.backup = connect() -> Database
        self.inferred("Repo.put", "self.store.save", save)             # class-level `store: Database`
        self.inferred("SubRepo.put_twice", "self.db.save", save)       # attribute type from the base class
        self.inferred("use_param", "db.save", save)                    # db: Database
        self.inferred("use_optional", "db.save", save)                 # Optional[Database]
        self.inferred("use_local", "d.save", save)                     # d = Database()
        self.inferred("use_local", "c.execute", "app.db.Cursor.execute")   # c = d.cursor() -> "Cursor"
        self.inferred("use_with", "conn.save", save)                   # with Database() as conn (__enter__)
        self.inferred("use_global", "GLOBAL_DB.save", save)            # module-level GLOBAL_DB = Database()

    def test_not_inferred(self):
        self.unresolved("ambiguous", "x.save")                         # x bound to two different things
        self.unresolved("rebound", "db.save")                          # parameter re-bound in the body
        self.unresolved("container", "items.save")                     # list[Database] is not a Database

    def test_plain_calls_are_not_marked_inferred(self):
        c = self.calls["app.service.Repo.__init__"]["Database"]
        self.assertFalse(c.inferred)
        self.assertEqual(self.r.stats.inferred, 11)


if __name__ == "__main__":
    unittest.main()
