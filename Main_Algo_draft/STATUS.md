# Code Mapper: Status

_Last updated: 2026-11-17_ (Stages 1 to 6 and the optional 2.9 complete, tool is now v0.7; Stage 7 = move into `backend/core`)

## Goal
Python tool that scans a project and gives:
- an overview of all functions
- a history of which function calls which
- loop detection

Long-term, this prototype becomes the engine for **CodeMap** (air-gapped, zero-telemetry, `ast`-only, deterministic): dependency maps, call graphs, circular dependency detection (SCC), dead code identification and onboarding dossiers.

Built in small batches. The draft is a proof of concept of how much a static algorithm can get out of a Python project; it is kept as one self-contained file (`code_mapper.py`) so it can later be dropped into whichever engine CodeMap ends up using, as the Python algorithm next to algorithms for other languages (see Batch 8 and "The output contract").

## Where we stand
v0.7 finishes the draft: everything up to Stage 6 is built and tested, in one file with one input / output boundary (`run(root) -> dict`, written to `result_<time>.json` on every scan with everything the algorithm found). It has light type inference (2.9), handles the awkward inputs (non-UTF-8 files, huge files, symlinks, `.pyi` stubs, namespace packages), has the new CLI options (`--format`, `--output`, `--ignore`, `--no-reports`, ...), saves a snapshot per run and reports what changed since the previous run, and writes an onboarding dossier with one page per module. 66 unit tests (`python -m unittest discover tests`, about 2 s) cover every stage, including a golden-file test of the report. Each restructuring (split into a package, then back into one file) was checked byte for byte on the seeded project and asyncio. **Next: decide the engine, then Stage 7 (wire `run()` into it).**

Measured on real code (5.4; installed open-source packages plus stdlib packages, v0.5 vs v0.7, same machine):

| Project | Files | Lines | Calls | Resolved v0.5 | Resolved v0.7 | via inferred types | Call edges v0.5 / v0.7 | Dead code v0.7 (certain / likely / uncertain) | Time v0.7 |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| click | 17 | 12,179 | 1,989 | 67.4% | 70.9% | 70 | 449 / 510 | 1 / 61 / 130 | 0.3 s |
| requests | 19 | 6,385 | 984 | 70.0% | 71.5% | 15 | 226 / 240 | 0 / 32 / 48 | 0.2 s |
| httpx | 23 | 8,828 | 1,559 | 60.4% | 65.1% | 74 | 358 / 428 | 0 / 51 / 131 | 0.2 s |
| jinja2 | 25 | 14,425 | 3,057 | 69.5% | 74.7% | 159 | 775 / 893 | 1 / 102 / 351 | 0.4 s |
| fastapi | 48 | 21,048 | 1,845 | 73.7% | 75.8% | 39 | 444 / 478 | 1 / 69 / 173 | 0.4 s |
| asyncio (stdlib) | 35 | 14,971 | 3,393 | 56.4% | 57.5% | 37 | 881 / 917 | 2 / 41 / 302 | 0.5 s |
| email (stdlib) | 29 | 10,507 | 2,589 | 52.7% | 55.2% | 64 | 597 / 635 | 4 / 45 / 212 | 0.3 s |

Type inference adds 1 to 5 points of resolved calls and 4 to 16% more call edges, and every one of those edges removes dead-code noise (requests: 72 to 48 `uncertain` findings). The whole `Lib` folder of Python 3.14 (1,850 files, 83k call-graph nodes, ~500 MB peak memory) runs in roughly 30 s to 3 min on this laptop: wall-clock and even CPU time vary by up to 5x between identical runs (CPU throttling / memory pressure), so timings above are indicative only. By call count the v0.7 parser does about 6% more work than v0.5 (type hints and fingerprints); the later stages are unchanged.

### v0.5 summary (kept for reference)
v0.5 finished Stage 4: seven analyzers run on the two graphs (import cycles, call cycles / recursion, loop report, entry points, dead code, unused / missing imports, metrics) and every finding is labelled **certain / likely / uncertain**. The analysis is part of the markdown report, is saved as `analysis.json`, and can be produced from a saved `graph.json` without the code (`--from-graph ... --analyze`). The seeded test project (`tests/fixtures/seeded_project`, 11 unit tests, `python -m unittest discover tests`) is detected exactly. Measured on real code: asyncio 0.4 s (2 import cycles, 1 call cycle, 4 direct recursions, 14 loop calls into looping code, 362 dead-code candidates of which 2 certain / 46 likely / 314 uncertain, 101 entry points); the whole stdlib (16,527 call-graph nodes) 6.4 s. Two runs on the same code give byte-identical files (graph, analysis, Mermaid, DOT). **Stage 5 (tests and module split)** is next. The optional 2.9 (type inference) is still open; it would lift call-graph coverage and make dead-code results more trustworthy.

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

