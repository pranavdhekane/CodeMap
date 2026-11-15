# Code Mapper: Status

_Last updated: 2026-10-24_ (reports now saved in the tool's folder)

## Goal
Python tool that scans a project and gives:
- an overview of all functions
- a history of which function calls which
- loop detection

Built in small batches. Single file (`code_mapper.py`) for now; split into modules once it grows.

## Done

### Batch 1: initial draft (v0.1)
- [x] 1. Traverse all folders and files (`find_python_files`), skips `.git`, `venv`, `__pycache__`, `reports`, etc.
- [x] 2. List all functions module-wise (`analyze_module`), including methods (`Class.method`) and nested functions (`outer.inner`)
- [x] 3. Show docstrings (module and function), inputs (args with annotations/defaults, return type) and calls made in each function
- [x] 4. Timestamped report: `reports/<YYYY-MM-DD>/report_<HH-MM-SS>.md`, saved in the tool's own folder (next to `code_mapper.py`), not in the scanned project

## How to run
```
python code_mapper.py [project_folder] [--quiet]
```

## Code layout (single file)
| Section | Purpose |
|---|---|
| Data models | `CallInfo`, `FunctionInfo`, `ModuleInfo` |
| Traversal | `find_python_files` |
| Parsing | `_FunctionExtractor`, `_CallCollector`, `analyze_module` |
| Report | `build_report`, `write_report` |
| CLI | `main` |

## Known limitations
- Calls are recorded as written (`self.save`, `os.path.join`); they are **not yet resolved** to the actual function/module they point to
- Python files only; files with syntax errors are listed as errors, not skipped silently
- Calls inside nested functions are attributed to the nested function, not the parent

## Next (ideas, not started)
- [ ] Resolve calls to real functions (handle imports, `self.method`, aliases)
- [ ] Call history: keep a record per run and diff between runs
- [ ] Build call graph
- [ ] Loop detection: `for`/`while` inside functions, plus recursion / circular call chains in the call graph
- [ ] Split into modules (scanner, parser, report, graph)