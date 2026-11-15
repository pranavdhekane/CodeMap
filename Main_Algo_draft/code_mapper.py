"""
code_mapper.py
==============
Scans a Python project and reports every function, grouped by module.

Current features (v0.1):
    1. Traverse all folders/files of a project
    2. List all functions/methods, module-wise (names can repeat across files)
    3. Show module/function docstrings, inputs (arguments) and the calls each
       function makes
    4. Write a timestamped report to  reports/<YYYY-MM-DD>/report_<HH-MM-SS>.md
       (saved next to this script, not inside the scanned project)

Usage:
    python code_mapper.py                 # scan current folder
    python code_mapper.py path/to/project # scan another project
    python code_mapper.py . --quiet       # don't print to console, only write report

Planned (not built yet): call history, loop / recursion detection, module split.
"""

import argparse
import ast
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
# Folders we never descend into
IGNORE_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", "venv", ".venv", "env", ".env",
    "node_modules", ".idea", ".vscode", ".mypy_cache", ".pytest_cache",
    ".tox", "build", "dist", "site-packages", "reports",
}
REPORTS_DIR_NAME = "reports"
# Folder where this script lives; reports are saved here, not in the scanned project
TOOL_DIR = os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #
@dataclass
class CallInfo:
    """One function call found inside a function body."""
    name: str      # e.g. "helper" or "self.save" or "os.path.join"
    line: int


@dataclass
class FunctionInfo:
    """Everything we know about one function / method."""
    name: str                     # short name, e.g. "save"
    qualified_name: str           # e.g. "Database.save" or "outer.inner"
    line: int
    is_async: bool = False
    args: List[str] = field(default_factory=list)   # e.g. ["self", "path: str", "retries=3"]
    returns: Optional[str] = None
    docstring: Optional[str] = None
    calls: List[CallInfo] = field(default_factory=list)


@dataclass
class ModuleInfo:
    """One .py file."""
    path: str                     # path relative to project root
    docstring: Optional[str] = None
    functions: List[FunctionInfo] = field(default_factory=list)
    error: Optional[str] = None   # set if the file could not be parsed


# --------------------------------------------------------------------------- #
# Task 1: traverse folders and files
# --------------------------------------------------------------------------- #
def find_python_files(root: str) -> List[str]:
    """Return sorted relative paths of every .py file under `root`."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        # prune ignored folders in-place so os.walk skips them
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORE_DIRS)
        for fname in sorted(filenames):
            if fname.endswith(".py"):
                full = os.path.join(dirpath, fname)
                found.append(os.path.relpath(full, root))
    return found


# --------------------------------------------------------------------------- #
# Task 2 + 3: parse a module and extract functions, docstrings, args, calls
# --------------------------------------------------------------------------- #
def _dotted_name(node: ast.AST) -> str:
    """Turn a call target into text: Name -> 'foo', Attribute -> 'a.b.c'."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted_name(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):            # e.g. foo()()  or  get().run()
        return f"{_dotted_name(node.func)}()"
    if isinstance(node, ast.Subscript):       # e.g. handlers[x]()
        return f"{_dotted_name(node.value)}[...]"
    return "<expr>"


def _format_args(args: ast.arguments) -> List[str]:
    """Return arguments as readable strings with annotations and defaults."""
    out = []

    def fmt(a: ast.arg, default: Optional[ast.AST] = None) -> str:
        s = a.arg
        if a.annotation is not None:
            s += f": {ast.unparse(a.annotation)}"
        if default is not None:
            s += f" = {ast.unparse(default)}" if a.annotation else f"={ast.unparse(default)}"
        return s

    positional = args.posonlyargs + args.args
    # defaults align to the END of the positional list
    pad = [None] * (len(positional) - len(args.defaults))
    defaults = pad + list(args.defaults)
    for a, d in zip(positional, defaults):
        out.append(fmt(a, d))
    if args.vararg:
        out.append("*" + fmt(args.vararg))
    elif args.kwonlyargs:
        out.append("*")
    for a, d in zip(args.kwonlyargs, args.kw_defaults):
        out.append(fmt(a, d))
    if args.kwarg:
        out.append("**" + fmt(args.kwarg))
    return out


class _CallCollector(ast.NodeVisitor):
    """Collects calls inside ONE function body (does not enter nested defs)."""

    def __init__(self):
        self.calls: List[CallInfo] = []

    def visit_Call(self, node: ast.Call):
        self.calls.append(CallInfo(_dotted_name(node.func), node.lineno))
        self.generic_visit(node)

    # nested functions/classes are reported as their own entries
    def visit_FunctionDef(self, node):
        pass

    def visit_AsyncFunctionDef(self, node):
        pass

    def visit_ClassDef(self, node):
        pass


