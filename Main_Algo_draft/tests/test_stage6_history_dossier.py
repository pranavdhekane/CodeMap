"""Stage 6: run snapshots + diffs (6.1), onboarding dossier (6.2) and module pages (6.3)."""
import os
import shutil
import unittest
from datetime import datetime

from _helpers import SEEDED, temp_dir, write

from code_mapper import run_pipeline
from code_mapper import build_dossier, build_module_page, write_dossier
from code_mapper import (build_snapshot, diff_lines, diff_snapshots, list_snapshots, load_snapshot,
                                    project_key, save_snapshot)

T1 = datetime(2026, 11, 1, 10, 0, 0)
T2 = datetime(2026, 11, 2, 10, 0, 0)


def edit(path, old, new):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    assert old in text, old
    write(path, text.replace(old, new))


class History(unittest.TestCase):
    def test_diff_after_edits(self):
        with temp_dir() as tmp:
            project = os.path.join(tmp, "shop_copy")
            shutil.copytree(SEEDED, project)
            before = build_snapshot(run_pipeline(project), T1)
            self.assertEqual(diff_snapshots(before, before)["summary"],
                             {k: 0 for k in diff_snapshots(before, before)["summary"]})

            orders = os.path.join(project, "shop", "orders.py")
            edit(orders, "import os\n", "")                                       # fixes an unused import
            edit(orders, "return price_of(item) * 2", "return price_of(item) * 3")   # body change
            edit(orders, "def price_of(item):", "def price_of(item, discount=0):")    # signature change
            with open(os.path.join(project, "shop", "mathutil.py"), "a", encoding="utf-8") as f:
                f.write("\n\ndef brand_new():\n    return 0\n")                   # added (and dead)
            os.remove(os.path.join(project, "shop", "orphan.py"))                 # removed module
            after = build_snapshot(run_pipeline(project), T2)

            d = diff_snapshots(before, after)
            self.assertEqual((d["from"], d["to"]), ("2026-11-01 10:00:00", "2026-11-02 10:00:00"))
            self.assertEqual(d["modules"], {"added": [], "removed": ["shop.orphan"]})
            self.assertEqual(d["symbols"]["added"], ["shop.mathutil.brand_new"])
            self.assertEqual(d["symbols"]["removed"], ["shop.orphan.Orphan", "shop.orphan.Orphan.run"])
            changed = {c["id"]: c["what"] for c in d["symbols"]["changed"]}
            self.assertEqual(changed, {"shop.orders.price_of": "signature", "shop.orders.quote": "body"})
            # only the functions below the edit moved; moving is not a change
            self.assertNotIn("shop.orders.total_cost", changed)
            self.assertEqual(d["findings"]["unused_imports"], {"new": [], "gone": ["shop.orders: import os"]})
            self.assertEqual(d["findings"]["dead_code"],
                             {"new": ["shop.mathutil.brand_new [likely]"], "gone": ["shop.orphan.Orphan [likely]"]})
            text = "\n".join(diff_lines(d))
            self.assertIn("`shop.orders.price_of`: signature `def price_of(item)` -> "
                          "`def price_of(item, discount=0)`", text)

    def test_storage(self):
        result = run_pipeline(SEEDED)
        with temp_dir() as out:
            self.assertEqual(list_snapshots(out, SEEDED), [])
            p1 = save_snapshot(build_snapshot(result, T1), out, SEEDED, T1)
            p2 = save_snapshot(build_snapshot(result, T2), out, SEEDED, T2)
            self.assertEqual(list_snapshots(out, SEEDED), [p1, p2])
            self.assertIn(project_key(SEEDED), p1)
            self.assertTrue(project_key(SEEDED).startswith("seeded_project-"))
            self.assertEqual(load_snapshot(p1)["stats"]["functions"], 34)
            with self.assertRaises(ValueError):
                write(os.path.join(out, "bad.json"), "{}")
                load_snapshot(os.path.join(out, "bad.json"))


class Dossier(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_pipeline(SEEDED)
        cls.text = build_dossier(cls.result, T1)

    def test_sections(self):
        for heading in ("## 1. At a glance", "## 2. Where execution starts", "## 3. Main flows",
                        "## 4. Architecture", "## 5. Key modules", "## 6. Hot spots", "## 7. Known problems",
                        "## 8. Suggested reading order", "## 9. Changes since the previous run",
                        "## 10. All modules"):
            self.assertIn(heading, self.text)

    def test_content(self):
        t = self.text
        self.assertIn("| Modules | 17 (1 package) |", t)
        self.assertIn("**`shop.__main__.<module>`** (main-module, reaches 5 functions)", t)
        self.assertIn("    - `shop.orders.price_of` _(in a loop)_", t)
        self.assertIn("1. [`shop.__main__`](modules/shop.__main__.md) - entry point", t)
        self.assertIn("| `shop.billing` (cycle) |", t)
        self.assertIn("certain: `shop.orders._unused_helper`", t)
        self.assertIn("_First run for this project", t)

    def test_module_page(self):
        page = build_module_page(self.result, "shop.orders")
        self.assertIn("- **File:** `shop/orders.py` (module, 46 lines)", page)
        self.assertIn("- [`shop.cli`](shop.cli.md)", page)                       # used by
        self.assertIn("Called by: `shop.cli.main`, `tests.test_orders.test_place_order`", page)
        self.assertIn("- unused import (certain): `import os` (line 2)", page)
        self.assertIn("in import cycle `import-cycle-1`", page)

    def test_write(self):
        with temp_dir() as out:
            path = write_dossier(self.result, out, T1)
            self.assertTrue(os.path.isfile(path))
            pages = sorted(os.listdir(os.path.join(out, "modules")))
            self.assertEqual(len(pages), 17)
            self.assertIn("shop.orders.md", pages)


if __name__ == "__main__":
    unittest.main()
