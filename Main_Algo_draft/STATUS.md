# Code Mapper: Status

_Last updated: 2026-11-15_ (Stages 1, 2, 3 and 4 complete, tool is now v0.5)

## Goal
Python tool that scans a project and gives:
- an overview of all functions
- a history of which function calls which
- loop detection

Long-term, this prototype becomes the engine for **CodeMap** (air-gapped, zero-telemetry, `ast`-only, deterministic): dependency maps, call graphs, circular dependency detection (SCC), dead code identification and onboarding dossiers.

Built in small batches. Single file (`code_mapper.py`) for now; split into modules once Stage 5 starts.

## Where we stand
v0.5 finishes Stage 4: seven analyzers run on the two graphs (import cycles, call cycles / recursion, loop report, entry points, dead code, unused / missing imports, metrics) and every finding is labelled **certain / likely / uncertain**. The analysis is part of the markdown report, is saved as `analysis.json`, and can be produced from a saved `graph.json` without the code (`--from-graph ... --analyze`). The seeded test project (`tests/fixtures/seeded_project`, 11 unit tests, `python -m unittest discover tests`) is detected exactly. Measured on real code: asyncio 0.4 s (2 import cycles, 1 call cycle, 4 direct recursions, 14 loop calls into looping code, 362 dead-code candidates of which 2 certain / 46 likely / 314 uncertain, 101 entry points); the whole stdlib (16,527 call-graph nodes) 6.4 s. Two runs on the same code give byte-identical files (graph, analysis, Mermaid, DOT). **Stage 5 (tests and module split)** is next. The optional 2.9 (type inference) is still open; it would lift call-graph coverage and make dead-code results more trustworthy.

## Done

### Batch 1: initial draft (v0.1)
- [x] 1. Traverse all folders and files (`find_python_files`), skips `.git`, `venv`, `__pycache__`, `reports`, etc.
- [x] 2. List all functions module-wise (`analyze_module`), including methods (`Class.method`) and nested functions (`outer.inner`)
- [x] 3. Show docstrings (module and function), inputs (args with annotations/defaults, return type) and calls made in each function
- [x] 4. Timestamped report: `reports/<YYYY-MM-DD>/report_<HH-MM-SS>.md`, saved in the tool's own folder (next to `code_mapper.py`), not in the scanned project

### Batch 2: Stage 1, capture more facts (v0.2)
- [x] 1.1 Imports: `import x`, `import x as y`, `from a.b import c as d`, relative (`from . import x`, `from ..pkg import y`) with level, alias, star imports, and the scope each import sits in (module or inside a function/class)
- [x] 1.2 Dotted module name per file (`pkg/sub/mod.py` -> `pkg.sub.mod`, `__init__.py` -> `pkg`, plus an `is_package` flag for relative-import resolution)
- [x] 1.3 Classes as entities: name, qualified name, line, bases (incl. `metaclass=`), decorators, docstring, methods
- [x] 1.4 Decorators on functions, plus `enclosing_class` for methods
- [x] 1.5 Module-level and class-body calls collected under pseudo-function `<module>` (decorators and default values of defs count here too)
- [x] 1.6 Loops per function and scope (`for`, `async for`, `while`; line and nesting depth); each call also records `loop_depth`
- [x] 1.7 Module-level alias candidates (`x = some.func`, `x: T = y`) and the `if __name__ == "__main__":` block as pseudo-function `<main>`
- [x] 1.8 Only the tool's own `reports/` folder is skipped; a project's own `reports` package is now scanned
- [x] 1.9 Report shows imports, classes, aliases, module-level code, main block, loops, decorators; summary table has dotted name, imports, classes, loops

Verified on a fixture project covering every import form, nested loops (incl. `else` blocks), nested classes/functions, a syntax-error file, a `reports/` package, both orders of the `__main__` guard, and a skipped `venv/`.

