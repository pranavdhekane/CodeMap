"""Stage 1 (scanner + parser) and the 5.3 edge cases: ignore patterns, build folders, .pyi stubs,
namespace folders, syntax errors, non-UTF-8 files, huge files, symlinks, nested defs, loops."""
import os
import unittest

from _helpers import EDGE, SEEDED, TYPED, temp_dir, write

from code_mapper import analyze_module, analyze_project, find_python_files, module_name_from_path


class Scanner(unittest.TestCase):
    def test_files_found(self):
        files = [f.replace(os.sep, "/") for f in find_python_files(EDGE)]
        self.assertEqual(files, [
            "app.py", "broken.py", "cookie.py", "legacy.py", "core/__init__.py", "core/engine.py",
            "core/loop_a.py", "core/loop_b.py", "core/util.py", "nsdir/mod.py", "stubs/fast.pyi", "stubs/slow.py"])
        # files of a folder first, then its subfolders (sorted); build/ is in IGNORE_DIRS;
        # slow.pyi is skipped because slow.py exists

    def test_ignore_patterns(self):
        def found(*patterns):
            return {f.replace(os.sep, "/") for f in find_python_files(EDGE, ignore=patterns)}
        self.assertFalse({f for f in found("core") if f.startswith("core/")})
        self.assertNotIn("stubs/fast.pyi", found("*.pyi"))
        self.assertNotIn("stubs/slow.py", found("stubs/slow.py"))
        self.assertFalse({f for f in found("stubs/*") if f.startswith("stubs/")})
        self.assertEqual(found("nothing-matches"), found())

    def test_skip_dirs(self):
        files = find_python_files(EDGE, skip_dirs=[os.path.join(EDGE, "core")])
        self.assertFalse([f for f in files if f.startswith("core")])

    def test_module_names(self):
        self.assertEqual(module_name_from_path(os.path.join("pkg", "sub", "mod.py"), EDGE), ("pkg.sub.mod", False))
        self.assertEqual(module_name_from_path(os.path.join("pkg", "__init__.py"), EDGE), ("pkg", True))
        self.assertEqual(module_name_from_path(os.path.join("stubs", "fast.pyi"), EDGE), ("stubs.fast", False))
        # a scanned folder that is itself a package prefixes its own name
        core = os.path.join(EDGE, "core")
        self.assertEqual(module_name_from_path("engine.py", core), ("core.engine", False))

    def test_symlink_outside_is_skipped(self):
        with temp_dir() as outside, temp_dir() as project:
            write(os.path.join(outside, "secret.py"), "x = 1\n")
            write(os.path.join(project, "real.py"), "y = 2\n")
            try:
                os.symlink(os.path.join(outside, "secret.py"), os.path.join(project, "link.py"))
                os.symlink(project, os.path.join(project, "loop"), target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("cannot create symlinks here (Windows without developer mode)")
            warnings = []
            self.assertEqual(find_python_files(project, warnings=warnings), ["real.py"])
            self.assertTrue(any("link.py" in w for w in warnings))


class Parser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.warnings = []
        cls.mods = {m.module_name: m for m in analyze_project(EDGE, warnings=cls.warnings)}

    def test_syntax_error_is_reported_not_skipped(self):
        self.assertIn("broken", self.mods)
        self.assertTrue(self.mods["broken"].error.startswith("SyntaxError"))

    def test_encodings(self):
        legacy, cookie = self.mods["legacy"], self.mods["cookie"]
        self.assertIsNone(legacy.error)                       # bad UTF-8: read again as latin-1
        self.assertTrue(legacy.warnings and "latin-1" in legacy.warnings[0])
        self.assertTrue(any(w.startswith("legacy.py:") for w in self.warnings))
        self.assertEqual([f.name for f in legacy.functions], ["legacy"])
        self.assertIsNone(cookie.error)                       # PEP 263 coding line is honoured
        self.assertEqual(cookie.warnings, [])

    def test_stub_only_module(self):
        fast = self.mods["stubs.fast"]
        self.assertTrue(fast.is_stub)
        self.assertEqual([(f.name, f.returns) for f in fast.functions], [("speed", "int")])
        self.assertFalse(self.mods["stubs.slow"].is_stub)

    def test_nested_and_methods(self):
        engine = self.mods["core.engine"]
        names = {f.qualified_name: f for f in engine.functions}
        self.assertIn("outer.inner", names)
        self.assertIsNone(names["outer.inner"].enclosing_class)
        self.assertEqual(names["Engine.build"].enclosing_class, "Engine")
        self.assertEqual(names["Engine.build"].decorators, ["classmethod"])
        self.assertEqual([c.qualified_name for c in engine.classes], ["Base", "Engine"])
        self.assertEqual(engine.classes[1].bases, ["Base"])
        self.assertEqual(engine.classes[1].methods, ["__init__", "step", "build"])

    def test_imports_and_exports(self):
        core = self.mods["core"]
        self.assertTrue(core.is_package)
        self.assertEqual([(i.kind, i.module, i.name, i.alias, i.level) for i in core.imports],
                         [("from", "engine", "Engine", "Engine", 1), ("from", "util", "*", None, 1)])
        self.assertEqual(core.exports, ["Engine", "helper"])
        app = self.mods["app"]
        rel = [i for i in app.imports if i.level == 2]
        self.assertEqual(len(rel), 1)
        self.assertEqual(rel[0].scope, "deep_relative")

    def test_aliases_and_main_block(self):
        self.assertEqual([(a.name, a.target) for a in self.mods["core.util"].aliases], [("alias_helper", "helper")])
        app = self.mods["app"]
        self.assertIsNotNone(app.main_block)
        self.assertEqual([c.name for c in app.main_block.calls], ["run"])

    def test_sizes_and_fingerprints(self):
        engine = self.mods["core.engine"]
        self.assertEqual(engine.line_count, 28)
        fns = {f.qualified_name: f for f in engine.functions}
        self.assertEqual((fns["Base.start"].line, fns["Base.start"].end_line), (6, 7))
        self.assertEqual(len({f.fingerprint for f in engine.functions}), len(engine.functions))
        again = analyze_module(EDGE, os.path.join("core", "engine.py"))
        self.assertEqual([f.fingerprint for f in again.functions], [f.fingerprint for f in engine.functions])

    def test_huge_file_limit(self):
        m = analyze_module(EDGE, "app.py", max_bytes=10)
        self.assertTrue(m.error.startswith("FileTooLarge"))
        self.assertEqual(m.functions, [])

    def test_loops(self):
        with temp_dir() as d:
            write(os.path.join(d, "loops.py"),
                  "def f(xs):\n"
                  "    for x in xs:\n"
                  "        while x:\n"
                  "            g(x)\n"
                  "    else:\n"
                  "        h()\n"
                  "    return [i for i in xs]\n")
            fn = analyze_module(d, "loops.py").functions[0]
            self.assertEqual([(lp.kind, lp.depth) for lp in fn.loops], [("for", 1), ("while", 2)])
            self.assertEqual({c.name: c.loop_depth for c in fn.calls}, {"g": 2, "h": 0})

    def test_type_hints(self):
        service = {m.module_name: m for m in analyze_project(TYPED)}["app.service"]
        fns = {f.qualified_name: f for f in service.functions}
        self.assertEqual(fns["use_local"].var_types, {"c": "call:d.cursor", "d": "call:Database"})
        self.assertEqual(fns["use_with"].var_types, {"conn": "enter:Database"})
        self.assertEqual(fns["ambiguous"].var_types, {})                     # bound to two different things
        self.assertEqual(fns["use_param"].param_types, {"db": "ann:Database"})
        repo = next(c for c in service.classes if c.name == "Repo")
        self.assertEqual(repo.attr_types, {"backup": "call:connect", "db": "call:Database", "store": "ann:Database"})
        self.assertEqual(service.module_scope.var_types, {"GLOBAL_DB": "call:Database"})

    def test_seeded_project_has_no_errors(self):
        self.assertFalse([m.path for m in analyze_project(SEEDED) if m.error])


if __name__ == "__main__":
    unittest.main()