### Batch 6: Stage 5 (quality, tests, structure) and 2.9 (light type inference) (v0.6)
- [x] 5.5 Split into the `codemap_engine` package: `config`, `models`, `scanner`, `parser`, `resolver`, `graph`, `analyzers`, `report`, `pipeline`, `cli` (later `history`, `dossier`). `code_mapper.py` is now a thin shim: same command line, and `import code_mapper as cm` still exposes every function (private helpers too). Verified byte for byte against v0.5 on the seeded project and asyncio (graph.json, analysis.json, Mermaid, DOT, report) before adding anything. _(Merged back into one file in Batch 8.)_
- [x] `run_pipeline(root, ignore=..., analyze=..., min_confidence=..., max_bytes=..., skip_dirs=...)` runs every stage in one call and returns a `PipelineResult` (modules, resolver, graphs, import issues, analysis, warnings): the seed of the engine contract for Stage 7
- [x] 2.9 Light type inference. A name gets a type only when the code is unambiguous, and calls resolved through it are flagged `inferred` (graph site `"inferred": true`, edge confidence at most `likely`, counted in the coverage section):
  - `x = Foo()`, `x = make()` with `-> Foo`, `x = obj.method()` with a return annotation (also a string, `Optional[...]`, `Foo | None`, `Annotated[...]`, `Self`)
  - `x: Foo`, annotated parameters `def f(db: Database)` (only while the parameter is not re-bound)
  - `self.db = Database()` / `self.db: Database` in any method, class-level `db: Database` / `db = Database()`, inherited from project base classes
  - `with Foo() as x` (uses `Foo.__enter__`'s return annotation when there is one), `async with`, `await make()`
  - module-level `ENGINE = Engine()` used from functions and from other modules
  - a name bound to two different things (or to anything else as well) stays untyped; `List[Foo]` / `Type[Foo]` are not instances of Foo
- [x] 5.3 Edge cases: files over `--max-file-mb` (default 5) are listed as errors; encoding taken from the BOM / PEP 263 `# coding:` line like Python does, and a file that is not valid in its encoding is read as latin-1 with a warning instead of being dropped; very deep nesting (`RecursionError`) becomes a parse error; symlinked folders are never followed (no loops) and symlinked files that point outside the scanned folder are skipped; `.pyi` stubs are read only when there is no `.py` of the same name, and their declarations are never reported as dead code; folders without `__init__.py` imported directly (`import nsdir`) get an import-graph node of kind `namespace`
- [x] 5.6 CLI: `--format md|json`, `--output DIR`, `--ignore PATTERN` (repeatable / comma-separated fnmatch on names and relative paths), `--no-reports`, `--max-file-mb`, `--version`; the output folder is never scanned even when it sits inside the project; with `--format json` stdout carries only the JSON (the summary lines go to stderr)
- [x] 5.7 Python 3.9+ check on import, and a test that the engine imports only the standard library, no networking module, and keeps to Python 3.9 syntax
- [x] 5.1 / 5.2 Tests: three fixture projects (`seeded_project`: cycles, recursion, loops, dead code, imports; `edge_project`: aliases, re-exports, star imports, circular aliases, nested defs, `super()`, syntax error, latin-1 file with and without a coding line, stubs, namespace folder, ignored `build/`; `typed_project`: every inference rule and the cases that must stay unresolved) and 62 unit tests, one file per stage plus CLI, meta and a golden-file test of the markdown report (`tests/golden/edge_project_report.md`; regenerate with `CODEMAP_UPDATE_GOLDEN=1` after an intended change)
- [x] 5.4 Run on click, requests, httpx, jinja2, fastapi, asyncio, email and the whole stdlib (table above)
- [x] Reports and warnings use forward-slash paths on every OS (the golden file is the same on Windows and Linux)

The seeded fixture that `test_stage4_seeded.py` needs was missing from the folder (only the test file was there); it was rebuilt from the test's expectations and all 11 original assertions pass on it unchanged.

### Batch 7: Stage 6 (run history and onboarding dossier) (v0.7)
- [x] 6.1 Snapshot per run (`history.py`): modules, every function / class with its signature and a fingerprint of its source lines, call and import edges, findings and totals, saved as `<output>/history/<project>-<hash of its path>/snapshot_<date>_<time>.json`. Each scan is compared with the previous snapshot: modules / functions added, removed and changed (signature or body; a function that only moved is not changed), call and import edges added / removed, findings new and gone, totals that changed. Shown in the report ("Changes since the previous run"), saved as `diff.json`, summarised on the console. `--history` lists the snapshots, `--diff OLD NEW` compares two of them, `--diff OLD` compares a fresh scan with OLD, `--no-history` turns it off
- [x] 6.2 Onboarding dossier (`dossier.py`, `dossier_<time>/dossier.md`): at a glance (size, packages, entry points, coverage, findings), where execution starts, main flows (call tree from each entry point, or from the public functions that reach the most code when a library has no entry points), architecture (packages collapsed to at most ~25 groups, Mermaid diagram, foundations first, cycles marked), key modules, hot spots (most called, calls the most, largest functions, deepest loops), known problems, suggested reading order (top-down from the entry points), changes since the previous run, index of all modules
- [x] 6.3 One page per module (`dossier_<time>/modules/<module>.md`): docstring, what it depends on (project modules with lines, stdlib / third-party), who imports it, classes and methods, every function with signature, size, docstring summary, calls, outside calls, callers, and the findings that concern the module

Verified on the seeded project (the dossier tests check sections, flows, reading order, cycles and module pages) and by editing a copy of it between two runs (the diff test checks one removed module, one added and two changed functions, a fixed unused import and the dead-code changes exactly). Read through on click, where it also showed the two fixes made: library fallback for the main flows and docstring summaries taken from the first paragraph.

### Batch 8: back to one file, with an engine boundary (v0.7, same behaviour)
The draft is a proof of concept of how much static analysis can get out of a Python project. It will become one of several language algorithms behind an engine that is not decided yet, so it is kept as **one self-contained file** with a single input / output boundary that the engine can rewire later.
- [x] The Stage 5 package was merged back into `code_mapper.py` (4,400 lines, stdlib only). Checked byte for byte against the package version on the seeded project and asyncio (graphs, analysis, report and dossier identical) before the package was removed
- [x] ENGINE BOUNDARY section at the end of the file: `run(root, ...) -> dict` is the algorithm's whole input -> output; `run_pipeline()` gives the same as live objects; `write_outputs()` / the CLI are only one way of delivering it
- [x] "Log everything": every scan also writes `result_<time>.json`, one JSON with everything the algorithm found: every module, import (with origin), class (with resolved bases and typed attributes), function (signature, docstring, decorators, size, fingerprint, loops, type hints, every call with how it was resolved), aliases, `__all__`, names used, the symbol table, resolution coverage with reasons, both graphs, import issues, all findings, the snapshot, the diff with the previous run, warnings, options and the time per stage. `--format json` prints the same dict
- [x] `tests/test_result_contract.py` pins the keys of that dict (66 tests in total)

## How to run
```
python code_mapper.py [project_folder]                                # report + result.json + graphs + dossier + snapshot
python code_mapper.py [project_folder] --quiet --output out/          # files somewhere else, nothing on screen
python code_mapper.py [project_folder] --ignore migrations --ignore "*_pb2.py"
python code_mapper.py [project_folder] --format json --no-reports     # the full result on stdout, nothing written
python code_mapper.py [project_folder] --min-confidence likely        # hide the uncertain findings
python code_mapper.py [project_folder] --no-analysis                  # graphs only
python code_mapper.py [project_folder] --query callers pkg.core.Engine.make --depth 2
python code_mapper.py --from-graph reports/<date>/graphs_<time>/graph.json --query imports pkg.core --depth 0
python code_mapper.py --from-graph reports/<date>/graphs_<time>/graph.json --analyze
python code_mapper.py [project_folder] --history                      # saved snapshots of this project
python code_mapper.py --diff reports/history/<project>/snapshot_A.json reports/history/<project>/snapshot_B.json
python code_mapper.py --help                                          # every option
python -m unittest discover tests                                     # all tests (run from the tool folder)
```
`--depth` defaults to 1; 0 follows all levels. One scan writes, under `reports/` next to `code_mapper.py` (or `--output`):

```
<date>/report_<time>.md (or .json)       human report (+ "Changes since the previous run")
<date>/result_<time>.json                EVERYTHING the algorithm found (the engine output)
<date>/graphs_<time>/                    graph.json, analysis.json, diff.json, call/import graph .mmd and .dot
<date>/dossier_<time>/dossier.md         onboarding dossier
<date>/dossier_<time>/modules/*.md       one page per module
history/<project>-<hash>/snapshot_<date>_<time>.json
```
The report lists at most 25 rows per list; the JSON files and `--from-graph --analyze` are complete. `--no-graphs`, `--no-dossier`, `--no-history` skip one output, `--no-reports` writes nothing.

From code (what the engine will call):
```python
import code_mapper
result = code_mapper.run("path/to/project", ignore=["migrations"])     # one JSON-safe dict
result["facts"]["modules"], result["graphs"]["call"], result["analysis"]["dead_code"], result["run"]["timings_s"]
later = code_mapper.run("path/to/project", previous=result["snapshot"])  # later["diff"]: what changed
```

### The output contract (`result_to_dict`, `RESULT_SCHEMA_VERSION = 1`)
| Key | Content |
|---|---|
| `algorithm` | name, language (`python`), version, method |
| `project` | name, root, generated_at |
| `run` | options used, seconds per stage (`1_scan_and_parse`, `2_resolve`, `3_graphs`, `4_analyze`) |
| `warnings` | files read with an encoding fallback, skipped symlinks, duplicate module names |
| `totals` | modules, errors, lines, classes, functions, imports, loops |
| `resolution` | calls, resolved %, by status, unresolved reasons (+ what each means), external kinds, inferred |
| `facts` | `modules` (everything the parser and resolver recorded, per module), `symbols`, `duplicate_modules` |
| `graphs` | `call` and `import`: nodes with attributes, edges with every call / import site |
| `import_issues` | unused imports and imports of missing project modules |
| `analysis` | entry points, cycles, recursion, loops, dead code, imports, metrics, summary, notes |
| `snapshot` | compact summary to pass as `previous` next time |
| `diff` | changes since `previous` (None on a first run) |

A future algorithm for another language should return the same top-level keys; `facts` is the part that is allowed to differ per language.

## Code layout (`code_mapper.py`, sections in order)
| Section | Main names |
|---|---|
| Config | ignored folders, file-size limit, version, schema versions, query kinds |
| Data models | `CallInfo`, `LoopInfo`, `ImportInfo`, `AliasInfo`, `FunctionInfo`, `ClassInfo`, `ModuleInfo` |
| Stage 1a scanner | `find_python_files` (ignore patterns, stubs, symlinks, skipped folders), `module_name_from_path` |
| Stage 1b parser | `_FunctionExtractor`, `_ScopeCollector` (calls, loops, type hints), `_NameUsage`, `analyze_module` (reading / encodings / limits), `analyze_project` |
| Stage 2 resolver | `Resolver` (symbol table, import maps, call resolution, type inference), `resolve_project`, `REASON_HELP` |
| Stage 3 graphs | `Graph` (nodes, edges, reverse lookups, BFS, JSON / Mermaid / DOT), `build_graphs`, `write_graphs`, `load_graphs`, `run_query` |
| Stage 4 analyzers | `_scc`, cycles, recursion, loops, entry points, dead code, import issues, metrics, `analyze_graphs`, `filter_analysis` |
| Report | `analysis_lines`, `build_report` (markdown), `build_report_data`, `write_report` |
| Stage 6.1 history | `build_snapshot`, `save_snapshot` / `list_snapshots` / `load_snapshot`, `diff_snapshots`, `diff_lines` |
| Stage 6.2 / 6.3 dossier | `build_dossier`, `build_module_page`, `write_dossier` |
| Pipeline and ENGINE BOUNDARY | `run_pipeline` -> `PipelineResult`, `facts_to_dict`, `result_to_dict`, **`run`**, `write_outputs` |
| CLI | `main` |

Tests: `tests/test_stage1_scanner_parser.py`, `test_stage2_resolver.py`, `test_stage3_graphs.py`, `test_stage4_seeded.py`, `test_stage6_history_dossier.py`, `test_result_contract.py`, `test_cli.py` (CLI + golden report), `test_meta.py` (one file, stdlib only, no network, Python 3.9 syntax); fixtures in `tests/fixtures/`, golden file in `tests/golden/`.

## Known limitations
- Type inference is deliberately light (2.9): no flow analysis, no generics / containers (`List[Foo]`, `dict[str, Foo]`), no inference from `isinstance`, from function arguments at call sites, or from return statements without an annotation; a name bound in two ways stays untyped. Calls on values of unknown type (`variable` / `self-attribute` / `instance-attribute`) are still most of the unresolved calls (24-45% of all calls are unresolved in the measured projects)
- `with Foo() as x` assumes `x` is a `Foo` when `Foo.__enter__` has no return annotation (the usual `return self`)
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
- Python files (`.py`, and `.pyi` when there is no `.py`) only; files with syntax errors are listed as errors, not skipped silently. Files over the size limit are not parsed at all
- Call graph has only resolved local / internal calls, so its edges are a lower bound: anything behind a value of unknown type is missing. Dead-code and "who calls me" answers inherit this (labelled with confidence)
- Import graph: `import a.b.c` is an edge to `a.b.c` only; the parent packages Python also runs are not added. A namespace folder gets a node only when it is imported directly. Imports of modules in files with syntax errors give no edge. Self-imports are skipped
- Symlinked folders are never followed (also those pointing inside the project); on Windows, creating symlinks needs developer mode, so the symlink test is skipped there
- History: snapshots are keyed by the project's absolute path (moving the folder starts a new history); a function counts as changed when any of its lines change, comments and blank lines included; renames show as one removed and one added function
- Dossier: entry points, flows, "key modules" and the reading order come from the same heuristics as the analyzers (no AI); architecture groups are dotted-name prefixes, not real layers
- Wall-clock timings on the development laptop vary by up to 5x between identical runs (CPU throttling / memory pressure); compare versions by call counts or on a quiet machine
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

- [x] 2.9 (optional, lifts coverage) Light type inference: `x = Foo()`, `self.attr = Foo()` in `__init__`, annotated parameters (`db: Database`) so `x.run()` / `self.db.save()` resolve

**Done when:** on a real project, most internal calls resolve and the unresolved ones are explained. _(met for 2.1-2.8, see Batch 3; 2.9 see Batch 6)_

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
- [x] 5.1 Add a `tests/` folder with small fixture projects (cycles, aliases, inheritance, nested defs, syntax errors) _(seeded_project, edge_project, typed_project)_
- [x] 5.2 Unit tests per feature from Stages 1-4; golden-file test for the report
- [x] 5.3 Handle edge cases: huge files, non-UTF-8 files, symlink loops, `.pyi`, namespace packages
- [x] 5.4 Run on 2-3 real open-source projects and record resolution coverage and run time _(5 packages + 2 stdlib packages + whole stdlib, see Where we stand)_
- [x] 5.5 Split single file into modules: `scanner`, `parser`, `resolver`, `graph`, `analyzers`, `report`
- [x] 5.6 Add CLI options: `--format md|json`, `--output`, `--ignore`, `--no-reports`
- [x] 5.7 Python version check (`ast.unparse` needs 3.9+) and zero external dependencies confirmed

**Done when:** tests pass, the tool runs on real projects, and the code is split cleanly. _(met, see Batch 6)_

### Stage 6: Run history and onboarding dossier
Goal: the features that make the report useful over time.
- [x] 6.1 Store a snapshot per run (JSON) and diff between runs: new / removed / changed functions and edges
- [x] 6.2 Onboarding dossier: project overview, entry points, key modules, hot spots, cycles, dead code, how data flows
- [x] 6.3 Per-module summary pages / sections with inbound and outbound dependencies

**Done when:** a new developer can read one generated document and understand the project's structure. _(built, see Batch 7; worth confirming with a teammate who has not seen the code)_

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
5. ~~**Batch 6:** Stage 5 tests and module split, plus 2.9 type inference~~ done
6. ~~**Batch 7:** Stage 6 (run history, onboarding dossier, module pages)~~ done
7. ~~**Batch 8:** back to one file with an engine boundary and a full `result.json`~~ done
8. **Next:** decide the engine; then Stage 7: call `run()` from it (input: folder / zip; output: the result dict -> database / API, 7.2 is the output contract above), split the file only if the engine needs it, and add algorithms for other languages that return the same top-level keys. Stage 8 (optional AI) after that