### Batch 3: Stage 2, symbol table and call resolution (v0.3)
- [x] 2.1 Symbol table (`Resolver.symbols`): functions, methods, classes under fully qualified names (`pkg.core.Engine.make`); listed in the report
- [x] 2.2 Per-scope import maps (module level and inside functions); relative imports turned into absolute module names; each import gets `abs_module` and `origin` (internal / stdlib / third-party / unresolved)
- [x] 2.3 Every call classified: `local` (same module), `internal` (other project module), `external`, `unresolved`
- [x] 2.4 Resolves plain names, module attributes (`utils.parse()`), `import x as y`, module-level aliases, re-exports through `__init__.py`, and star imports of project modules; respects shadowing by parameters, local variables and nested defs
- [x] 2.5 `self.method()` / `cls.method()` resolved through the enclosing class and its project base classes (also from nested functions inside a method)
- [x] 2.6 `Foo()` -> `Foo.__init__`, `cls(...)`, `Foo().method()`, `Foo.method()`, `super().method()`
- [x] 2.7 Unresolved calls kept with a reason code and note (`variable`, `dynamic`, `self-attribute`, `member-not-found`, `external-base`, `name-not-found`, `not-in-module`, `star-import`, `function-attribute`, `relative-import`, `cycle`). Builtins are classed as `external` (note `builtin`), not unresolved
- [x] 2.8 Resolution coverage in the report header, a coverage section with a reason table, and a console summary line

Also added: a scanned folder that is itself a package (has `__init__.py`) now prefixes its name to every module, so absolute imports like `from mypkg.x import y` resolve. Verified on a fixture project (re-exports, aliases, circular aliases, inheritance, `super()`, star imports, shadowing, missing and too-deep relative imports) and on stdlib packages.

### Batch 4: Stage 3, graph building (v0.4)
- [x] 3.1 Call graph (`build_call_graph`): nodes = every function, method and class from the symbol table, plus the `<module>` / `<main>` scopes that make calls; edges = calls resolved as local or internal, each with all call sites (line, call text, loop depth, note such as `instantiates Foo`). External and unresolved calls are not edges; they are counted on the calling node (`external_calls` per target, `unresolved_calls`). Direct recursion shows as a self-edge; an edge has `in_loop` if any of its call sites sits in a loop
- [x] 3.2 Import graph (`build_import_graph`): nodes = project modules and packages; edges = project-internal imports with line, statement and scope; an edge has `top_level` = false when every import of it sits inside a function (cycle breakers)
- [x] 3.3 Reverse edges: `Graph.predecessors()` / `successors()` / `reach()`; report shows **Called by** per function and **Imported by** per module (capped at 20 entries each)
- [x] 3.4 Export to `reports/<date>/graphs_<time>/`: `graph.json` (schema_version 1, both graphs plus stats), `call_graph.mmd` / `.dot`, `import_graph.mmd` / `.dot` (diagrams show only connected nodes; thick/bold = call in loop, dotted/dashed = function-level import, `xN` = N sites). `load_graphs()` reads `graph.json` back
- [x] 3.5 Deterministic: everything sorted, no timestamps or absolute paths in the exports, forward-slash paths, fixed newlines
- [x] Queries: `--query callers|callees|importers|imports NODE [--depth N]`, works on a fresh scan or on a saved file with `--from-graph`; NODE may be a full id or a unique ending (`Engine.fact`); ambiguous or unknown names are reported

Verified on a fixture project (re-exports, `__main__` guard, inheritance, `super()`, recursion, loop calls, a function-level import that closes an import cycle) and on asyncio, email, json and concurrent. Run twice on the fixture and on asyncio: all five graph files byte-identical.

Bug found and fixed while verifying (belongs to Stage 2 import annotation): `from . import events` inside a package whose `__init__` star-imports submodules was recorded as an import of the package (`asyncio`) instead of the submodule (`asyncio.events`). That would have produced wrong edges and false cycles in the import graph. Now the target is the submodule (asyncio.events importers: 1 -> 15).