class _FunctionExtractor(ast.NodeVisitor):
    """Walks a module and builds FunctionInfo for every def (incl. methods, nested)."""

    def __init__(self):
        self.functions: List[FunctionInfo] = []
        self._scope: List[str] = []       # names of enclosing classes/functions

    def _handle_function(self, node, is_async: bool):
        qualified = ".".join(self._scope + [node.name])
        collector = _CallCollector()
        for stmt in node.body:
            collector.visit(stmt)

        self.functions.append(FunctionInfo(
            name=node.name,
            qualified_name=qualified,
            line=node.lineno,
            is_async=is_async,
            args=_format_args(node.args),
            returns=ast.unparse(node.returns) if node.returns else None,
            docstring=ast.get_docstring(node),
            calls=collector.calls,
        ))

        self._scope.append(node.name)
        self.generic_visit(node)          # find nested functions
        self._scope.pop()

    def visit_FunctionDef(self, node):
        self._handle_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node):
        self._handle_function(node, is_async=True)

    def visit_ClassDef(self, node):
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()


def analyze_module(root: str, rel_path: str) -> ModuleInfo:
    """Parse one file and return its ModuleInfo."""
    module = ModuleInfo(path=rel_path)
    full = os.path.join(root, rel_path)
    try:
        with open(full, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=rel_path)
    except (SyntaxError, UnicodeDecodeError, OSError) as exc:
        module.error = f"{type(exc).__name__}: {exc}"
        return module

    module.docstring = ast.get_docstring(tree)
    extractor = _FunctionExtractor()
    extractor.visit(tree)
    module.functions = extractor.functions
    return module


def analyze_project(root: str) -> List[ModuleInfo]:
    """Task 1 + 2 + 3 combined: scan the whole project."""
    return [analyze_module(root, p) for p in find_python_files(root)]


# --------------------------------------------------------------------------- #
# Report building (Markdown) -- used for both console and file output
# --------------------------------------------------------------------------- #
def _indent_doc(doc: str, prefix: str = "> ") -> str:
    return "\n".join(prefix + line if line else prefix.rstrip() for line in doc.splitlines())


def build_report(root: str, modules: List[ModuleInfo], generated_at: datetime) -> str:
    total_funcs = sum(len(m.functions) for m in modules)
    lines = [
        "# Code Mapper Report",
        "",
        f"- **Project:** `{os.path.abspath(root)}`",
        f"- **Generated:** {generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Modules scanned:** {len(modules)}",
        f"- **Functions found:** {total_funcs}",
        "",
        "## Summary",
        "",
        "| Module | Functions | Module docstring |",
        "|---|---:|:---:|",
    ]
    for m in modules:
        status = "error" if m.error else ("yes" if m.docstring else "no")
        lines.append(f"| `{m.path}` | {len(m.functions)} | {status} |")
    lines.append("")

    for m in modules:
        lines += [f"## Module: `{m.path}`", ""]
        if m.error:
            lines += [f"Could not parse: `{m.error}`", ""]
            continue
        if m.docstring:
            lines += ["**Module docstring:**", "", _indent_doc(m.docstring), ""]
        else:
            lines += ["_No module docstring._", ""]
        if not m.functions:
            lines += ["_No functions defined._", ""]
            continue

        for fn in m.functions:
            prefix = "async " if fn.is_async else ""
            sig = f"{prefix}def {fn.qualified_name}({', '.join(fn.args)})"
            if fn.returns:
                sig += f" -> {fn.returns}"
            lines += [f"### `{fn.qualified_name}`  (line {fn.line})", "", "```python", sig, "```", ""]

            if fn.docstring:
                lines += ["**Docstring:**", "", _indent_doc(fn.docstring), ""]
            else:
                lines += ["_No docstring._", ""]

            lines.append(f"**Inputs:** {', '.join(f'`{a}`' for a in fn.args) if fn.args else '_none_'}")
            lines.append("")

            if fn.calls:
                lines.append("**Calls:**")
                lines.append("")
                for c in fn.calls:
                    lines.append(f"- `{c.name}()` (line {c.line})")
            else:
                lines.append("**Calls:** _none_")
            lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Task 4: timestamped, date-wise report in reports/ folder
# --------------------------------------------------------------------------- #
def write_report(content: str, generated_at: datetime) -> str:
    """Save to <tool folder>/reports/<YYYY-MM-DD>/report_<HH-MM-SS>.md and return path.

    The reports live next to code_mapper.py, NOT inside the scanned project.
    """
    day_dir = os.path.join(TOOL_DIR, REPORTS_DIR_NAME, generated_at.strftime("%Y-%m-%d"))
    os.makedirs(day_dir, exist_ok=True)
    path = os.path.join(day_dir, f"report_{generated_at.strftime('%H-%M-%S')}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Map functions in a Python project.")
    parser.add_argument("root", nargs="?", default=".", help="project folder (default: .)")
    parser.add_argument("--quiet", action="store_true", help="don't print the report to console")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"Error: '{root}' is not a folder", file=sys.stderr)
        return 1

    now = datetime.now()
    modules = analyze_project(root)
    report = build_report(root, modules, now)

    if not args.quiet:
        print(report)
    path = write_report(report, now)
    print(f"\nReport saved to: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())