### Batch 5: Stage 4, analyzers (v0.5)
- [x] 4.1 Circular dependencies (`analyze_import_cycles`, `analyze_call_cycles`): iterative Tarjan SCC (no recursion limit) on both graphs. Import cycles are split by how the cycle closes: **import-time** (certain), **deferred** by a function-level import (likely), **typing-only** by `if TYPE_CHECKING:` (uncertain); each finding has an example cycle with the line and statement of every hop. Call cycles = mutual recursion, with an example cycle
- [x] 4.2 Recursion: direct (self-edge; certain for a plain-name call, likely when it goes through `self.` / `cls.` / `super()`, because an override may be the real target) and indirect (shortest cycle length per function, which cycle it belongs to)
- [x] 4.3 Loop report: scopes with nested loops (max depth), and calls made inside a loop into code that loops, is recursive, or reaches such code further down the chain (`indirect`, one level less confident)
- [x] 4.4 Entry points: `__main__` blocks, `__main__` modules, functions named `main`, handler decorators (`route`, `get`, `command`, `task`, `receiver`, ...), tests / fixtures / `setUp` hooks, names listed in `__all__` (re-exports followed to the real symbol)
- [x] 4.5 Dead code candidates (`find_dead_code`): functions, methods, classes with no caller outside themselves. Excludes entry points, dunder methods, methods overriding a project base-class method, classes used as a base class. A class counts as used if the class or any method is called, or `Foo()` runs (also when `__init__` is inherited). Also reported: code only called by dead code (one level less confident) and call cycles nobody else calls. Members are folded into their dead class / function
- [x] 4.6 Unused imports and imports of project modules that do not exist (`find_import_issues`). Names counted as used if read anywhere in the module, listed in `__all__`, or inside a string annotation. Lower confidence for package `__init__` (re-export), `try:` blocks (optional dependency), `TYPE_CHECKING`, modules calling `globals()` / `eval()` / `exec()`
- [x] 4.7 Metrics: fan-in, fan-out, most connected, depth of call / import chains (longest chain with example path; `~>` marks a move inside a cycle) for both graphs
- [x] 4.8 Confidence labels on every finding. Dead code: `certain` = private name with no reference anywhere; `likely` = public name, or chained on dead code; `uncertain` = signs of a false positive (name also used as a value / attribute, unresolved call ending in the same name, unknown decorator, framework base class, overridden in a subclass, defined in `__init__`). `--min-confidence` filters report, console and JSON

Also added: `graph.json` now also stores `import_issues` and extra node attributes for the analyzers (`max_loop_depth`, `referenced_as_value`, `unresolved_name_hits`, `exported`, `instantiated_from`, class `decorators`; import-edge sites get `type_checking`). Old `graph.json` files from v0.4 still load and are analysed, with a warning that the result is less exact. Parser: tracks `if TYPE_CHECKING:` and `try:` around imports, collects every name read (`used_names`), names used as values (`value_refs`), literal `__all__`, and use of `globals()` / `eval()` / `exec()`.

Verified on the seeded project (3 import cycles of the three kinds, 3 call cycles, 2 direct recursions, nested loops, 3 loop calls, 8 entry points, 9 dead-code findings at three confidence levels, 4 unused and 1 missing import, all exact), on asyncio, email, json, concurrent, unittest and the whole stdlib. Real bug found and fixed while verifying: `Foo()` resolves to an inherited `__init__` of a base class, so a class without its own `__init__` looked unused and was labelled `certain` dead (`asyncio.proactor_events._ProactorDuplexPipeTransport` and others). Instantiations are now recorded per class (`instantiated_from`, no extra edges) and counted as use. The seeded project has a regression case; the test fails without the fix.

## How to run
```
python code_mapper.py [project_folder] [--quiet] [--no-graphs]
python code_mapper.py [project_folder] --query callers pkg.core.Engine.make --depth 2
python code_mapper.py --from-graph reports/<date>/graphs_<time>/graph.json --query imports pkg.core --depth 0
python code_mapper.py [project_folder] --min-confidence likely        # hide the uncertain findings
python code_mapper.py [project_folder] --no-analysis                  # v0.4 behaviour, no analyzers
python code_mapper.py --from-graph reports/<date>/graphs_<time>/graph.json --analyze
python -m unittest discover tests                                     # seeded-project test (run from the tool folder)
```
`--depth` defaults to 1; 0 follows all levels. A normal scan writes `analysis.json` next to `graph.json`; the report lists at most 25 rows per list, the JSON and `--from-graph --analyze` are complete.

## Code layout (single file)
| Section | Purpose |
|---|---|
| Data models | `CallInfo`, `LoopInfo`, `ImportInfo`, `AliasInfo`, `FunctionInfo`, `ClassInfo`, `ModuleInfo`, `Symbol`, `ResolutionStats` |
| Traversal | `find_python_files`, `module_name_from_path` |
| Parsing | `_FunctionExtractor`, `_ScopeCollector`, `_NameUsage`, `_module_exports`, `_collect_aliases`, `analyze_module` |
| Resolution | `Resolver` (symbol table, import maps, call resolution), `resolve_project` |
| Graphs | `Graph` (nodes, edges, reverse lookups, BFS, JSON / Mermaid / DOT), `build_call_graph`, `build_import_graph`, `build_graphs`, `write_graphs`, `load_graphs`, `run_query` |
| Analyzers | `_scc`, `analyze_import_cycles`, `analyze_call_cycles`, `analyze_loops`, `find_entry_points`, `find_dead_code`, `find_import_issues`, `_graph_metrics`, `analyze_graphs`, `filter_analysis`, `analysis_lines` |
| Report | `build_report` (Called by / Imported by, Analysis section), `write_report` |
| CLI | `main` |

## Known limitations
- No type inference: `x = Foo(); x.run()` and `self.db.save()` stay unresolved (`variable` / `self-attribute`); these are the bulk of unresolved calls (roughly 40-60% of calls in stdlib packages)
- `self.method()` points to the class's own definition (or the nearest project base), not to subclass overrides
- Base-class lookup is depth-first, left to right (an approximation of Python's MRO); bases outside the project are treated as unknown
- Local variables are detected by assignment only; `global` / `nonlocal` names and `match` captures are not tracked
- Resolution is by dotted module name relative to the scanned folder: scan the folder that holds your top-level packages (for a `src/` layout, scan `src/`)
- Two files with the same dotted module name: the first one wins and a warning is shown
- `from X import *` of a non-project module makes unknown names `star-import` instead of `name-not-found`
- Decorators are recorded but not interpreted (a decorated function is still treated as the function itself)
- Dotted module names are relative to the scanned folder; if you scan a `src/` layout folder, names won't include outer packages
- Calls inside nested functions are attributed to the nested function, not the parent; class-body calls inside a function are attributed to that function
- Loops are `for` / `async for` / `while` statements only; comprehensions are not counted as loops
- `match` statements and `try`/`with` blocks are walked for calls, but only top-level `if __name__` guards are treated as the main block
- Python files only; files with syntax errors are listed as errors, not skipped silently
- No tests yet (verified by hand on fixtures and stdlib packages)
- Call graph has only resolved local / internal calls, so its edges are a lower bound: anything behind `x = Foo(); x.run()` or `self.db.save()` is missing until 2.9 (type inference). Dead-code and "who calls me" answers inherit this (Stage 4 must label them with confidence)
- Import graph: `import a.b.c` is an edge to `a.b.c` only; the parent packages Python also runs are not added. Imports of a folder without `__init__.py` (namespace package) and imports of modules in files with syntax errors give no edge. Self-imports are skipped
- Two functions with the same qualified name in one module (e.g. `@property` setter, `if/else` defs) share one call-graph node; their call sites are merged
- Mermaid refuses more than ~500 edges by default (asyncio's call graph has 844): use the `.dot` file or `--query` for big projects
- `graph.json` is large for big projects (asyncio: about 800 KB)

- Analyzers (Stage 4): dead-code and entry-point rules are heuristics. Public names may be used by code outside the scanned folder; `getattr` / string-based dispatch is invisible; console scripts in `setup.py` / `pyproject.toml` are not read (only `main()` by name, `__main__`, handler decorators and `__all__`)
- The "used as a value" hint matches by short name across the whole project (`on_done` is marked `uncertain` if any module reads an attribute or name `on_done` without calling it); it can make a finding `uncertain` without a real use, never the opposite
- Unused imports are judged per module by name: a function-level import that is unused while the same name is used elsewhere in the module is not found; `__all__` is only read when it is a literal list / tuple; names used only in comments, doctests or `typing.cast("X")` strings count as unused
- Import cycles: `TYPE_CHECKING` is recognised by the name `TYPE_CHECKING`; an import in a class body counts as import-time; an import-time cycle is a real dependency cycle but does not always crash (`from . import x` often survives it)
- A call cycle through `self.method()` is `likely`, not `certain`: the call may reach a subclass override instead
- Dead-code classes: `Foo().method()` and `Foo()` count as use; a class referenced only in annotations, `isinstance` or `except` is reported as `uncertain` (name used as a value)
- A `graph.json` written by v0.4 can be analysed but has no `TYPE_CHECKING` marks, re-export marks, loop depths or import issues (the tool warns; re-scan for exact results)
- `--min-confidence` filters findings, not the entry-point list or the metrics

## Roadmap (in stages)
Each stage builds on the previous one. Do not start a stage until the one before it is verified on a real project.

### Stage 1: Capture more facts (parser completeness)
Goal: record everything the later stages need, with no resolution yet.
- [x] 1.1 Capture imports: `import x`, `import x as y`, `from a.b import c as d`, relative imports (`from . import x`, `from ..pkg import y`), including level and alias
- [x] 1.2 Add a dotted module name per file (`pkg/sub/mod.py` -> `pkg.sub.mod`, `__init__.py` -> `pkg.sub`)
- [x] 1.3 Record classes as entities: name, line, bases, decorators, docstring, methods
- [x] 1.4 Record decorators on functions (needed for entry points and dead-code false positives)
- [x] 1.5 Capture module-level and class-body calls under a pseudo-function (`<module>`)
- [x] 1.6 Record `for` / `while` loops per function (line, kind, nesting depth) for loop detection
- [x] 1.7 Capture module-level assignments of aliases (`x = some.func`) and `if __name__ == "__main__":` blocks
- [x] 1.8 Fix `reports` ignore rule so it only skips the tool's own output folder
- [x] 1.9 Update report to show imports, classes and loops

**Done when:** a sample project's report lists every import, class and loop correctly. _(met, see Batch 2)_

### Stage 2: Symbol table and call resolution (the big value jump)
Goal: turn call text into references to real things.
- [x] 2.1 Build a project-wide symbol table: module -> functions, classes, methods (fully qualified names)
- [x] 2.2 Per-module import map: local name -> fully qualified target
- [x] 2.3 Classify every call as `local` (same module), `internal` (another project module), `external` (stdlib / third-party) or `unresolved`
- [x] 2.4 Resolve plain names (`helper()`), module attributes (`utils.parse()`), and aliases (`import numpy as np`)
- [x] 2.5 Resolve `self.method()` / `cls.method()` to the enclosing class, including inherited methods in the same project
- [x] 2.6 Resolve class instantiation (`Foo()` -> `Foo.__init__`) and `super().method()`
- [x] 2.7 Keep the unresolved calls with a reason code and note instead of dropping them (builtins count as external)
- [x] 2.8 Report resolution coverage (% resolved) so quality is measurable

- [ ] 2.9 (optional, lifts coverage) Light type inference: `x = Foo()`, `self.attr = Foo()` in `__init__`, annotated parameters (`db: Database`) so `x.run()` / `self.db.save()` resolve

**Done when:** on a real project, most internal calls resolve and the unresolved ones are explained. _(met for 2.1-2.8, see Batch 3)_

### Stage 3: Graph building
Goal: produce graphs as data, independent of the markdown report.
- [x] 3.1 Call graph: nodes = functions/methods, edges = resolved calls (with call-site line numbers)
- [x] 3.2 Import / module dependency graph: nodes = modules, edges = imports
- [x] 3.3 Reverse edges (who calls me / who imports me)
- [x] 3.4 Export graphs as JSON (stable schema) and Mermaid / DOT for quick viewing
- [x] 3.5 Deterministic ordering everywhere so two runs on the same code give identical output

**Done when:** `graph.json` can be loaded and queried without re-parsing the code. _(met, see Batch 4)_

### Stage 4: Analyzers (the actual insights)
Goal: answer the questions the tool exists for.
- [x] 4.1 Circular dependencies: Tarjan's SCC on the import graph (module cycles) and on the call graph (mutual recursion)
- [x] 4.2 Recursion detection: direct (self-call) and indirect (cycle length > 1)
- [x] 4.3 Loop report: loops per function, nested loops, and loops containing calls into recursive or looping functions
- [x] 4.4 Entry points: `__main__` blocks, CLI hooks, decorated route/handlers, test functions
- [x] 4.5 Dead code candidates: functions/classes with no inbound edges, excluding entry points, dunder methods, decorated callbacks and `__all__` exports
- [x] 4.6 Unused imports and imports of missing internal modules
- [x] 4.7 Simple metrics: fan-in, fan-out, depth of call chains, most-connected functions
- [x] 4.8 Label each finding with confidence (certain / likely / uncertain) to avoid false-positive noise

**Done when:** a seeded test project with known cycles, recursion and dead functions is detected exactly. _(met, see Batch 5 and `tests/test_stage4_seeded.py`)_

### Stage 5: Quality, tests and structure
Goal: make the draft trustworthy and ready to move into the product.
- [ ] 5.1 Add a `tests/` folder with small fixture projects (cycles, aliases, inheritance, nested defs, syntax errors) _(started: `tests/fixtures/seeded_project` covers cycles, recursion, inheritance, loops, dead code, imports; aliases, nested defs and syntax errors still missing)_
- [ ] 5.2 Unit tests per feature from Stages 1-4; golden-file test for the report
- [ ] 5.3 Handle edge cases: huge files, non-UTF-8 files, symlink loops, `.pyi`, namespace packages
- [ ] 5.4 Run on 2-3 real open-source projects and record resolution coverage and run time
- [ ] 5.5 Split single file into modules: `scanner`, `parser`, `resolver`, `graph`, `analyzers`, `report`
- [ ] 5.6 Add CLI options: `--format md|json`, `--output`, `--ignore`, `--no-reports`
- [ ] 5.7 Python version check (`ast.unparse` needs 3.9+) and zero external dependencies confirmed

**Done when:** tests pass, the tool runs on real projects, and the code is split cleanly.

### Stage 6: Run history and onboarding dossier
Goal: the features that make the report useful over time.
- [ ] 6.1 Store a snapshot per run (JSON) and diff between runs: new / removed / changed functions and edges
- [ ] 6.2 Onboarding dossier: project overview, entry points, key modules, hot spots, cycles, dead code, how data flows
- [ ] 6.3 Per-module summary pages / sections with inbound and outbound dependencies

**Done when:** a new developer can read one generated document and understand the project's structure.

### Stage 7: Move into the product (`backend/core`)
Goal: replace the `.gitkeep` placeholders with the validated engine.
- [ ] 7.1 Port modules into `backend/core/parser`, `graph`, `analyzers`, `docs`
- [ ] 7.2 Define a stable engine contract (input: path or zip; output: JSON schema) shared by Local and Cloud modes
- [ ] 7.3 Expose via FastAPI in `backend/app`; store results in SQLite (Local) / PostgreSQL (Cloud)
- [ ] 7.4 Feed graph JSON to the frontend dashboard
- [ ] 7.5 Confirm offline guarantee: no network calls, no telemetry in the core

### Stage 8: Optional AI layer (off by default)
- [ ] 8.1 Semantic explanations on top of the rule-based output (never replaces it)
- [ ] 8.2 Explicit opt-in switch; disabled in air-gapped / `RUN_LOCAL` mode unless a local model is configured

## Suggested order of work (next batches)
1. ~~**Batch 2:** Stage 1 (items 1.1 to 1.9)~~ done
2. ~~**Batch 3:** Stage 2 (items 2.1 to 2.8)~~ done
3. ~~**Batch 4:** Stage 3 (graphs)~~ done
4. ~~**Batch 5:** Stage 4 (SCC cycles on both graphs, recursion, loop report, entry points, dead code, metrics, confidence labels)~~ done
5. **Batch 6:** Stage 5 tests and module split; optionally 2.9 type inference first, since it raises call-graph coverage (56-64% resolved on stdlib) and turns many `uncertain` dead-code findings into `likely` / `certain`
