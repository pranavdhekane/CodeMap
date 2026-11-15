"""
code_mapper.py
==============
Scans a Python project and reports every module, class and function.

Features
--------
Batch 1 (v0.1)
    1. Traverse all folders/files of a project
    2. List all functions/methods, module-wise (names can repeat across files)
    3. Show module/function docstrings, inputs (arguments) and the calls each
       function makes
    4. Write a timestamped report to  reports/<YYYY-MM-DD>/report_<HH-MM-SS>.md
       (saved next to this script, not inside the scanned project)

Batch 2 (v0.2, roadmap Stage 1: capture more facts, no resolution yet)
    5. Imports: import / from-import / relative / aliases / star, with scope
    6. Dotted module name per file (pkg/sub/mod.py -> pkg.sub.mod)
    7. Classes as entities: bases, decorators, docstring, methods
    8. Decorators on functions
    9. Module-level and class-body calls, kept under a pseudo-function "<module>"
   10. Loops per function (kind, line, nesting depth); every call also knows
       how deep inside loops it sits
   11. Module-level alias candidates (x = some.func) and the
       `if __name__ == "__main__":` block (pseudo-function "<main>")
   12. Only this tool's own reports/ folder is skipped (not every folder named
       "reports" in the scanned project)

Batch 3 (v0.3, roadmap Stage 2: symbol table and call resolution)
   13. Project-wide symbol table: every module's functions, methods, classes
       under a fully qualified name (e.g. "pkg.core.Engine.make")
   14. Per-scope import maps (module level and inside functions), relative
       imports resolved to absolute module names
   15. Every call classified: local (same module), internal (other project
       module), external (builtin / stdlib / third-party) or unresolved
   16. Resolves plain names, module attributes, aliases, `import x as y`,
       re-exports through __init__.py, star imports of project modules
   17. Resolves self.method() / cls.method() through the class hierarchy
       (project base classes), Foo() -> Foo.__init__, super().method()
   18. Unresolved calls are kept with a reason code and a note
   19. Resolution coverage (% resolved, reasons for the rest) in the report

Batch 4 (v0.4, roadmap Stage 3: graph building)
   20. Call graph: nodes = functions / methods / classes (+ "<module>" and
       "<main>" scopes), edges = resolved local / internal calls with every
       call-site line and loop depth; external / unresolved calls are counted
       per node
   21. Import graph: nodes = project modules, edges = project-internal imports
       (with line, statement, scope; edges flagged top-level or function-level)
   22. Reverse edges (who calls me / who imports me), shown in the report as
       "Called by" / "Imported by" and available through queries
   23. Export: graph.json (stable schema) plus Mermaid (.mmd) and Graphviz
       (.dot) files for both graphs
   24. Deterministic: everything sorted, no timestamps or absolute paths in
       the exports, so two runs on the same code give identical files
   25. Query a saved graph.json without re-parsing the code (--from-graph)

Batch 5 (v0.5, roadmap Stage 4: analyzers)
   26. Import cycles (SCC on the import graph): import-time / deferred
       (function-level import) / typing-only (`if TYPE_CHECKING:`)
   27. Call cycles (mutual recursion) and recursion: direct self-calls and
       indirect cycles with the shortest cycle length per function
   28. Loop report: nested loops, and calls made inside a loop into code that
       loops or recurses (directly or further down the call chain)
   29. Entry points: __main__ blocks and modules, main(), handler decorators,
       tests / fixtures, names listed in __all__
   30. Dead code candidates: functions, methods and classes nobody calls (and
       code only called by dead code), minus entry points, dunder methods,
       overrides and base classes
   31. Unused imports and imports of project modules that do not exist
   32. Metrics: fan-in, fan-out, most connected, depth of call / import chains
   33. Every finding is labelled certain / likely / uncertain; output goes to
       the report, to analysis.json, and to `--from-graph graph.json --analyze`

Usage:
    python code_mapper.py                 # scan current folder
    python code_mapper.py path/to/project # scan another project
    python code_mapper.py . --quiet       # don't print to console, only write report
    python code_mapper.py . --no-graphs   # skip the graph files
    python code_mapper.py . --query callers pkg.core.Engine.make --depth 2
    python code_mapper.py --from-graph reports/2026-11-15/graphs_22-30-00/graph.json \
        --query imports pkg.core --depth 0

    python code_mapper.py . --min-confidence likely      # hide the uncertain findings
    python code_mapper.py --from-graph reports/2026-11-15/graphs_22-30-00/graph.json --analyze

Query kinds: callers, callees (call graph); importers, imports (import graph).
--depth N follows edges N levels (default 1, 0 = all levels).

Requires Python 3.9+ (uses ast.unparse). No external dependencies.

Planned (not built yet): tests and module split (Stage 5).
"""

import argparse
import ast
import builtins
import json
import os
import re
import sys
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

if sys.version_info < (3, 9):
    sys.exit("code_mapper.py needs Python 3.9 or newer (ast.unparse).")

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
# Folders we never descend into
IGNORE_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", "venv", ".venv", "env", ".env",
    "node_modules", ".idea", ".vscode", ".mypy_cache", ".pytest_cache",
    ".tox", "build", "dist", "site-packages",
}
REPORTS_DIR_NAME = "reports"
# Folder where this script lives; reports are saved here, not in the scanned project
TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
# Only THIS folder is skipped while scanning (a project's own "reports" package is scanned)
OWN_REPORTS_DIR = os.path.normcase(os.path.realpath(os.path.join(TOOL_DIR, REPORTS_DIR_NAME)))

MODULE_SCOPE = "<module>"   # pseudo-function: module-level / class-body code
MAIN_SCOPE = "<main>"       # pseudo-function: `if __name__ == "__main__":` block


# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #
@dataclass
class CallInfo:
    """One function call found inside a scope."""
    name: str                # e.g. "helper" or "self.save" or "os.path.join"
    line: int
    loop_depth: int = 0      # 0 = not inside a loop, 1 = in a loop, 2 = in a nested loop ...
    # --- filled in by Resolver (None = not resolved yet) ---
    status: Optional[str] = None   # "local" | "internal" | "external" | "unresolved"
    target: Optional[str] = None   # fully qualified target, e.g. "pkg.core.Engine.make", "os.path.join"
    reason: Optional[str] = None   # reason code when status == "unresolved"
    note: Optional[str] = None     # extra detail ("stdlib", "builtin", "instantiates Foo", ...)
    instantiates: Optional[str] = None   # full name of the class when the call is `Foo()` (the edge itself goes to its __init__)


@dataclass
class LoopInfo:
    """One for / async for / while statement."""
    kind: str                # "for", "async for" or "while"
    line: int
    depth: int               # 1 = outermost loop of the scope, 2 = loop inside a loop ...


@dataclass
class ImportInfo:
    """One imported name (an `import a, b` statement gives two entries)."""
    kind: str                # "import" or "from"
    module: str              # "os.path"; "" for `from . import x`
    name: Optional[str]      # imported name for "from" imports ("*" = star); None for "import"
    alias: Optional[str]     # the `as ...` name, if any
    level: int               # number of leading dots in a relative import (0 = absolute)
    line: int
    scope: str               # "<module>" or the qualified function/class it sits in
    # --- filled in by Resolver ---
    abs_module: Optional[str] = None   # absolute module this import depends on
    origin: Optional[str] = None       # "internal" | "stdlib" | "third-party" | "external" | "unresolved"
    type_checking: bool = False        # inside `if TYPE_CHECKING:` (never runs at runtime)
    in_try: bool = False               # inside the body of a `try:` (often an optional-dependency probe)

    @property
    def bound_name(self) -> str:
        """The local name this import creates."""
        if self.alias:
            return self.alias
        if self.kind == "import":
            return self.module.split(".")[0]    # `import a.b.c` binds `a`
        return self.name or ""

    def describe(self) -> str:
        if self.kind == "import":
            text = f"import {self.module}"
        else:
            text = f"from {'.' * self.level}{self.module} import {self.name}"
        if self.alias:
            text += f" as {self.alias}"
        return text


@dataclass
class AliasInfo:
    """Module-level `name = some.dotted.reference` (a candidate alias; not verified yet)."""
    name: str
    target: str
    line: int


@dataclass
class FunctionInfo:
    """Everything we know about one function / method (or a pseudo-function)."""
    name: str                     # short name, e.g. "save"
    qualified_name: str           # e.g. "Database.save" or "outer.inner"
    line: int
    is_async: bool = False
    args: List[str] = field(default_factory=list)   # e.g. ["self", "path: str", "retries=3"]
    returns: Optional[str] = None
    docstring: Optional[str] = None
    decorators: List[str] = field(default_factory=list)   # e.g. ["staticmethod", "app.route('/')"]
    enclosing_class: Optional[str] = None   # qualified class name if defined directly in a class
    calls: List[CallInfo] = field(default_factory=list)
    loops: List[LoopInfo] = field(default_factory=list)
    local_names: List[str] = field(default_factory=list)   # names assigned in this scope (variables)


@dataclass
class ClassInfo:
    """One class."""
    name: str
    qualified_name: str           # e.g. "Outer.Inner"
    line: int
    bases: List[str] = field(default_factory=list)        # includes keywords like "metaclass=Meta"
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    methods: List[str] = field(default_factory=list)      # short names of methods defined in it


@dataclass
class ModuleInfo:
    """One .py file."""
    path: str                     # path relative to project root
    module_name: str = ""         # dotted name relative to the scanned root, e.g. "pkg.sub.mod"
    is_package: bool = False      # True for __init__.py
    docstring: Optional[str] = None
    imports: List[ImportInfo] = field(default_factory=list)
    classes: List[ClassInfo] = field(default_factory=list)
    functions: List[FunctionInfo] = field(default_factory=list)
    aliases: List[AliasInfo] = field(default_factory=list)
    module_scope: Optional[FunctionInfo] = None   # "<module>": module-level + class-body code
    main_block: Optional[FunctionInfo] = None     # "<main>": if __name__ == "__main__" body
    error: Optional[str] = None   # set if the file could not be parsed
    used_names: Set[str] = field(default_factory=set)    # every name read anywhere in the file (+ __all__)
    value_refs: Set[str] = field(default_factory=set)    # names / attributes used as values, not as call targets
    exports: Optional[List[str]] = None                  # names in a literal `__all__`, or None
    uses_dynamic_names: bool = False                     # calls globals() / locals() / vars() / eval() / exec()

    def loop_count(self) -> int:
        scopes = list(self.functions) + [s for s in (self.module_scope, self.main_block) if s]
        return sum(len(s.loops) for s in scopes)


# --------------------------------------------------------------------------- #
# Task 1: traverse folders and files
# --------------------------------------------------------------------------- #
def _is_own_reports_dir(path: str) -> bool:
    return os.path.normcase(os.path.realpath(path)) == OWN_REPORTS_DIR


def find_python_files(root: str) -> List[str]:
    """Return sorted relative paths of every .py file under `root`."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        # prune ignored folders in-place so os.walk skips them
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in IGNORE_DIRS and not _is_own_reports_dir(os.path.join(dirpath, d))
        )
        for fname in sorted(filenames):
            if fname.endswith(".py"):
                full = os.path.join(dirpath, fname)
                found.append(os.path.relpath(full, root))
    return found


def module_name_from_path(rel_path: str, root: str) -> Tuple[str, bool]:
    """'pkg/sub/mod.py' -> ('pkg.sub.mod', False);  'pkg/__init__.py' -> ('pkg', True)."""
    parts = rel_path[:-3].split(os.sep)           # drop ".py"
    is_package = parts[-1] == "__init__"
    if is_package:
        parts = parts[:-1]
    root_name = os.path.basename(os.path.normpath(root))
    if os.path.isfile(os.path.join(root, "__init__.py")):
        parts = [root_name] + parts               # the scanned folder is itself a package
    return ".".join(parts) or root_name, is_package


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


def _is_plain_reference(node: ast.AST) -> bool:
    """True for `name` or `a.b.c` (only names and attribute access, no calls)."""
    while isinstance(node, ast.Attribute):
        node = node.value
    return isinstance(node, ast.Name)


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


class _ScopeCollector(ast.NodeVisitor):
    """Collects calls and loops of ONE scope (a function body, or the module level).

    - Bodies of nested defs are NOT entered: they are reported as their own functions.
    - Decorators and default values of nested defs run in THIS scope, so they are collected.
    - Class bodies ARE entered: class-body code runs when the enclosing scope runs.
    - Loop depth is tracked so each call knows how deep inside loops it sits.
    """

    def __init__(self):
        self.calls: List[CallInfo] = []
        self.loops: List[LoopInfo] = []
        self.assigned: Set[str] = set()       # variable names bound in this scope
        self._depth = 0

    def visit_Call(self, node: ast.Call):
        self.calls.append(CallInfo(_dotted_name(node.func), node.lineno, self._depth))
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Store):
            self.assigned.add(node.id)

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        if node.name:
            self.assigned.add(node.name)
        self.generic_visit(node)

    # -- loops ------------------------------------------------------------- #
    def _visit_for(self, node, kind: str):
        self.loops.append(LoopInfo(kind, node.lineno, self._depth + 1))
        self.visit(node.iter)                 # evaluated once, before the loop starts
        self.visit(node.target)
        self._depth += 1
        for stmt in node.body:
            self.visit(stmt)
        self._depth -= 1
        for stmt in node.orelse:              # runs once, after the loop
            self.visit(stmt)

    def visit_For(self, node):
        self._visit_for(node, "for")

    def visit_AsyncFor(self, node):
        self._visit_for(node, "async for")

    def visit_While(self, node):
        self.loops.append(LoopInfo("while", node.lineno, self._depth + 1))
        self._depth += 1
        self.visit(node.test)                 # re-evaluated on every iteration
        for stmt in node.body:
            self.visit(stmt)
        self._depth -= 1
        for stmt in node.orelse:
            self.visit(stmt)

    # -- nested functions: collect only what runs in the current scope ------- #
    def _visit_def(self, node):
        for deco in node.decorator_list:
            self.visit(deco)
        for default in node.args.defaults:
            self.visit(default)
        for default in node.args.kw_defaults:
            if default is not None:
                self.visit(default)

    visit_FunctionDef = _visit_def
    visit_AsyncFunctionDef = _visit_def


class _FunctionExtractor(ast.NodeVisitor):
    """Walks a module and builds FunctionInfo / ClassInfo / ImportInfo for everything in it."""

    def __init__(self):
        self.functions: List[FunctionInfo] = []
        self.classes: List[ClassInfo] = []
        self.imports: List[ImportInfo] = []
        self._scope: List[str] = []       # names of enclosing classes/functions
        self._kinds: List[str] = []       # "class" / "function", parallel to _scope
        self._try_depth = 0               # > 0 while inside the body of a try statement
        self._tc_depth = 0                # > 0 while inside `if TYPE_CHECKING:`

    def _scope_name(self) -> str:
        return ".".join(self._scope) or MODULE_SCOPE

    def _handle_function(self, node, is_async: bool):
        qualified = ".".join(self._scope + [node.name])
        collector = _ScopeCollector()
        for stmt in node.body:
            collector.visit(stmt)

        in_class = bool(self._kinds) and self._kinds[-1] == "class"
        self.functions.append(FunctionInfo(
            name=node.name,
            qualified_name=qualified,
            line=node.lineno,
            is_async=is_async,
            args=_format_args(node.args),
            returns=ast.unparse(node.returns) if node.returns else None,
            docstring=ast.get_docstring(node),
            decorators=[ast.unparse(d) for d in node.decorator_list],
            enclosing_class=".".join(self._scope) if in_class else None,
            calls=collector.calls,
            loops=collector.loops,
            local_names=sorted(collector.assigned),
        ))

        self._scope.append(node.name)
        self._kinds.append("function")
        self.generic_visit(node)          # find nested functions / classes
        self._kinds.pop()
        self._scope.pop()

    def visit_FunctionDef(self, node):
        self._handle_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node):
        self._handle_function(node, is_async=True)

    def visit_ClassDef(self, node):
        qualified = ".".join(self._scope + [node.name])
        bases = [ast.unparse(b) for b in node.bases]
        for kw in node.keywords:               # metaclass=Meta, **opts
            bases.append(f"{kw.arg}={ast.unparse(kw.value)}" if kw.arg else f"**{ast.unparse(kw.value)}")
        info = ClassInfo(
            name=node.name,
            qualified_name=qualified,
            line=node.lineno,
            bases=bases,
            decorators=[ast.unparse(d) for d in node.decorator_list],
            docstring=ast.get_docstring(node),
        )
        self.classes.append(info)

        self._scope.append(node.name)
        self._kinds.append("class")
        self.generic_visit(node)
        self._kinds.pop()
        self._scope.pop()

        info.methods = [f.name for f in self.functions if f.enclosing_class == qualified]

    def visit_Import(self, node: ast.Import):
        scope = self._scope_name()
        for a in node.names:
            self.imports.append(ImportInfo("import", a.name, None, a.asname, 0, node.lineno, scope,
                                           type_checking=self._tc_depth > 0, in_try=self._try_depth > 0))

    def visit_ImportFrom(self, node: ast.ImportFrom):
        scope = self._scope_name()
        for a in node.names:
            self.imports.append(ImportInfo(
                "from", node.module or "", a.name, a.asname, node.level, node.lineno, scope,
                type_checking=self._tc_depth > 0, in_try=self._try_depth > 0))

    def visit_Try(self, node):
        self._try_depth += 1
        for stmt in node.body:
            self.visit(stmt)
        self._try_depth -= 1
        for stmt in node.handlers + node.orelse + node.finalbody:
            self.visit(stmt)

    visit_TryStar = visit_Try

    def visit_If(self, node: ast.If):
        if _is_type_checking(node.test):
            self._tc_depth += 1
            for stmt in node.body:
                self.visit(stmt)
            self._tc_depth -= 1
            for stmt in node.orelse:
                self.visit(stmt)
        else:
            self.generic_visit(node)


def _is_type_checking(test: ast.AST) -> bool:
    """True for `TYPE_CHECKING` / `typing.TYPE_CHECKING`."""
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or \
           (isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")


_DYNAMIC_NAME_CALLS = {"globals", "locals", "vars", "eval", "exec"}


class _NameUsage(ast.NodeVisitor):
    """Which names does a file read? (for unused imports and dead-code hints)

    used        every name read anywhere, plus identifiers inside string annotations
    value_refs  names and attributes read as VALUES, i.e. not as the target of a call
                (`register(handler)`, `@decorator`, `obj.prop`); a function that only appears
                like this is probably used even though no call edge reaches it
    """

    def __init__(self):
        self.used: Set[str] = set()
        self.value_refs: Set[str] = set()
        self.dynamic = False

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, (ast.Load, ast.Del)):
            self.used.add(node.id)
            self.value_refs.add(node.id)

    def visit_Attribute(self, node: ast.Attribute):
        if isinstance(node.ctx, ast.Load):
            self.value_refs.add(node.attr)
        self.visit(node.value)

    def visit_Call(self, node: ast.Call):
        func = node.func
        while isinstance(func, ast.Attribute):          # a.b.c(): only `a` is read, `c` is called
            func = func.value
        if isinstance(func, ast.Name):
            self.used.add(func.id)
            if func is node.func and func.id in _DYNAMIC_NAME_CALLS:
                self.dynamic = True
        else:
            self.visit(func)
        for arg in node.args:
            self.visit(arg)
        for kw in node.keywords:
            self.visit(kw)

    def _annotation(self, node: Optional[ast.AST]):
        if node is None:
            return
        for sub in ast.walk(node):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                self.used.update(_IDENT_RE.findall(sub.value))      # "Foo | None" style string annotations

    def visit_arg(self, node: ast.arg):
        self._annotation(node.annotation)
        self.generic_visit(node)

    def _visit_def(self, node):
        self._annotation(node.returns)
        self.generic_visit(node)

    visit_FunctionDef = _visit_def
    visit_AsyncFunctionDef = _visit_def

    def visit_AnnAssign(self, node: ast.AnnAssign):
        self._annotation(node.annotation)
        self.generic_visit(node)


def _module_exports(body: list) -> Optional[List[str]]:
    """Names listed in a literal module-level `__all__ = [...]` (also `+=`); None if there is none."""
    names: Optional[List[str]] = None
    for stmt in body:
        value, reset = None, False
        if isinstance(stmt, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in stmt.targets):
            value, reset = stmt.value, True
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None and \
                isinstance(stmt.target, ast.Name) and stmt.target.id == "__all__":
            value, reset = stmt.value, True
        elif isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id == "__all__":
            value = stmt.value
        if isinstance(value, (ast.List, ast.Tuple)):
            items = [e.value for e in value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            names = items if (reset or names is None) else names + items
    return sorted(set(names)) if names is not None else None


def _is_main_guard(node: ast.AST) -> bool:
    """True for `if __name__ == "__main__":` (either operand order)."""
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq)):
        return False
    sides = [test.left, test.comparators[0]]
    has_name = any(isinstance(s, ast.Name) and s.id == "__name__" for s in sides)
    has_main = any(isinstance(s, ast.Constant) and s.value == "__main__" for s in sides)
    return has_name and has_main


def _collect_aliases(body: list) -> List[AliasInfo]:
    """Find module-level `x = a.b.c` / `x: T = a.b.c` (not inside defs or classes)."""
    found: List[AliasInfo] = []
    for stmt in body:
        if isinstance(stmt, ast.Assign) and _is_plain_reference(stmt.value):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    found.append(AliasInfo(target.id, _dotted_name(stmt.value), stmt.lineno))
        elif (isinstance(stmt, ast.AnnAssign) and stmt.value is not None
              and isinstance(stmt.target, ast.Name) and _is_plain_reference(stmt.value)):
            found.append(AliasInfo(stmt.target.id, _dotted_name(stmt.value), stmt.lineno))
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        else:                                   # descend into if / try / with / for / while
            for attr in ("body", "orelse", "finalbody"):
                found += _collect_aliases(getattr(stmt, attr, None) or [])
            for handler in getattr(stmt, "handlers", None) or []:
                found += _collect_aliases(handler.body)
    return found


def analyze_module(root: str, rel_path: str) -> ModuleInfo:
    """Parse one file and return its ModuleInfo."""
    module_name, is_package = module_name_from_path(rel_path, root)
    module = ModuleInfo(path=rel_path, module_name=module_name, is_package=is_package)
    full = os.path.join(root, rel_path)
    try:
        with open(full, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=rel_path)
    except (SyntaxError, UnicodeDecodeError, OSError, ValueError) as exc:
        module.error = f"{type(exc).__name__}: {exc}"
        return module

    module.docstring = ast.get_docstring(tree)
    extractor = _FunctionExtractor()
    extractor.visit(tree)
    module.functions = extractor.functions
    module.classes = extractor.classes
    module.imports = extractor.imports
    module.aliases = _collect_aliases(tree.body)
    usage = _NameUsage()
    usage.visit(tree)
    module.exports = _module_exports(tree.body)
    module.used_names = usage.used | set(module.exports or [])
    module.value_refs = usage.value_refs
    module.uses_dynamic_names = usage.dynamic

    # module-level code -> "<module>", `if __name__ == "__main__"` body -> "<main>"
    top = _ScopeCollector()
    main = _ScopeCollector()
    main_line = None
    for stmt in tree.body:
        if _is_main_guard(stmt):
            main_line = main_line or stmt.lineno
            for s in stmt.body:
                main.visit(s)
            for s in stmt.orelse:
                top.visit(s)
        else:
            top.visit(stmt)
    module.module_scope = FunctionInfo(
        name=MODULE_SCOPE, qualified_name=MODULE_SCOPE, line=1, calls=top.calls, loops=top.loops,
        local_names=sorted(top.assigned | main.assigned))
    if main_line is not None:
        module.main_block = FunctionInfo(
            name=MAIN_SCOPE, qualified_name=MAIN_SCOPE, line=main_line,
            calls=main.calls, loops=main.loops)
    return module


def analyze_project(root: str) -> List[ModuleInfo]:
    """Task 1 + 2 + 3 combined: scan the whole project."""
    return [analyze_module(root, p) for p in find_python_files(root)]


# --------------------------------------------------------------------------- #
# Stage 2: symbol table and call resolution
# --------------------------------------------------------------------------- #
# Purely static: no type inference. `x = Foo(); x.run()` stays unresolved
# (reason "variable"); `self.method()` / `cls.method()` is resolved through the
# class hierarchy of the enclosing class.
_STDLIB_NAMES = getattr(sys, "stdlib_module_names", None)     # Python 3.10+ only
_PARAM_RE = re.compile(r"\*{0,2}\s*([A-Za-z_]\w*)")
_IDENT_RE = re.compile(r"[A-Za-z_]\w*")

REASON_HELP = {
    "dynamic": "call on the result of an expression, subscript, lambda or module object",
    "variable": "call or attribute on a parameter / local / module variable (type unknown)",
    "name-not-found": "name is not defined in the module and not imported",
    "star-import": "name may come from a `from X import *` of a non-project module",
    "not-in-module": "name not found in a project module it was imported from",
    "member-not-found": "method not found on the class or its project base classes",
    "external-base": "method may be inherited from a base class outside the project",
    "self-attribute": "attribute of an instance attribute (e.g. self.db.save())",
    "function-attribute": "attribute access on a project function",
    "relative-import": "relative import goes above the scanned folder",
    "cycle": "alias / re-export chain is circular or too deep",
}


def _ext_note(dotted: str) -> str:
    """'builtin' / 'stdlib' / 'third-party' (or 'external' on Python 3.9, which can't tell)."""
    top = dotted.split(".")[0]
    if top == "builtins":
        return "builtin"
    if _STDLIB_NAMES is None:
        return "external"
    return "stdlib" if top in _STDLIB_NAMES else "third-party"


def _param_list(fn: FunctionInfo) -> List[str]:
    """Parameter names in order (annotations / defaults / stars stripped)."""
    names = []
    for a in fn.args:
        match = _PARAM_RE.match(a)
        if match:
            names.append(match.group(1))
    return names


@dataclass
class Symbol:
    """One entry of the project-wide symbol table."""
    full_name: str          # e.g. "pkg.core.Engine.make"
    kind: str               # "function" | "method" | "class"
    module: str             # dotted module name, e.g. "pkg.core"
    qualified_name: str     # name inside the module, e.g. "Engine.make"
    line: int


@dataclass
class _Binding:
    """What a name points to, before it is turned into a call result."""
    kind: str               # "symbol" | "module" | "external" | "unknown"
    target: str = ""
    reason: str = ""        # reason code when kind == "unknown"
    note: str = ""


@dataclass
class ResolutionStats:
    total: int = 0
    by_status: Counter = field(default_factory=Counter)
    by_reason: Counter = field(default_factory=Counter)
    external_kinds: Counter = field(default_factory=Counter)

    def add(self, call: CallInfo):
        self.total += 1
        self.by_status[call.status] += 1
        if call.status == "unresolved":
            self.by_reason[call.reason or "unknown"] += 1
        elif call.status == "external":
            self.external_kinds[call.note or "external"] += 1

    def resolved(self) -> int:
        return self.by_status["local"] + self.by_status["internal"] + self.by_status["external"]

    def percent(self) -> float:
        return 100.0 * self.resolved() / self.total if self.total else 100.0


class Resolver:
    """Builds the symbol table and resolves every call of every module (in place)."""

    MAX_DEPTH = 10      # guard against circular aliases / re-exports

    def __init__(self, modules: List[ModuleInfo]):
        self.modules = [m for m in modules if not m.error]
        self.mod_by_name: Dict[str, ModuleInfo] = {}
        self.duplicate_modules: List[Tuple[str, str]] = []     # (module name, path of the ignored file)
        self.symbols: Dict[str, Symbol] = {}
        self.stats = ResolutionStats()
        self._fn_index: Dict[Tuple[str, str], FunctionInfo] = {}
        self._classes: Dict[str, ClassInfo] = {}
        self._imports: Dict[Tuple[str, str], Dict[str, ImportInfo]] = {}   # (module, scope) -> bound name -> import
        self._stars: Dict[str, List[ImportInfo]] = {}
        self._aliases: Dict[Tuple[str, str], AliasInfo] = {}
        self._module_vars: Dict[str, Set[str]] = {}
        self._prefixes: Set[str] = set()       # every module name and every parent package name
        self._bases_cache: Dict[str, List[Tuple[str, str]]] = {}
        self._instantiated: Optional[str] = None     # set while resolving a `Foo()` call (see resolve_all)
        self._build()

    # -- 2.1 symbol table ----------------------------------------------------- #
    def _build(self):
        for m in self.modules:
            if m.module_name in self.mod_by_name:
                self.duplicate_modules.append((m.module_name, m.path))
                continue
            self.mod_by_name[m.module_name] = m
        for name, m in self.mod_by_name.items():
            parts = name.split(".")
            for i in range(1, len(parts) + 1):
                self._prefixes.add(".".join(parts[:i]))
            for fn in m.functions:
                full = f"{name}.{fn.qualified_name}"
                kind = "method" if fn.enclosing_class else "function"
                self.symbols.setdefault(full, Symbol(full, kind, name, fn.qualified_name, fn.line))
                self._fn_index[(name, fn.qualified_name)] = fn
            for c in m.classes:
                full = f"{name}.{c.qualified_name}"
                self.symbols[full] = Symbol(full, "class", name, c.qualified_name, c.line)
                self._classes[full] = c
            for imp in m.imports:
                if imp.bound_name == "*":
                    if imp.scope == MODULE_SCOPE:
                        self._stars.setdefault(name, []).append(imp)
                else:
                    self._imports.setdefault((name, imp.scope), {})[imp.bound_name] = imp
            for al in m.aliases:
                self._aliases[(name, al.name)] = al
            self._module_vars[name] = set(m.module_scope.local_names) if m.module_scope else set()

    # -- 2.2 imports -------------------------------------------------------------- #
    def _abs_from_module(self, m: ModuleInfo, imp: ImportInfo) -> Tuple[Optional[str], bool]:
        """Absolute module name of an import. Returns (name, ok); ok=False = relative import too deep."""
        if imp.level == 0:
            return imp.module, True
        parts = m.module_name.split(".")
        base = parts if m.is_package else parts[:-1]
        up = imp.level - 1
        if up > len(base):
            return None, False
        base = base[:len(base) - up]
        if imp.module:
            base = base + imp.module.split(".")
        return ".".join(base), True

    def _module_binding(self, dotted: str) -> _Binding:
        if dotted in self._prefixes:
            return _Binding("module", dotted)
        if dotted.split(".")[0] in self._prefixes:        # looks like project code, but no such module
            return _Binding("unknown", reason="not-in-module", note=f"module `{dotted}` not found in the project")
        return _Binding("external", dotted, note=_ext_note(dotted))

    def _pkg_attr(self, m: ModuleInfo, abs_mod: str, name: str, sub: str, depth: int) -> Optional[_Binding]:
        """`from abs_mod import name` where `name` is defined in (or re-exported by) a project module.

        Importing from the module itself (`from . import x` inside __init__.py) means a submodule, so skip.
        """
        if abs_mod not in self.mod_by_name or abs_mod == m.module_name:
            return None
        found = self.resolve_in_module(abs_mod, name, depth + 1)
        if found is not None and found.kind == "unknown" and found.reason == "cycle" and sub in self._prefixes:
            return None
        return found

    def _bind_import(self, m: ModuleInfo, imp: ImportInfo, depth: int) -> _Binding:
        """What the local name created by `imp` points to."""
        if imp.kind == "import":
            dotted = imp.module if imp.alias else imp.module.split(".")[0]
            return self._module_binding(dotted)
        abs_mod, ok = self._abs_from_module(m, imp)
        if not ok:
            return _Binding("unknown", reason="relative-import",
                            note=f"`{imp.describe()}` goes above the scanned folder")
        name = imp.name or ""
        sub = f"{abs_mod}.{name}" if abs_mod else name
        found = self._pkg_attr(m, abs_mod, name, sub, depth)
        if found is not None:
            return found
        if sub in self._prefixes:                       # `from pkg import submodule`
            return _Binding("module", sub)
        if abs_mod in self._prefixes or not abs_mod:
            return _Binding("unknown", reason="not-in-module",
                            note=f"`{name}` not found in project module `{abs_mod or '.'}`")
        if imp.level > 0 or abs_mod.split(".")[0] in self._prefixes:
            return _Binding("unknown", reason="not-in-module",
                            note=f"module `{abs_mod}` not found in the project")
        return _Binding("external", sub, note=_ext_note(sub))

    def resolve_in_module(self, modname: str, name: str, depth: int = 0) -> Optional[_Binding]:
        """Look `name` up at module level of a project module (defs, aliases, re-exports, star imports)."""
        if depth > self.MAX_DEPTH:
            return _Binding("unknown", reason="cycle", note=f"`{modname}.{name}`: circular alias or re-export")
        m = self.mod_by_name.get(modname)
        if m is None:
            return None
        full = f"{modname}.{name}"
        if full in self.symbols:
            return _Binding("symbol", full)
        alias = self._aliases.get((modname, name))
        if alias is not None:
            return self._walk(m, None, alias.target.split("."), depth + 1)
        imp = self._imports.get((modname, MODULE_SCOPE), {}).get(name)
        if imp is not None:
            return self._bind_import(m, imp, depth + 1)
        if name in self._module_vars.get(modname, ()):
            return _Binding("unknown", reason="variable",
                            note=f"`{name}` is a module-level variable of `{modname}` (type unknown)")
        for star in self._stars.get(modname, []):
            abs_mod, ok = self._abs_from_module(m, star)
            if ok and abs_mod in self.mod_by_name:
                found = self.resolve_in_module(abs_mod, name, depth + 1)
                if found is not None and found.kind != "unknown":
                    return found
        return None

    # -- names inside a scope ------------------------------------------------------ #
    def _scope_chain(self, m: ModuleInfo, fn: Optional[FunctionInfo]) -> List[FunctionInfo]:
        """fn and the functions it is nested in, innermost first (class scopes are skipped, like Python)."""
        if fn is None or fn.qualified_name in (MODULE_SCOPE, MAIN_SCOPE):
            return []
        parts = fn.qualified_name.split(".")
        chain = [fn]
        for i in range(len(parts) - 1, 0, -1):
            outer = self._fn_index.get((m.module_name, ".".join(parts[:i])))
            if outer is not None:
                chain.append(outer)
        return chain

    def _lookup_head(self, m: ModuleInfo, fn: Optional[FunctionInfo], name: str, depth: int) -> _Binding:
        for f in self._scope_chain(m, fn):
            imp = self._imports.get((m.module_name, f.qualified_name), {}).get(name)
            if imp is not None:
                return self._bind_import(m, imp, depth + 1)
            nested = f"{m.module_name}.{f.qualified_name}.{name}"
            if nested in self.symbols:
                return _Binding("symbol", nested)
            if name in _param_list(f) or name in f.local_names:
                return _Binding("unknown", reason="variable",
                                note=f"`{name}` is a parameter or local variable (type unknown)")
        found = self.resolve_in_module(m.module_name, name, depth + 1)
        if found is not None:
            return found
        if name in self._module_vars.get(m.module_name, ()):
            return _Binding("unknown", reason="variable",
                            note=f"`{name}` is a module-level variable (type unknown)")
        if hasattr(builtins, name):
            return _Binding("external", f"builtins.{name}", note="builtin")
        if self._stars.get(m.module_name):
            return _Binding("unknown", reason="star-import",
                            note=f"`{name}` may come from a star import of a non-project module")
        return _Binding("unknown", reason="name-not-found",
                        note=f"`{name}` is not defined in this module and not imported")

    def _walk(self, m: ModuleInfo, fn: Optional[FunctionInfo], parts: List[str], depth: int) -> _Binding:
        """Binding for a dotted chain of names: a.b.c"""
        b = self._lookup_head(m, fn, parts[0], depth)
        for part in parts[1:]:
            if b.kind == "unknown":
                break
            b = self._attr(b, part, depth)
        return b

    def _attr(self, b: _Binding, part: str, depth: int) -> _Binding:
        """Binding of `<b>.<part>`."""
        if b.kind == "module":
            if b.target in self.mod_by_name:
                found = self.resolve_in_module(b.target, part, depth + 1)
                if found is not None:
                    return found
            sub = f"{b.target}.{part}"
            if sub in self._prefixes:
                return _Binding("module", sub)
            return _Binding("unknown", reason="not-in-module",
                            note=f"`{part}` not found in project module `{b.target}`")
        if b.kind == "external":
            return _Binding("external", f"{b.target}.{part}", note=b.note)
        if b.kind == "symbol":
            sym = self.symbols[b.target]
            if sym.kind == "class":
                member = self.find_member(b.target, part)
                if member is not None:
                    owner = member.rsplit(".", 1)[0]
                    return _Binding("symbol", member, note=f"inherited from {owner}" if owner != b.target else "")
                if self._has_unknown_base(b.target, {b.target}):
                    return _Binding("unknown", reason="external-base",
                                    note=f"`{part}` not in {b.target}; may come from a base class outside the project")
                return _Binding("unknown", reason="member-not-found",
                                note=f"`{part}` not found on {b.target} or its project base classes")
            return _Binding("unknown", reason="function-attribute",
                            note=f"attribute `{part}` of function `{b.target}`")
        return b

    # -- 2.5 / 2.6 classes ---------------------------------------------------------- #
    def _class_bases(self, cls_full: str) -> List[Tuple[str, str]]:
        """Base classes in order: ("project", full) | ("external", dotted) | ("unknown", text)."""
        if cls_full in self._bases_cache:
            return self._bases_cache[cls_full]
        self._bases_cache[cls_full] = []          # recursion guard
        m = self.mod_by_name[self.symbols[cls_full].module]
        out: List[Tuple[str, str]] = []
        for text in self._classes[cls_full].bases:
            if "=" in text or text.startswith("**"):      # metaclass=..., **opts
                continue
            text = re.sub(r"\[.*\]$", "", text)          # Generic[T] -> Generic
            if text == "object":
                continue
            parts = text.split(".")
            if not all(_IDENT_RE.fullmatch(p) for p in parts):
                out.append(("unknown", text))
                continue
            b = self._walk(m, None, parts, 0)
            if b.kind == "symbol" and self.symbols[b.target].kind == "class":
                out.append(("project", b.target))
            elif b.kind == "external":
                out.append(("external", b.target))
            else:
                out.append(("unknown", text))
        self._bases_cache[cls_full] = out
        return out

    def _has_unknown_base(self, cls_full: str, seen: Set[str]) -> bool:
        for kind, ref in self._class_bases(cls_full):
            if kind != "project":
                return True
            if ref not in seen:
                seen.add(ref)
                if self._has_unknown_base(ref, seen):
                    return True
        return False

    def find_member(self, cls_full: str, name: str, _seen: Optional[Set[str]] = None) -> Optional[str]:
        """Full name of method/nested class `name` on a class or its project bases (depth-first, left to right)."""
        seen = _seen if _seen is not None else set()
        if cls_full in seen:
            return None
        seen.add(cls_full)
        candidate = f"{cls_full}.{name}"
        if candidate in self.symbols:
            return candidate
        for kind, ref in self._class_bases(cls_full):
            if kind == "project":
                found = self.find_member(ref, name, seen)
                if found is not None:
                    return found
        return None

    def _enclosing_class(self, m: ModuleInfo, fn: Optional[FunctionInfo]) -> Tuple[Optional[str], Set[str]]:
        """Class whose method `fn` is (or is nested in), plus the names that mean 'this object' (self / cls)."""
        for f in self._scope_chain(m, fn):
            if f.enclosing_class:
                cls_full = f"{m.module_name}.{f.enclosing_class}"
                if cls_full not in self.symbols:
                    continue
                receivers = {"self", "cls"}
                params = _param_list(f)
                if params and "staticmethod" not in f.decorators:
                    receivers.add(params[0])
                return cls_full, receivers
        return None, set()

    # -- turning bindings into call results ---------------------------------------------- #
    def _binding_to_result(self, m: ModuleInfo, b: _Binding) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
        """-> (status, target, reason, note)"""
        if b.kind == "symbol":
            sym = self.symbols[b.target]
            target, note = b.target, b.note
            if sym.kind == "class":                       # Foo()  ->  Foo.__init__
                self._instantiated = b.target
                init = self.find_member(b.target, "__init__")
                if init is not None:
                    target, note = init, f"instantiates {sym.qualified_name}"
                else:
                    note = f"instantiates {sym.qualified_name} (no __init__ in project)"
            status = "local" if self.symbols[target].module == m.module_name else "internal"
            return status, target, None, note or None
        if b.kind == "external":
            return "external", b.target, None, b.note or None
        if b.kind == "module":
            return "unresolved", None, "dynamic", f"`{b.target}` is a module, not a callable"
        return "unresolved", None, b.reason or "name-not-found", b.note or None

    def _resolve_super(self, m: ModuleInfo, fn: FunctionInfo, method: str):
        cls_full, _ = self._enclosing_class(m, fn)
        if cls_full is None:
            return "unresolved", None, "dynamic", "super() used outside a method"
        first_external = None
        has_unknown = False
        for kind, ref in self._class_bases(cls_full):
            if kind == "project":
                found = self.find_member(ref, method)
                if found is not None:
                    return self._binding_to_result(m, _Binding("symbol", found, note="via super()"))
            elif kind == "external":
                first_external = first_external or ref
            else:
                has_unknown = True
        if first_external:
            return "external", f"{first_external}.{method}", None, f"{_ext_note(first_external)}, via super()"
        if has_unknown:
            return "unresolved", None, "external-base", f"`super().{method}` not found in project base classes"
        return "external", f"builtins.object.{method}", None, "builtin, via super()"

    def _resolve_self(self, m: ModuleInfo, cls_full: str, parts: List[str]):
        if len(parts) == 1:
            if parts[0] == "cls":                                   # cls(...) builds the class itself
                return self._binding_to_result(m, _Binding("symbol", cls_full))
            return "unresolved", None, "dynamic", f"`{parts[0]}` called like a function (__call__ not tracked)"
        b = _Binding("symbol", cls_full)
        for idx, part in enumerate(parts[1:], start=1):
            b = self._attr(b, part, 0)
            if b.kind == "unknown":
                if idx == 1 and len(parts) > 2:
                    return ("unresolved", None, "self-attribute",
                            f"`{parts[0]}.{parts[1]}` is not a method of {cls_full}; "
                            f"it is an instance attribute or comes from outside the project")
                break
        return self._binding_to_result(m, b)

    def _resolve(self, m: ModuleInfo, fn: FunctionInfo, name: str):
        parts = name.split(".")
        if len(parts) == 2 and parts[0] == "super()":
            return self._resolve_super(m, fn, parts[1])

        odd = [i for i, p in enumerate(parts) if "(" in p or "[" in p or p == "<expr>"]
        if odd:
            i = odd[0]
            # Foo().method / pkg.Foo().method : the object is a fresh instance of a known class
            if (len(odd) == 1 and i == len(parts) - 2 and re.fullmatch(r"[A-Za-z_]\w*\(\)", parts[i])):
                b = self._walk(m, fn, parts[:i] + [parts[i][:-2]], 0)
                if b.kind == "symbol" and self.symbols[b.target].kind == "class":
                    return self._binding_to_result(m, self._attr(b, parts[-1], 0))
            return "unresolved", None, "dynamic", "call on the result of an expression, subscript or call"

        cls_full, receivers = self._enclosing_class(m, fn)
        if cls_full is not None and parts[0] in receivers:
            return self._resolve_self(m, cls_full, parts)

        return self._binding_to_result(m, self._walk(m, fn, parts, 0))

    # -- public --------------------------------------------------------------------------- #
    def _annotate_imports(self, m: ModuleInfo):
        for imp in m.imports:
            abs_mod, ok = self._abs_from_module(m, imp)
            if not ok:
                imp.abs_module, imp.origin = None, "unresolved"
                continue
            target = abs_mod or ""
            if imp.kind == "from" and imp.name != "*":
                sub = f"{abs_mod}.{imp.name}" if abs_mod else (imp.name or "")
                if sub in self.mod_by_name:
                    found = self._pkg_attr(m, abs_mod, imp.name or "", sub, 0)
                    if found is None:
                        target = sub                   # `from pkg import submodule`
                    elif found.kind == "module" and found.target in self.mod_by_name:
                        target = found.target          # name is a module (e.g. via a star-import chain)
            imp.abs_module = target or None
            if target in self._prefixes:
                imp.origin = "internal"
            elif target and (imp.level > 0 or target.split(".")[0] in self._prefixes):
                imp.origin = "unresolved"              # points into the project, but no such module
            elif target:
                imp.origin = _ext_note(target)
            else:
                imp.origin = "unresolved"

    def resolve_all(self) -> ResolutionStats:
        """Resolve every call in every module (fills CallInfo / ImportInfo fields in place)."""
        self.stats = ResolutionStats()
        for m in self.modules:
            self._annotate_imports(m)
            scopes = list(m.functions)
            if m.module_scope:
                scopes.append(m.module_scope)
            if m.main_block:
                scopes.append(m.main_block)
            for fn in scopes:
                for call in fn.calls:
                    self._instantiated = None
                    call.status, call.target, call.reason, call.note = self._resolve(m, fn, call.name)
                    call.instantiates = self._instantiated
                    self.stats.add(call)
        return self.stats


def resolve_project(modules: List[ModuleInfo]) -> Resolver:
    """Stage 2: build the symbol table and resolve all calls."""
    resolver = Resolver(modules)
    resolver.resolve_all()
    return resolver


# --------------------------------------------------------------------------- #
# Stage 3: graph building
# --------------------------------------------------------------------------- #
# Two graphs, kept as plain data (no AST objects) so they can be saved as JSON
# and queried later without parsing the code again:
#   call graph    nodes = functions / methods / classes (+ "<module>" / "<main>" scopes)
#                 edges = resolved local / internal calls, with every call site
#   import graph  nodes = project modules, edges = project-internal imports
# Everything is sorted and the JSON holds no timestamps or absolute paths, so
# two runs on the same code give byte-identical files.
TOOL_VERSION = "0.5"
GRAPH_SCHEMA_VERSION = 1
MERMAID_EDGE_WARN = 500          # Mermaid refuses to draw more edges than this by default
REPORT_EDGE_LIMIT = 20           # max "Called by" / "Imported by" entries listed per item in the report

QUERY_KINDS = {                  # query name -> (graph, direction)
    "callers": ("call", "in"),
    "callees": ("call", "out"),
    "importers": ("import", "in"),
    "imports": ("import", "out"),
}


def _rel(path: str) -> str:
    """Path with forward slashes, so exports are identical on every OS."""
    return path.replace(os.sep, "/")


def _mermaid_text(text: str) -> str:
    return text.replace('"', "#quot;").replace("<", "#lt;").replace(">", "#gt;")


def _dot_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


class Graph:
    """A directed graph stored as plain dicts (JSON friendly).

    nodes: id -> attribute dict
    edges: (src, dst) -> {"src", "dst", "sites": [...], "count", flag}
           flag is "in_loop" for call graphs, "top_level" for import graphs
    Reverse edges (predecessors) come from the same data, so "who calls me" needs no extra storage.
    """

    def __init__(self, kind: str):
        self.kind = kind                      # "call" | "import"
        self.nodes: Dict[str, dict] = {}
        self.edges: Dict[Tuple[str, str], dict] = {}
        self._out: Dict[str, List[str]] = {}
        self._in: Dict[str, List[str]] = {}
        self._indexed = False

    # -- building ------------------------------------------------------------ #
    def add_node(self, node_id: str, **attrs):
        self.nodes[node_id] = attrs
        self._indexed = False

    def add_edge(self, src: str, dst: str, site: dict):
        edge = self.edges.setdefault((src, dst), {"src": src, "dst": dst, "sites": []})
        edge["sites"].append(site)
        self._indexed = False

    def finalize(self):
        """Sort call / import sites and compute counts and flags (3.5: deterministic)."""
        for edge in self.edges.values():
            edge["sites"].sort(key=lambda s: (s["line"], json.dumps(s, sort_keys=True)))
            edge["count"] = len(edge["sites"])
            if self.kind == "call":
                edge["in_loop"] = any(s.get("loop_depth", 0) > 0 for s in edge["sites"])
            else:
                edge["top_level"] = any(s.get("scope") == MODULE_SCOPE for s in edge["sites"])
        self._indexed = False

    # -- queries (forward and reverse) ---------------------------------------- #
    def _index(self):
        if self._indexed:
            return
        out: Dict[str, List[str]] = {n: [] for n in self.nodes}
        inn: Dict[str, List[str]] = {n: [] for n in self.nodes}
        for src, dst in sorted(self.edges):
            out.setdefault(src, []).append(dst)
            inn.setdefault(dst, []).append(src)
        self._out, self._in, self._indexed = out, inn, True

    def successors(self, node_id: str) -> List[str]:
        """Direct targets (callees / imported modules), sorted."""
        self._index()
        return list(self._out.get(node_id, []))

    def predecessors(self, node_id: str) -> List[str]:
        """Direct sources (callers / importers), sorted."""
        self._index()
        return list(self._in.get(node_id, []))

    def edge(self, src: str, dst: str) -> Optional[dict]:
        return self.edges.get((src, dst))

    def reach(self, start: str, direction: str = "out", depth: int = 1) -> List[Tuple[int, str]]:
        """Breadth-first walk: [(level, node)], sorted inside each level. depth <= 0 means no limit.

        The start node is not listed, even when it can reach itself through a cycle.
        """
        step = self.successors if direction == "out" else self.predecessors
        seen = {start}
        frontier = [start]
        found: List[Tuple[int, str]] = []
        level = 0
        while frontier and (depth <= 0 or level < depth):
            level += 1
            nxt = set()
            for node in frontier:
                for other in step(node):
                    if other not in seen:
                        nxt.add(other)
            seen |= nxt
            frontier = sorted(nxt)
            found += [(level, n) for n in frontier]
        return found

    def find(self, text: str) -> List[str]:
        """Node ids matching `text`: exact id, else ids ending in `.text`, else ids containing it."""
        if text in self.nodes:
            return [text]
        suffix = sorted(n for n in self.nodes if n.endswith("." + text))
        if suffix:
            return suffix
        return sorted(n for n in self.nodes if text in n)

    # -- export --------------------------------------------------------------- #
    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "nodes": [dict(attrs, id=n) for n, attrs in sorted(self.nodes.items())],
            "edges": [self.edges[k] for k in sorted(self.edges)],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Graph":
        g = cls(data["kind"])
        for node in data["nodes"]:
            attrs = dict(node)
            g.nodes[attrs.pop("id")] = attrs
        for edge in data["edges"]:
            g.edges[(edge["src"], edge["dst"])] = edge
        return g

    def _drawn_nodes(self) -> List[str]:
        """Diagrams only show nodes that have at least one edge (isolated ones are in graph.json)."""
        self._index()
        return sorted(n for n in self.nodes if self._out.get(n) or self._in.get(n))

    def _edge_style(self, edge: dict) -> str:
        """'bold' (call inside a loop), 'dashed' (import inside a function) or ''."""
        if self.kind == "call" and edge.get("in_loop"):
            return "bold"
        if self.kind == "import" and not edge.get("top_level", True):
            return "dashed"
        return ""

    def to_mermaid(self) -> str:
        ids = self._drawn_nodes()
        alias = {n: f"n{i}" for i, n in enumerate(ids)}
        legend = "thick arrow = call inside a loop" if self.kind == "call" else "dotted arrow = import inside a function"
        lines = [f"%% {self.kind} graph: {len(ids)} connected nodes, {len(self.edges)} edges; {legend}; xN = N sites"]
        if len(self.edges) > MERMAID_EDGE_WARN:
            lines.append(f"%% more than {MERMAID_EDGE_WARN} edges: Mermaid may refuse to render this, use the .dot file or --query")
        lines.append("flowchart LR")
        for n in ids:
            lines.append(f'    {alias[n]}["{_mermaid_text(n)}"]')
        for key in sorted(self.edges):
            edge = self.edges[key]
            style = self._edge_style(edge)
            arrow = {"bold": "==>", "dashed": "-.->"}.get(style, "-->")
            label = f"|x{edge['count']}|" if edge.get("count", 1) > 1 else ""
            lines.append(f"    {alias[key[0]]} {arrow}{label} {alias[key[1]]}")
        return "\n".join(lines) + "\n"

    def to_dot(self) -> str:
        ids = self._drawn_nodes()
        lines = [
            f"// {self.kind} graph: {len(ids)} connected nodes, {len(self.edges)} edges",
            f"digraph {self.kind}_graph {{",
            "    rankdir=LR;",
            '    node [shape=box, fontname="Helvetica"];',
        ]
        for n in ids:
            lines.append(f'    "{_dot_text(n)}";')
        for key in sorted(self.edges):
            edge = self.edges[key]
            attrs = []
            if edge.get("count", 1) > 1:
                attrs.append(f'label="x{edge["count"]}"')
            style = self._edge_style(edge)
            if style:
                attrs.append(f"style={style}")
            suffix = f" [{', '.join(attrs)}]" if attrs else ""
            lines.append(f'    "{_dot_text(key[0])}" -> "{_dot_text(key[1])}"{suffix};')
        lines.append("}")
        return "\n".join(lines) + "\n"


# -- 3.1 call graph ----------------------------------------------------------------- #
def build_call_graph(resolver: "Resolver") -> Graph:
    """Nodes: every symbol (function / method / class) plus the <module> / <main> scopes that make calls.
    Edges: every call resolved as local or internal, with each call site.
    External and unresolved calls are not edges; they are counted on the calling node.
    """
    g = Graph("call")
    mods = [resolver.mod_by_name[n] for n in sorted(resolver.mod_by_name)]

    # Hints for the Stage 4 dead-code analyzer (they only exist as node attributes, so a saved graph.json is enough)
    value_refs: Set[str] = set()
    unresolved_tails: Counter = Counter()
    exported_ids: Set[str] = set()                    # symbols named in some __all__ (also re-exports)
    for m in mods:
        for name in m.exports or []:
            b = resolver.resolve_in_module(m.module_name, name)
            exported_ids.add(b.target if b is not None and b.kind == "symbol" else f"{m.module_name}.{name}")
    for m in mods:
        value_refs |= m.value_refs
        for fn in list(m.functions) + [s for s in (m.module_scope, m.main_block) if s is not None]:
            for c in fn.calls:
                if c.status == "unresolved":
                    unresolved_tails[c.name.rsplit(".", 1)[-1]] += 1

    for full in sorted(resolver.symbols):
        sym = resolver.symbols[full]
        m = resolver.mod_by_name[sym.module]
        attrs = {"kind": sym.kind, "module": sym.module, "qualified_name": sym.qualified_name,
                 "path": _rel(m.path), "line": sym.line}
        if sym.kind == "class":
            attrs["bases"] = list(resolver._classes[full].bases)
            attrs["decorators"] = list(resolver._classes[full].decorators)
        else:
            fn = resolver._fn_index[(sym.module, sym.qualified_name)]
            attrs.update(is_async=fn.is_async, decorators=list(fn.decorators), loops=len(fn.loops),
                         max_loop_depth=max((lp.depth for lp in fn.loops), default=0),
                         external_calls={}, unresolved_calls=0)
        short = sym.qualified_name.rsplit(".", 1)[-1]
        if not (short.startswith("__") and short.endswith("__")):
            if short in value_refs:
                attrs["referenced_as_value"] = True
            if unresolved_tails.get(short):
                attrs["unresolved_name_hits"] = unresolved_tails[short]
        if full in exported_ids:
            attrs["exported"] = True
        g.add_node(full, **attrs)

    for m in mods:
        for scope, kind in ((m.module_scope, "module-scope"), (m.main_block, "main-scope")):
            if scope is not None and scope.calls:
                g.add_node(f"{m.module_name}.{scope.qualified_name}", kind=kind, module=m.module_name,
                           qualified_name=scope.qualified_name, path=_rel(m.path), line=scope.line,
                           loops=len(scope.loops), max_loop_depth=max((lp.depth for lp in scope.loops), default=0),
                           external_calls={}, unresolved_calls=0)

    instantiated_from: Dict[str, Set[str]] = defaultdict(set)    # class -> callers of `Foo()` (edges go to __init__)
    for m in mods:
        scopes = list(m.functions) + [s for s in (m.module_scope, m.main_block) if s is not None]
        for fn in scopes:
            caller = f"{m.module_name}.{fn.qualified_name}"
            node = g.nodes.get(caller)
            if node is None:
                continue
            node.setdefault("external_calls", {})
            node.setdefault("unresolved_calls", 0)
            for c in fn.calls:
                if c.instantiates and c.status in ("local", "internal") and c.instantiates in g.nodes:
                    instantiated_from[c.instantiates].add(caller)
                if c.status in ("local", "internal") and c.target in g.nodes:
                    site = {"line": c.line, "name": c.name, "loop_depth": c.loop_depth}
                    if c.note:
                        site["note"] = c.note
                    g.add_edge(caller, c.target, site)
                elif c.status == "external":
                    key = c.target or c.name
                    node["external_calls"][key] = node["external_calls"].get(key, 0) + 1
                elif c.status == "unresolved":
                    node["unresolved_calls"] += 1
    for cls_id, callers in instantiated_from.items():
        g.nodes[cls_id]["instantiated_from"] = sorted(callers)
    g.finalize()
    return g


# -- 3.2 import graph ------------------------------------------------------------------ #
def build_import_graph(resolver: "Resolver") -> Graph:
    """Nodes: project modules. Edges: imports that point at another project module.

    `import a.b.c` is an edge to a.b.c only (the parent packages that Python also runs are not added).
    An import that only names a folder without __init__.py (namespace package) has no node, so no edge.
    """
    g = Graph("import")
    mods = [resolver.mod_by_name[n] for n in sorted(resolver.mod_by_name)]
    for m in mods:
        g.add_node(m.module_name, kind="package" if m.is_package else "module", path=_rel(m.path))
    for m in mods:
        for imp in m.imports:
            dst = imp.abs_module
            if imp.origin == "internal" and dst in g.nodes and dst != m.module_name:
                site = {"line": imp.line, "statement": imp.describe(), "scope": imp.scope}
                if imp.type_checking:
                    site["type_checking"] = True
                g.add_edge(m.module_name, dst, site)
    g.finalize()
    return g


def build_graphs(resolver: "Resolver") -> Dict[str, Graph]:
    return {"call": build_call_graph(resolver), "import": build_import_graph(resolver)}


# -- 3.4 export / load ------------------------------------------------------------------- #
def graphs_to_dict(graphs: Dict[str, Graph], project_name: str,
                   import_issues: Optional[List[dict]] = None) -> dict:
    data = {
        "schema_version": GRAPH_SCHEMA_VERSION,
        "tool": "code_mapper",
        "tool_version": TOOL_VERSION,
        "project": project_name,
        "stats": {
            "call_graph": {"nodes": len(graphs["call"].nodes), "edges": len(graphs["call"].edges)},
            "import_graph": {"nodes": len(graphs["import"].nodes), "edges": len(graphs["import"].edges)},
        },
        "call_graph": graphs["call"].to_dict(),
        "import_graph": graphs["import"].to_dict(),
    }
    if import_issues is not None:          # unused imports / missing modules (needed by --from-graph --analyze)
        data["import_issues"] = import_issues
    return data


def write_graphs(graphs: Dict[str, Graph], project_name: str, out_dir: str,
                 import_issues: Optional[List[dict]] = None, analysis: Optional[dict] = None) -> List[str]:
    """Write graph.json, the Mermaid (.mmd) / Graphviz (.dot) files and, if given, analysis.json. Returns the paths."""
    os.makedirs(out_dir, exist_ok=True)
    files = {
        "graph.json": json.dumps(graphs_to_dict(graphs, project_name, import_issues), indent=2, sort_keys=True,
                                 ensure_ascii=False) + "\n",
        "call_graph.mmd": graphs["call"].to_mermaid(),
        "call_graph.dot": graphs["call"].to_dot(),
        "import_graph.mmd": graphs["import"].to_mermaid(),
        "import_graph.dot": graphs["import"].to_dot(),
    }
    if analysis is not None:
        files["analysis.json"] = json.dumps(analysis, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    paths = []
    for name, text in files.items():
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:     # fixed newline = same bytes on every OS
            f.write(text)
        paths.append(path)
    return paths


def _read_graph_data(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    version = data.get("schema_version")
    if version != GRAPH_SCHEMA_VERSION:
        raise ValueError(f"unsupported graph schema_version {version!r} (this tool reads {GRAPH_SCHEMA_VERSION})")
    return data


def load_graphs(path: str) -> Dict[str, Graph]:
    """Load graph.json written by write_graphs (no code parsing needed)."""
    data = _read_graph_data(path)
    return {"call": Graph.from_dict(data["call_graph"]), "import": Graph.from_dict(data["import_graph"])}


def load_tool_version(path: str) -> str:
    """Version of code_mapper that wrote this graph.json."""
    return str(_read_graph_data(path).get("tool_version", "0.0"))


def load_import_issues(path: str) -> Optional[List[dict]]:
    """The unused / missing import findings saved in graph.json (None for files written before v0.5)."""
    return _read_graph_data(path).get("import_issues")


def run_query(graphs: Dict[str, Graph], kind: str, text: str, depth: int) -> int:
    """Print the result of a callers / callees / importers / imports query."""
    graph_name, direction = QUERY_KINDS[kind]
    graph = graphs[graph_name]
    matches = graph.find(text)
    if not matches:
        print(f"No {graph_name}-graph node matches '{text}'.", file=sys.stderr)
        return 1
    if len(matches) > 1:
        print(f"'{text}' matches {len(matches)} nodes, be more specific:", file=sys.stderr)
        for n in matches[:20]:
            print(f"  {n}", file=sys.stderr)
        if len(matches) > 20:
            print(f"  ... and {len(matches) - 20} more", file=sys.stderr)
        return 1
    start = matches[0]
    found = graph.reach(start, direction, depth)
    span = "all levels" if depth <= 0 else f"depth {depth}"
    print(f"{kind} of {start} ({span}): {len(found)} found")
    for level, node in found:
        extra = ""
        if level == 1:
            edge = graph.edge(node, start) if direction == "in" else graph.edge(start, node)
            if edge:
                nums = sorted({s["line"] for s in edge["sites"]})
                extra = f"  (line{'s' if len(nums) > 1 else ''} {', '.join(map(str, nums[:8]))}" \
                        f"{', ...' if len(nums) > 8 else ''})"
        print(f"  [{level}] {node}{extra}")
    return 0


# --------------------------------------------------------------------------- #
# Stage 4: analyzers
# --------------------------------------------------------------------------- #
# Every analyzer works on the saved graph data only (plus the import issues kept
# in graph.json), so `--from-graph graph.json --analyze` needs no source code.
# Each finding carries a confidence label (4.8):
#   certain    follows from exact facts: an import-time cycle, a plain-name self
#              call, an unused private helper that nothing in the project mentions
#   likely     right unless the code does something dynamic or the call graph
#              missed an edge (call edges are a lower bound, see Known limitations)
#   uncertain  plausible, but there are explicit signs of a false positive
#              (also used when a finding only exists because of weaker evidence)
ANALYSIS_SCHEMA_VERSION = 1
CONFIDENCE_ORDER = {"certain": 0, "likely": 1, "uncertain": 2}
_LOWER = {"certain": "likely", "likely": "uncertain", "uncertain": "uncertain"}
SELF_RECEIVERS = ("self.", "cls.", "super(")     # may dispatch to an override, so less exact
TOP_N = 10                                       # length of the "top" lists in the metrics
REPORT_ANALYSIS_LIMIT = 25                       # rows per list in the markdown report (JSON is complete)
CYCLE_LENGTH_LIMIT = 150                         # per-function shortest-cycle search only for cycles up to this size
FUNC_KINDS = ("function", "method", "class")

_HANDLER_DECORATOR_TAILS = {
    "route", "get", "post", "put", "delete", "patch", "head", "options", "websocket", "api_route",
    "on_event", "middleware", "errorhandler", "exception_handler", "before_request", "after_request",
    "teardown_request", "context_processor", "template_filter", "command", "group", "callback",
    "listener", "receiver", "subscriber", "task", "shared_task", "periodic_task", "hookimpl",
    "hookspec", "register", "validator", "field_validator", "root_validator", "model_validator",
}
_PLAIN_DECORATOR_TAILS = {
    "staticmethod", "classmethod", "property", "abstractmethod", "cached_property", "cache",
    "lru_cache", "wraps", "total_ordering", "override", "overload", "final", "dataclass", "unique",
    "contextmanager", "asynccontextmanager", "setter", "getter", "deleter",
}
_TEST_LIFECYCLE = {"setUp", "tearDown", "setUpClass", "tearDownClass", "setUpModule", "tearDownModule",
                   "asyncSetUp", "asyncTearDown"}


def _worst(*confs: str) -> str:
    return max(confs, key=CONFIDENCE_ORDER.__getitem__)


def _short_name(attrs: dict) -> str:
    return attrs.get("qualified_name", "").rsplit(".", 1)[-1]


def _is_dunder(name: str) -> bool:
    return len(name) > 4 and name.startswith("__") and name.endswith("__")


def _decorator_tail(decorator: str) -> str:
    return decorator.split("(")[0].strip().rsplit(".", 1)[-1]


def _is_plain_decorator(decorator: str) -> bool:
    return _decorator_tail(decorator) in _PLAIN_DECORATOR_TAILS


def _is_test_path(path: str) -> bool:
    parts = path.split("/")
    name = parts[-1]
    return (name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"
            or any(p in ("tests", "test") for p in parts[:-1]))


def _edge_confidence(edge: dict, only_loop_sites: bool = False) -> str:
    """certain if some call site names the target directly; likely if every site goes through
    self. / cls. / super() (the call may really reach an override)."""
    sites = edge.get("sites", [])
    if only_loop_sites:
        sites = [s for s in sites if s.get("loop_depth", 0) > 0]
    for s in sites:
        if not s.get("name", "").startswith(SELF_RECEIVERS):
            return "certain"
    return "likely"


# -- graph helpers -------------------------------------------------------------------- #
def _scc(nodes, succ) -> List[List[str]]:
    """Tarjan's strongly connected components, iterative (no recursion limit on deep chains).

    Returns the components in emission order: a component always comes after every component
    it can reach (callees before callers). Members of each component are sorted.
    """
    index: Dict[str, int] = {}
    low: Dict[str, int] = {}
    on_stack: Set[str] = set()
    stack: List[str] = []
    out: List[List[str]] = []
    counter = 0
    for root in sorted(nodes):
        if root in index:
            continue
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        work = [(root, iter(succ(root)))]
        while work:
            v, it = work[-1]
            advanced = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    on_stack.add(w)
                    work.append((w, iter(succ(w))))
                    advanced = True
                    break
                if w in on_stack:
                    low[v] = min(low[v], index[w])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                out.append(sorted(comp))
    return out


def _succ_from_edges(edges):
    table: Dict[str, List[str]] = {}
    for src, dst in sorted(edges):
        table.setdefault(src, []).append(dst)
    return lambda n: table.get(n, [])


def _shortest_cycle(start: str, members: Set[str], succ) -> Optional[List[str]]:
    """Shortest cycle of length >= 2 through `start` that stays inside `members`: [start, ..., start]."""
    parent: Dict[str, Optional[str]] = {start: None}
    queue = deque([start])
    while queue:
        v = queue.popleft()
        for w in succ(v):
            if w not in members:
                continue
            if w == start:
                if v == start:
                    continue
                path = [v]
                while parent[path[-1]] is not None:
                    path.append(parent[path[-1]])
                path.reverse()
                return path + [start]
            if w not in parent:
                parent[w] = v
                queue.append(w)
    return None


def _first_line(edge: Optional[dict]) -> Optional[int]:
    if not edge or not edge.get("sites"):
        return None
    return min(s["line"] for s in edge["sites"])


# -- 4.7 metrics ----------------------------------------------------------------------- #
def _graph_metrics(graph: Graph, top: int) -> dict:
    nodes = sorted(graph.nodes)
    fan_in = {n: len([p for p in graph.predecessors(n) if p != n]) for n in nodes}
    fan_out = {n: len([s for s in graph.successors(n) if s != n]) for n in nodes}

    comps = _scc(nodes, graph.successors)               # callees first
    comp_of = {n: i for i, comp in enumerate(comps) for n in comp}
    depth = [0] * len(comps)
    best: List[Optional[Tuple[str, str]]] = [None] * len(comps)
    for i, comp in enumerate(comps):
        for u in comp:
            for w in graph.successors(u):
                j = comp_of[w]
                if j != i and depth[j] + 1 > depth[i]:
                    depth[i] = depth[j] + 1
                    best[i] = (u, w)
    node_depth = {n: depth[comp_of[n]] for n in nodes}

    def chain(start: str) -> dict:
        path, hops, cur = [start], [], start
        i = comp_of[start]
        while best[i] is not None:
            u, w = best[i]
            if u != cur:                                # moved inside a cycle to reach the exit node
                path.append(u)
                hops.append("~>")
            path.append(w)
            hops.append("->")
            cur, i = w, comp_of[w]
        return {"length": node_depth[start], "path": path, "hops": hops}

    def ranked(values: Dict[str, int]) -> List[dict]:
        rows = sorted(((n, v) for n, v in values.items() if v > 0), key=lambda kv: (-kv[1], kv[0]))
        return [{"id": n, "value": v, "fan_in": fan_in[n], "fan_out": fan_out[n]} for n, v in rows[:top]]

    max_depth = max(node_depth.values(), default=0)
    deepest_start = min((n for n in nodes if node_depth[n] == max_depth), default=None)
    return {
        "nodes": len(nodes),
        "edges": len(graph.edges),
        "nodes_in_cycles": sum(len(c) for c in comps if len(c) > 1),
        "max_chain_depth": max_depth,
        "longest_chain": chain(deepest_start) if deepest_start and max_depth else None,
        "top_fan_in": ranked(fan_in),
        "top_fan_out": ranked(fan_out),
        "top_connected": ranked({n: fan_in[n] + fan_out[n] for n in nodes}),
        "deepest": ranked(node_depth),
    }


# -- 4.4 entry points -------------------------------------------------------------------- #
class _ClassIndex:
    """Project class lookup built from the call-graph class nodes (bases are matched by name)."""

    def __init__(self, cg: Graph):
        self.nodes = cg.nodes
        self.classes = {n: a for n, a in cg.nodes.items() if a.get("kind") == "class"}
        self.by_tail: Dict[str, List[str]] = defaultdict(list)
        for cid, a in self.classes.items():
            self.by_tail[_short_name(a)].append(cid)
        self._info: Dict[str, dict] = {}
        self.children: Dict[str, List[str]] = defaultdict(list)
        for cid in sorted(self.classes):
            for base in self.info(cid)["project_bases"]:
                self.children[base].append(cid)

    def _resolve_base(self, cid: str, text: str) -> Optional[str]:
        text = text.split("[")[0].strip()
        tail = text.rsplit(".", 1)[-1]
        cands = [n for n in self.by_tail.get(tail, []) if n != cid
                 and ("." not in text or n == text or n.endswith("." + text))]
        if len(cands) > 1:
            same = [n for n in cands if self.classes[n]["module"] == self.classes[cid]["module"]]
            cands = same if len(same) == 1 else []
        return cands[0] if len(cands) == 1 else None

    def info(self, cid: str) -> dict:
        if cid not in self._info:
            project, unknown, meta = [], False, False
            for base in self.classes.get(cid, {}).get("bases", []):
                if "=" in base or base.startswith("**"):
                    meta = True
                elif base == "object":
                    continue
                else:
                    resolved = self._resolve_base(cid, base)
                    if resolved:
                        project.append(resolved)
                    else:
                        unknown = True
            self._info[cid] = {"project_bases": project, "unknown_base": unknown, "metaclass": meta}
        return self._info[cid]

    def _ancestors(self, cid: str, seen: Optional[Set[str]] = None) -> List[str]:
        seen = seen if seen is not None else set()
        out = []
        for base in self.info(cid)["project_bases"]:
            if base not in seen:
                seen.add(base)
                out.append(base)
                out += self._ancestors(base, seen)
        return out

    def overrides(self, cid: str, method: str) -> bool:
        return any(f"{base}.{method}" in self.nodes for base in self._ancestors(cid))

    def overridden_in(self, cid: str, method: str) -> List[str]:
        out, seen, todo = [], set(), list(self.children.get(cid, []))
        while todo:
            child = todo.pop(0)
            if child in seen:
                continue
            seen.add(child)
            if f"{child}.{method}" in self.nodes:
                out.append(child)
            todo += self.children.get(child, [])
        return sorted(out)

    def looks_like_test_class(self, cid: str) -> bool:
        a = self.classes.get(cid)
        if not a:
            return False
        return _short_name(a).startswith("Test") or any(
            b.rsplit(".", 1)[-1].endswith("TestCase") for b in a.get("bases", []))


def find_entry_points(cg: Graph) -> List[dict]:
    """4.4: places where execution can start from outside the project's own call graph."""
    classes = _ClassIndex(cg)
    found: List[dict] = []

    def add(nid: str, a: dict, kind: str, confidence: str, detail: str):
        found.append({"id": nid, "type": kind, "confidence": confidence, "detail": detail,
                      "path": a.get("path"), "line": a.get("line")})

    for nid, a in sorted(cg.nodes.items()):
        kind, name, path = a.get("kind"), _short_name(a), a.get("path", "")
        if kind == "main-scope":
            add(nid, a, "main-block", "certain", 'if __name__ == "__main__" block')
        if kind == "module-scope" and a.get("module", "").split(".")[-1] == "__main__":
            add(nid, a, "main-module", "certain", "module run by `python -m package`")
        if kind == "function" and "." not in a.get("qualified_name", "") and name == "main":
            add(nid, a, "main-function", "likely", "function named main (CLI hook)")
        if kind in ("function", "method"):
            for d in a.get("decorators", []):
                tail = _decorator_tail(d)
                if tail == "fixture":
                    add(nid, a, "test", "likely", f"@{d}")
                    break
                if tail in _HANDLER_DECORATOR_TAILS:
                    add(nid, a, "handler", "likely", f"@{d}")
                    break
            in_test_file = _is_test_path(path)
            cid = ""
            if kind == "method":
                cid = f"{a['module']}.{a['qualified_name'].rsplit('.', 1)[0]}"
            test_class = bool(cid) and classes.looks_like_test_class(cid)
            if (name.startswith("test") and (in_test_file or test_class)) or \
               (name in _TEST_LIFECYCLE and (in_test_file or test_class)):
                add(nid, a, "test", "likely", "test function or fixture hook")
        if kind == "class" and _is_test_path(path) and _short_name(a).startswith("Test"):
            add(nid, a, "test", "likely", "test class")
        if a.get("exported"):
            add(nid, a, "exported", "certain", "listed in __all__")
    return sorted(found, key=lambda e: (e["type"], e["id"], e["detail"]))


# -- 4.1 / 4.2 cycles and recursion ---------------------------------------------------------- #
def _site_class(site: dict, src: str, cg_nodes: dict) -> str:
    """runtime = runs when the module is imported, deferred = inside a function, typing = TYPE_CHECKING only."""
    if site.get("type_checking"):
        return "typing"
    scope = site.get("scope", MODULE_SCOPE)
    if scope == MODULE_SCOPE or cg_nodes.get(f"{src}.{scope}", {}).get("kind") == "class":
        return "runtime"          # module level, or a class body (class bodies run at import time)
    return "deferred"


_IMPORT_RANK = {"runtime": 0, "deferred": 1, "typing": 2}


def analyze_import_cycles(ig: Graph, cg: Graph) -> List[dict]:
    """4.1 (modules): strongly connected components of the import graph, at three strictness levels.

    import-time  cycle made of imports that run when the module loads            (certain)
    deferred     cycle that needs function-level imports to close                (likely)
    typing-only  cycle that needs `if TYPE_CHECKING:` imports to close           (uncertain)
    """
    edge_rank: Dict[Tuple[str, str], int] = {}
    for key, edge in ig.edges.items():
        edge_rank[key] = min(_IMPORT_RANK[_site_class(s, key[0], cg.nodes)] for s in edge["sites"])
    findings, seen = [], set()
    for kind, confidence, max_rank in (("import-time", "certain", 0), ("deferred", "likely", 1),
                                        ("typing-only", "uncertain", 2)):
        keys = [k for k, r in edge_rank.items() if r <= max_rank]
        succ = _succ_from_edges(keys)
        nodes = sorted({n for k in keys for n in k})
        for comp in sorted((c for c in _scc(nodes, succ) if len(c) > 1), key=lambda c: c[0]):
            if tuple(comp) in seen:
                continue
            seen.add(tuple(comp))
            cycle = _shortest_cycle(comp[0], set(comp), succ) or comp + [comp[0]]
            hops = []
            for a, b in zip(cycle, cycle[1:]):
                edge = ig.edge(a, b)
                site = min((s for s in edge["sites"]
                            if _IMPORT_RANK[_site_class(s, a, cg.nodes)] <= max_rank),
                           key=lambda s: (s["line"], s["statement"]))
                hops.append({"src": a, "dst": b, "line": site["line"], "statement": site["statement"],
                             "scope": site["scope"], "class": _site_class(site, a, cg.nodes)})
            findings.append({"id": "", "kind": kind, "confidence": confidence, "size": len(comp),
                             "members": comp, "example_cycle": cycle, "hops": hops})
    findings.sort(key=lambda f: (_IMPORT_RANK[{"import-time": "runtime", "deferred": "deferred",
                                               "typing-only": "typing"}[f["kind"]]], f["members"]))
    for i, f in enumerate(findings, 1):
        f["id"] = f"import-cycle-{i}"
    return findings


def analyze_call_cycles(cg: Graph) -> Tuple[List[dict], dict, Set[str]]:
    """4.1 (calls) and 4.2: mutual recursion (SCC), direct recursion (self-edge), per-function cycle length.

    Returns (call cycles, {"direct": [...], "indirect": [...]}, ids of all recursive functions).
    """
    direct = []
    for (src, dst), edge in sorted(cg.edges.items()):
        if src == dst:
            a = cg.nodes[src]
            direct.append({"id": src, "path": a.get("path"), "line": a.get("line"),
                           "call_lines": sorted({s["line"] for s in edge["sites"]}),
                           "confidence": _edge_confidence(edge)})
    comps = sorted((c for c in _scc(sorted(cg.nodes), cg.successors) if len(c) > 1), key=lambda c: c[0])
    cycles, indirect = [], []
    for i, comp in enumerate(comps, 1):
        members = set(comp)
        cycle = _shortest_cycle(comp[0], members, cg.successors) or comp + [comp[0]]
        hops = [{"src": a, "dst": b, "line": _first_line(cg.edge(a, b))} for a, b in zip(cycle, cycle[1:])]
        confidence = _worst(*(_edge_confidence(cg.edge(a, b)) for a, b in zip(cycle, cycle[1:])))
        cid = f"call-cycle-{i}"
        cycles.append({"id": cid, "confidence": confidence, "size": len(comp), "members": comp,
                       "example_cycle": cycle, "hops": hops})
        for m in comp:
            if len(comp) <= CYCLE_LENGTH_LIMIT:
                own = _shortest_cycle(m, members, cg.successors)
                length = len(own) - 1 if own else None
            else:
                length = len(cycle) - 1 if m == comp[0] else None
            a = cg.nodes[m]
            indirect.append({"id": m, "cycle": cid, "cycle_length": length, "confidence": confidence,
                             "path": a.get("path"), "line": a.get("line")})
    recursive = {d["id"] for d in direct} | {r["id"] for r in indirect}
    return cycles, {"direct": direct, "indirect": indirect}, recursive


# -- 4.3 loops ------------------------------------------------------------------------------ #
def analyze_loops(cg: Graph, recursive: Set[str]) -> dict:
    """4.3: nested loops, and calls made inside a loop to code that loops or recurses."""
    nested, with_loops, total_loops = [], 0, 0
    for nid, a in sorted(cg.nodes.items()):
        n = a.get("loops", 0)
        if n:
            with_loops += 1
            total_loops += n
            depth = a.get("max_loop_depth", 1)
            if depth >= 2:
                nested.append({"id": nid, "path": a.get("path"), "line": a.get("line"),
                               "loops": n, "max_depth": depth})
    nested.sort(key=lambda r: (-r["max_depth"], r["id"]))

    heavy = {n for n, a in cg.nodes.items() if a.get("loops", 0) > 0 or n in recursive}
    reaches: Set[str] = set()                    # nodes that call (at any depth) a heavy node
    queue = deque(sorted(heavy))
    while queue:
        v = queue.popleft()
        for p in cg.predecessors(v):
            if p not in reaches:
                reaches.add(p)
                queue.append(p)

    in_loops = []
    for (src, dst), edge in sorted(cg.edges.items()):
        loop_sites = [s for s in edge["sites"] if s.get("loop_depth", 0) > 0]
        if not loop_sites:
            continue
        why = []
        if dst in recursive:
            why.append("recursive")
        if cg.nodes[dst].get("loops", 0) > 0:
            why.append("loops")
        if not why and dst in reaches:
            why.append("indirect")
        if not why:
            continue
        confidence = _edge_confidence(edge, only_loop_sites=True)
        if why == ["indirect"]:
            confidence = _LOWER[confidence]
        a = cg.nodes[src]
        in_loops.append({"caller": src, "callee": dst, "why": why, "confidence": confidence,
                         "max_loop_depth": max(s["loop_depth"] for s in loop_sites),
                         "lines": sorted({s["line"] for s in loop_sites}),
                         "path": a.get("path"), "line": a.get("line")})
    in_loops.sort(key=lambda r: (CONFIDENCE_ORDER[r["confidence"]], -r["max_loop_depth"], r["caller"], r["callee"]))
    return {"summary": {"scopes_with_loops": with_loops, "total_loops": total_loops,
                        "nested_loop_scopes": len(nested), "calls_in_loops": len(in_loops)},
            "nested": nested, "calls_in_loops": in_loops}


# -- 4.5 dead code ---------------------------------------------------------------------------- #
def find_dead_code(cg: Graph, entry_ids: Set[str]) -> Tuple[List[dict], Counter]:
    """4.5: functions / methods / classes nothing in the project calls.

    Not reported: entry points, special (dunder) methods, methods that override a project base-class
    method, classes used as a base class. A class counts as used when the class or any of its
    methods has a caller outside the class. Code only called by dead code is reported as well,
    one confidence level lower. Returns (findings, excluded-by-reason counter).
    """
    nodes = cg.nodes
    classes = _ClassIndex(cg)
    members: Dict[str, Set[str]] = defaultdict(set)      # id of a class / function -> ids defined inside it
    for nid, a in nodes.items():
        if a.get("kind") in FUNC_KINDS:
            parts = a["qualified_name"].split(".")
            for i in range(1, len(parts)):
                members[f"{a['module']}.{'.'.join(parts[:i])}"].add(nid)
    used_as_base = {b for cid in classes.classes for b in classes.info(cid)["project_bases"]}
    candidates = [n for n in sorted(nodes) if nodes[n].get("kind") in FUNC_KINDS]
    excluded: Counter = Counter()

    def ancestors(nid: str) -> List[str]:
        a = nodes[nid]
        parts = a["qualified_name"].split(".")
        return [f"{a['module']}.{'.'.join(parts[:i])}" for i in range(1, len(parts))]

    def exclusion(nid: str) -> Optional[str]:
        a = nodes[nid]
        name = _short_name(a)
        if nid in entry_ids:
            return "entry points"
        if _is_dunder(name):
            return "special (dunder) methods"
        if a["kind"] == "method":
            cid = ancestors(nid)[-1]
            if cid in classes.classes and classes.overrides(cid, name):
                return "methods overriding a project base-class method"
        if a["kind"] == "class" and nid in used_as_base:
            return "classes used as a base class"
        return None

    skip = {}
    for nid in candidates:
        reason = exclusion(nid)
        if reason:
            skip[nid] = reason
            excluded[reason] += 1

    def outside_callers(nid: str) -> List[str]:
        inner = {nid} | members.get(nid, set())
        callers = {p for n in inner for p in cg.predecessors(n)}
        callers |= set(nodes[nid].get("instantiated_from", []))      # `Foo()` whose edge goes to an inherited __init__
        return sorted(callers - inner)

    def judge(nid: str) -> Tuple[str, List[str]]:
        a = nodes[nid]
        name = _short_name(a)
        private = name.startswith("_") and not _is_dunder(name)
        confidence, reasons = ("certain" if private else "likely"), []
        if not private:
            reasons.append("public name: code outside the project may use it")

        def doubt(text: str):
            nonlocal confidence
            reasons.append(text)
            confidence = "uncertain"

        if a.get("referenced_as_value"):
            doubt("the name is also used as a value or attribute (callback, decorator, property access?)")
        if a.get("unresolved_name_hits"):
            doubt(f"{a['unresolved_name_hits']} unresolved call(s) end in `.{name}` and may reach it")
        odd = [d for d in a.get("decorators", []) if not _is_plain_decorator(d)]
        if odd:
            doubt(f"decorated with @{odd[0]} (may be registered somewhere)")
        if a["kind"] == "method":
            cid = ancestors(nid)[-1]
            if cid in classes.classes:
                info = classes.info(cid)
                if info["unknown_base"]:
                    doubt("the class has bases outside the project (a framework may call this method)")
                if info["metaclass"]:
                    doubt("the class uses a metaclass or class keywords")
                subs = classes.overridden_in(cid, name)
                if subs:
                    doubt(f"overridden in subclass {subs[0]}: it may be called through the base class")
        if a["path"].endswith("__init__.py"):
            doubt("defined in a package __init__ (public API)")
        return confidence, reasons

    def finding(nid: str, category: str, confidence: str, reasons: List[str], callers: List[str]) -> dict:
        a = nodes[nid]
        out = {"id": nid, "kind": a["kind"], "path": a.get("path"), "line": a.get("line"),
               "category": category, "confidence": confidence, "reasons": reasons}
        if callers:
            out["callers"] = callers
        return out

    dead: Dict[str, dict] = {}
    for nid in candidates:
        if nid in skip:
            continue
        callers = outside_callers(nid)
        if not callers:
            confidence, reasons = judge(nid)
            if cg.edge(nid, nid):
                reasons.append("only referenced by itself (recursion)")
            dead[nid] = finding(nid, "no-callers", confidence, reasons, [])

    def is_dead(nid: str) -> bool:
        if nid in dead:
            return True
        a = nodes.get(nid)
        return bool(a) and a.get("kind") in FUNC_KINDS and any(anc in dead for anc in ancestors(nid))

    groups = [set(c) for c in _scc(sorted(nodes), cg.successors) if len(c) > 1]    # mutual-recursion groups
    changed = True
    while changed:
        changed = False
        for nid in candidates:
            if nid in dead or nid in skip:
                continue
            callers = outside_callers(nid)
            if callers and all(is_dead(c) for c in callers):
                confidence, reasons = judge(nid)
                reasons.append("only called by dead code")
                dead[nid] = finding(nid, "only-called-by-dead-code", _LOWER[confidence], reasons, callers)
                changed = True
        # functions that only call each other (nobody else reaches the cycle) are dead as a group
        for group in groups:
            if any(n in dead or n in skip or nodes[n].get("kind") not in FUNC_KINDS for n in group):
                continue
            outside = sorted({c for n in group for c in outside_callers(n)} - group)
            if all(is_dead(c) for c in outside):
                for n in sorted(group):
                    confidence, reasons = judge(n)
                    reasons.append("only called by the other functions of its own call cycle")
                    if outside:
                        reasons.append("the cycle itself is only called by dead code")
                    dead[n] = finding(n, "unreachable-cycle", _LOWER[confidence] if outside else confidence,
                                      reasons, outside)
                changed = True

    # fold members of a dead class / function into it (one finding per dead unit)
    for nid in sorted(dead):
        dead_anc = [anc for anc in ancestors(nid) if anc in dead]
        if dead_anc:
            owner = dead[dead_anc[0]]
            owner.setdefault("contains", []).append(nodes[nid]["qualified_name"])
    findings = [f for nid, f in dead.items() if not any(anc in dead for anc in ancestors(nid))]
    for f in findings:
        if "contains" in f:
            f["contains"] = sorted(f["contains"])
    findings.sort(key=lambda f: (CONFIDENCE_ORDER[f["confidence"]], f["path"] or "", f["line"] or 0, f["id"]))
    return findings, excluded


# -- 4.6 imports ----------------------------------------------------------------------------- #
def find_import_issues(resolver: "Resolver") -> List[dict]:
    """4.6: unused imports and imports of project modules that do not exist.

    Works on names, per module: an imported name counts as used if it appears anywhere in the module
    (a function-level import that is unused while the same name is used elsewhere is not found).
    """
    issues: List[dict] = []
    for name in sorted(resolver.mod_by_name):
        m = resolver.mod_by_name[name]
        exports = set(m.exports or [])
        for imp in m.imports:
            if imp.origin == "unresolved":
                issues.append({
                    "kind": "missing-module", "module": m.module_name, "path": _rel(m.path), "line": imp.line,
                    "statement": imp.describe(), "scope": imp.scope, "name": imp.abs_module or imp.module,
                    "confidence": "likely",
                    "reason": "points into the project but no such module was found (or the relative "
                              "import leaves the scanned folder)"})
            if imp.kind == "from" and (imp.name == "*" or (imp.module == "__future__" and imp.level == 0)):
                continue
            bound = imp.bound_name
            if not bound or bound in m.used_names or bound in exports:
                continue
            if imp.alias and imp.alias == (imp.name if imp.kind == "from" else imp.module):
                continue                                  # `import x as x`: the explicit re-export form
            confidence, reasons = "certain", []
            if m.is_package:
                confidence, reasons = "uncertain", ["package __init__: the import may be a re-export"]
            if imp.in_try:
                confidence, reasons = "uncertain", reasons + ["inside try: (optional-dependency probe?)"]
            if imp.type_checking:
                confidence, reasons = _worst(confidence, "likely"), reasons + [
                    "inside `if TYPE_CHECKING:` (may be used in a string annotation)"]
            if m.uses_dynamic_names:
                confidence, reasons = "uncertain", reasons + ["module uses globals() / eval() / exec()"]
            issues.append({
                "kind": "unused-import", "module": m.module_name, "path": _rel(m.path), "line": imp.line,
                "statement": imp.describe(), "scope": imp.scope, "name": bound,
                "confidence": confidence, "reason": "; ".join(reasons)})
    issues.sort(key=lambda i: (i["kind"], i["path"], i["line"], i["name"]))
    return issues


# -- assembling ----------------------------------------------------------------------------- #
def _confidence_lists(a: dict) -> List[Tuple[str, list]]:
    out = [("import cycles", a["cycles"]["import"]), ("call cycles", a["cycles"]["call"]),
           ("direct recursion", a["recursion"]["direct"]), ("calls in loops", a["loops"]["calls_in_loops"]),
           ("dead code", a["dead_code"])]
    if a.get("imports"):
        out += [("unused imports", a["imports"]["unused"]), ("missing modules", a["imports"]["missing"])]
    return out


def _summarize(a: dict) -> dict:
    rows = {}
    for name, items in _confidence_lists(a):
        counts = Counter(i["confidence"] for i in items)
        rows[name] = {"total": len(items), **{k: counts.get(k, 0) for k in CONFIDENCE_ORDER}}
    return {"findings": rows, "entry_points": len(a["entry_points"]),
            "recursive_functions_in_cycles": len(a["recursion"]["indirect"]),
            "nested_loop_scopes": len(a["loops"]["nested"])}


def _version_tuple(text: str) -> Tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", text)[:3])


def analyze_graphs(graphs: Dict[str, Graph], import_issues: Optional[List[dict]] = None,
                   top: int = TOP_N, graph_tool_version: Optional[str] = None) -> dict:
    """Run every Stage 4 analyzer on the two graphs (+ the import issues saved with them)."""
    cg, ig = graphs["call"], graphs["import"]
    entries = find_entry_points(cg)
    call_cycles, recursion, recursive = analyze_call_cycles(cg)
    dead, excluded = find_dead_code(cg, {e["id"] for e in entries})
    notes = [
        "Call edges are a lower bound (no type inference yet): calls such as `x.run()` or `self.db.save()` "
        "are not edges. Dead-code findings are labelled with that in mind; read `uncertain` as 'check by hand'.",
        "Dead code is judged inside the scanned project only: public names may be used by outside code.",
    ]
    if graph_tool_version is not None and _version_tuple(graph_tool_version) < (0, 5):
        notes.append(f"This graph.json was written by code_mapper {graph_tool_version}: it has no TYPE_CHECKING "
                     "marks, re-export (`__all__`) marks or loop depths, so import cycles can look more certain "
                     "than they are and entry points / nested loops are incomplete. Re-scan for exact results.")
    if import_issues is None:
        notes.append("Unused / missing imports are not available: this graph.json has no import_issues "
                     "(re-scan the project to get them).")
    analysis = {
        "analysis_schema_version": ANALYSIS_SCHEMA_VERSION,
        "entry_points": entries,
        "cycles": {"import": analyze_import_cycles(ig, cg), "call": call_cycles},
        "recursion": recursion,
        "loops": analyze_loops(cg, recursive),
        "dead_code": dead,
        "dead_code_excluded": dict(sorted(excluded.items())),
        "imports": None if import_issues is None else {
            "unused": [i for i in import_issues if i["kind"] == "unused-import"],
            "missing": [i for i in import_issues if i["kind"] == "missing-module"]},
        "metrics": {"call_graph": _graph_metrics(cg, top), "import_graph": _graph_metrics(ig, top)},
        "notes": notes,
    }
    analysis["summary"] = _summarize(analysis)
    return analysis


def filter_analysis(analysis: dict, min_confidence: str) -> dict:
    """Keep only findings at least as confident as `min_confidence` (certain > likely > uncertain)."""
    if min_confidence == "uncertain":
        return analysis
    data = json.loads(json.dumps(analysis))
    limit = CONFIDENCE_ORDER[min_confidence]

    def keep(items):
        return [i for i in items if CONFIDENCE_ORDER[i["confidence"]] <= limit]

    data["cycles"] = {k: keep(v) for k, v in data["cycles"].items()}
    data["recursion"] = {k: keep(v) for k, v in data["recursion"].items()}
    data["loops"]["calls_in_loops"] = keep(data["loops"]["calls_in_loops"])
    data["dead_code"] = keep(data["dead_code"])
    if data.get("imports"):
        data["imports"] = {k: keep(v) for k, v in data["imports"].items()}
    data["min_confidence"] = min_confidence
    data["summary"] = _summarize(data)
    return data


def analysis_summary_line(analysis: dict) -> str:
    rows = analysis["summary"]["findings"]
    parts = [f"{rows[k]['total']} {k}" for k in rows if rows[k]["total"]]
    return "Analysis: " + (", ".join(parts) if parts else "no findings") + \
           f"; {analysis['summary']['entry_points']} entry points"


# -- markdown ---------------------------------------------------------------------------------- #
def _cell(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _capped(items: list, limit: Optional[int]) -> Tuple[list, int]:
    if limit is None or len(items) <= limit:
        return items, 0
    return items[:limit], len(items) - limit


def _more(hidden: int) -> List[str]:
    return [f"_... and {hidden} more (the analysis JSON has the full list)_", ""] if hidden else []


def _chain_text(chain: dict) -> str:
    out = chain["path"][0]
    for hop, node in zip(chain["hops"], chain["path"][1:]):
        out += f" {hop} {node}"
    return out


def _metric_table(title: str, rows: List[dict], value_name: str) -> List[str]:
    if not rows:
        return []
    lines = [f"**{title}**", "", f"| Node | {value_name} | Fan-in | Fan-out |", "|---|---:|---:|---:|"]
    for r in rows:
        lines.append(f"| `{_cell(r['id'])}` | {r['value']} | {r['fan_in']} | {r['fan_out']} |")
    return lines + [""]


def analysis_lines(analysis: dict, limit: Optional[int] = REPORT_ANALYSIS_LIMIT) -> List[str]:
    """Markdown for the analysis (limit = rows per list, None = everything)."""
    a = analysis
    lines = ["## Analysis", "",
             "Findings are labelled **certain** (exact facts), **likely** (right unless the code is dynamic "
             "or the call graph missed an edge) or **uncertain** (signs of a false positive, check by hand).", ""]
    if a.get("min_confidence"):
        lines += [f"_Showing findings at least `{a['min_confidence']}` only._", ""]
    for note in a["notes"]:
        lines.append(f"- {note}")
    lines += ["", "| Finding | Total | certain | likely | uncertain |", "|---|---:|---:|---:|---:|"]
    for name, row in a["summary"]["findings"].items():
        lines.append(f"| {name} | {row['total']} | {row['certain']} | {row['likely']} | {row['uncertain']} |")
    lines += ["", f"Entry points: {a['summary']['entry_points']}; functions inside call cycles: "
              f"{a['summary']['recursive_functions_in_cycles']}; scopes with nested loops: "
              f"{a['summary']['nested_loop_scopes']}", ""]

    # entry points
    lines += ["### Entry points", ""]
    if a["entry_points"]:
        rows, hidden = _capped(a["entry_points"], limit)
        lines += ["| Type | Node | Why | Confidence |", "|---|---|---|---|"]
        for e in rows:
            lines.append(f"| {e['type']} | `{_cell(e['id'])}` | {_cell(e['detail'])} | {e['confidence']} |")
        lines += [""] + _more(hidden)
    else:
        lines += ["_None found._", ""]

    # cycles
    lines += ["### Circular dependencies", ""]
    for title, items in (("Import cycles (modules)", a["cycles"]["import"]),
                         ("Call cycles (mutual recursion)", a["cycles"]["call"])):
        lines += [f"**{title}:** " + ("_none_" if not items else f"{len(items)}"), ""]
        rows, hidden = _capped(items, limit)
        for c in rows:
            kind = f"{c['kind']}, " if "kind" in c else ""
            lines.append(f"- `{c['id']}` ({kind}{c['confidence']}, {c['size']} members): "
                         + " -> ".join(f"`{n}`" for n in c["example_cycle"]))
            for hop in c["hops"]:
                where = f"line {hop['line']}"
                if "statement" in hop:
                    where += f", `{hop['statement']}`" + ("" if hop["class"] == "runtime" else f" ({hop['class']})")
                lines.append(f"  - `{hop['src']}` -> `{hop['dst']}` ({where})")
            if c["size"] > len(c["example_cycle"]) - 1:
                lines.append(f"  - all members: {', '.join(f'`{m}`' for m in c['members'][:15])}"
                             + (", ..." if c["size"] > 15 else ""))
        lines += [""] + _more(hidden)

    # recursion
    lines += ["### Recursion", ""]
    direct = a["recursion"]["direct"]
    lines += [f"**Direct (a function calls itself):** " + ("_none_" if not direct else str(len(direct))), ""]
    if direct:
        rows, hidden = _capped(direct, limit)
        lines += ["| Function | Call lines | Confidence |", "|---|---|---|"]
        for d in rows:
            lines.append(f"| `{_cell(d['id'])}` | {', '.join(map(str, d['call_lines']))} | {d['confidence']} |")
        lines += [""] + _more(hidden)
    indirect = a["recursion"]["indirect"]
    lines += [f"**Indirect (cycle length > 1):** " + ("_none_" if not indirect else f"{len(indirect)} functions"), ""]
    if indirect:
        rows, hidden = _capped(indirect, limit)
        lines += ["| Function | Shortest cycle | Cycle | Confidence |", "|---|---:|---|---|"]
        for r in rows:
            lines.append(f"| `{_cell(r['id'])}` | {r['cycle_length'] if r['cycle_length'] else '?'} | "
                         f"{r['cycle']} | {r['confidence']} |")
        lines += [""] + _more(hidden)

    # loops
    ls = a["loops"]["summary"]
    lines += ["### Loops", "",
              f"{ls['total_loops']} loops in {ls['scopes_with_loops']} scopes; {ls['nested_loop_scopes']} scopes "
              f"with nested loops; {ls['calls_in_loops']} calls inside loops into code that loops or recurses.", ""]
    if a["loops"]["nested"]:
        rows, hidden = _capped(a["loops"]["nested"], limit)
        lines += ["**Nested loops:**", "", "| Scope | Loops | Max depth |", "|---|---:|---:|"]
        for r in rows:
            lines.append(f"| `{_cell(r['id'])}` | {r['loops']} | {r['max_depth']} |")
        lines += [""] + _more(hidden)
    if a["loops"]["calls_in_loops"]:
        rows, hidden = _capped(a["loops"]["calls_in_loops"], limit)
        lines += ["**Calls inside loops into looping / recursive code:**", "",
                  "| Caller | Callee | Why | Loop depth | Lines | Confidence |", "|---|---|---|---:|---|---|"]
        for r in rows:
            why = ", ".join("calls looping code further down" if w == "indirect" else w for w in r["why"])
            lines.append(f"| `{_cell(r['caller'])}` | `{_cell(r['callee'])}` | {why} | {r['max_loop_depth']} | "
                         f"{', '.join(map(str, r['lines'][:6]))} | {r['confidence']} |")
        lines += [""] + _more(hidden)

    # dead code
    lines += ["### Dead code candidates", ""]
    if a["dead_code_excluded"]:
        lines += ["Not reported: " + ", ".join(f"{v} {k}" for k, v in a["dead_code_excluded"].items()) + ".", ""]
    if a["dead_code"]:
        rows, hidden = _capped(a["dead_code"], limit)
        lines += ["| Confidence | Kind | Node | Line | Notes |", "|---|---|---|---:|---|"]
        for f in rows:
            notes = list(f["reasons"])
            if f["category"] == "only-called-by-dead-code":
                notes.insert(0, "called only by " + ", ".join(f"`{c}`" for c in f["callers"][:3]))
            if f.get("contains"):
                notes.append("contains " + ", ".join(f"`{c}`" for c in f["contains"][:6]))
            lines.append(f"| {f['confidence']} | {f['kind']} | `{_cell(f['id'])}` | {f['line']} | "
                         f"{_cell('; '.join(notes))} |")
        lines += [""] + _more(hidden)
    else:
        lines += ["_None found._", ""]

    # imports
    lines += ["### Imports", ""]
    if a.get("imports") is None:
        lines += ["_Not available for this graph file._", ""]
    else:
        for title, key in (("Unused imports", "unused"), ("Imports of missing project modules", "missing")):
            items = a["imports"][key]
            lines += [f"**{title}:** " + ("_none_" if not items else str(len(items))), ""]
            if items:
                rows, hidden = _capped(items, limit)
                lines += ["| Confidence | Module | Line | Import | Notes |", "|---|---|---:|---|---|"]
                for i in rows:
                    lines.append(f"| {i['confidence']} | `{_cell(i['module'])}` | {i['line']} | "
                                 f"`{_cell(i['statement'])}` | {_cell(i['reason'])} |")
                lines += [""] + _more(hidden)

    # metrics
    lines += ["### Metrics", ""]
    for title, key in (("Call graph", "call_graph"), ("Import graph", "import_graph")):
        m = a["metrics"][key]
        lines += [f"**{title}:** {m['nodes']} nodes, {m['edges']} edges, {m['nodes_in_cycles']} nodes in cycles, "
                  f"longest chain {m['max_chain_depth']} steps", ""]
        if m["longest_chain"]:
            lines += ["Longest chain (`~>` = moves inside a cycle):", "", f"`{_chain_text(m['longest_chain'])}`", ""]
        lines += _metric_table("Highest fan-in (most used)", m["top_fan_in"], "Score")
        lines += _metric_table("Highest fan-out (uses the most)", m["top_fan_out"], "Score")
        lines += _metric_table("Most connected", m["top_connected"], "In + out")
        lines += _metric_table("Deepest call / import chains below them", m["deepest"], "Depth")
    return lines


# --------------------------------------------------------------------------- #
# Report building (Markdown) -- used for both console and file output
# --------------------------------------------------------------------------- #
def _indent_doc(doc: str, prefix: str = "> ") -> str:
    return "\n".join(prefix + line if line else prefix.rstrip() for line in doc.splitlines())


def _resolution_text(c: CallInfo) -> str:
    if c.status == "unresolved":
        return f"unresolved ({c.reason})" + (f": {c.note}" if c.note else "")
    return f"`{c.target}` [{c.status}" + (f": {c.note}" if c.note else "") + "]"


def _call_lines(calls: List[CallInfo]) -> List[str]:
    out = []
    for c in calls:
        text = f"- `{c.name}()` (line {c.line})"
        if c.status is not None:
            text += f" -> {_resolution_text(c)}"
        if c.loop_depth:
            text += f" - in loop, depth {c.loop_depth}"
        out.append(text)
    return out


def _loop_lines(loops: List[LoopInfo]) -> List[str]:
    return [f"- `{lp.kind}` (line {lp.line}, depth {lp.depth})" for lp in loops]


def _scope_lines(title: str, scope: FunctionInfo) -> List[str]:
    """Lines for a pseudo-function (<module> / <main>); empty if it holds nothing."""
    if not scope.calls and not scope.loops:
        return []
    lines = [title, ""]
    if scope.loops:
        lines += ["Loops:", ""] + _loop_lines(scope.loops) + [""]
    if scope.calls:
        lines += ["Calls:", ""] + _call_lines(scope.calls) + [""]
    return lines


def _coverage_lines(resolver: "Resolver") -> List[str]:
    st = resolver.stats
    lines = ["## Resolution coverage", ""]
    if st.total == 0:
        return lines + ["_No calls found._", ""]
    ext = ""
    if st.external_kinds:
        ext = " (" + ", ".join(f"{k} {v}" for k, v in sorted(st.external_kinds.items())) + ")"
    lines += [
        f"- **Calls analysed:** {st.total}",
        f"- **Resolved:** {st.resolved()} ({st.percent():.1f}%)",
        f"  - local (same module): {st.by_status['local']}",
        f"  - internal (other project module): {st.by_status['internal']}",
        f"  - external: {st.by_status['external']}{ext}",
        f"- **Unresolved:** {st.by_status['unresolved']} ({100 - st.percent():.1f}%)",
        "",
    ]
    if st.by_reason:
        lines += ["| Unresolved reason | Calls | Meaning |", "|---|---:|---|"]
        for reason, count in st.by_reason.most_common():
            lines.append(f"| `{reason}` | {count} | {REASON_HELP.get(reason, '')} |")
        lines.append("")
    if resolver.duplicate_modules:
        lines += ["**Warning:** these files share a dotted module name with an earlier file, "
                  "so lookups use the first one:", ""]
        lines += [f"- `{path}` (module `{name}`)" for name, path in resolver.duplicate_modules]
        lines.append("")
    return lines


def _edge_list(title: str, graph: Graph, node_id: str, direction: str) -> List[str]:
    """'Called by' / 'Imported by' block built from reverse edges."""
    others = graph.predecessors(node_id) if direction == "in" else graph.successors(node_id)
    if not others:
        return [f"{title} _none found_", ""]
    lines = [title, ""]
    for other in others[:REPORT_EDGE_LIMIT]:
        edge = graph.edge(other, node_id) if direction == "in" else graph.edge(node_id, other)
        nums = sorted({s["line"] for s in edge["sites"]})
        shown = ", ".join(str(n) for n in nums[:5]) + (", ..." if len(nums) > 5 else "")
        lines.append(f"- `{other}` ({'line' if len(nums) == 1 else 'lines'} {shown})")
    if len(others) > REPORT_EDGE_LIMIT:
        lines.append(f"- ... and {len(others) - REPORT_EDGE_LIMIT} more")
    lines.append("")
    return lines


def _is_graph_node(graph: Graph, node_id: str, path: str) -> bool:
    """True if the node comes from this file (a duplicate module name keeps only the first file's nodes)."""
    return graph.nodes.get(node_id, {}).get("path") == _rel(path)


def build_report(root: str, modules: List[ModuleInfo], generated_at: datetime,
                 resolver: Optional["Resolver"] = None,
                 graphs: Optional[Dict[str, Graph]] = None,
                 analysis: Optional[dict] = None) -> str:
    total_funcs = sum(len(m.functions) for m in modules)
    total_classes = sum(len(m.classes) for m in modules)
    total_imports = sum(len(m.imports) for m in modules)
    total_loops = sum(m.loop_count() for m in modules)
    lines = [
        "# Code Mapper Report",
        "",
        f"- **Project:** `{os.path.abspath(root)}`",
        f"- **Generated:** {generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Modules scanned:** {len(modules)}",
        f"- **Classes found:** {total_classes}",
        f"- **Functions found:** {total_funcs}",
        f"- **Imports found:** {total_imports}",
        f"- **Loops found:** {total_loops}",
    ]
    if resolver is not None:
        lines.append(f"- **Calls resolved:** {resolver.stats.resolved()} of {resolver.stats.total} "
                     f"({resolver.stats.percent():.1f}%)")
    if graphs is not None:
        cg, ig = graphs["call"], graphs["import"]
        lines.append(f"- **Call graph:** {len(cg.nodes)} nodes, {len(cg.edges)} edges")
        lines.append(f"- **Import graph:** {len(ig.nodes)} nodes, {len(ig.edges)} edges")
    if analysis is not None:
        lines.append(f"- **{analysis_summary_line(analysis)}**")
    lines += [
        "",
        "## Summary",
        "",
        "| Module | Dotted name | Imports | Classes | Functions | Loops | Module docstring |",
        "|---|---|---:|---:|---:|---:|:---:|",
    ]
    for m in modules:
        status = "error" if m.error else ("yes" if m.docstring else "no")
        lines.append(
            f"| `{m.path}` | `{m.module_name}` | {len(m.imports)} | {len(m.classes)} "
            f"| {len(m.functions)} | {m.loop_count()} | {status} |")
    lines.append("")
    if resolver is not None:
        lines += _coverage_lines(resolver)
    if analysis is not None:
        lines += analysis_lines(analysis, limit=REPORT_ANALYSIS_LIMIT)

    for m in modules:
        lines += [f"## Module: `{m.path}`", ""]
        if m.error:
            lines += [f"Could not parse: `{m.error}`", ""]
            continue
        kind = "package `__init__`" if m.is_package else "module"
        lines += [f"**Dotted name:** `{m.module_name}` ({kind})", ""]
        if m.docstring:
            lines += ["**Module docstring:**", "", _indent_doc(m.docstring), ""]
        else:
            lines += ["_No module docstring._", ""]

        if m.imports:
            lines += ["**Imports:**", ""]
            for imp in m.imports:
                where = "" if imp.scope == MODULE_SCOPE else f" - inside `{imp.scope}`"
                dep = ""
                if imp.origin == "internal":
                    dep = f" -> internal `{imp.abs_module}`"
                elif imp.origin == "unresolved":
                    dep = " -> unresolved"
                elif imp.origin:
                    dep = f" -> {imp.origin} `{imp.abs_module}`"
                lines.append(f"- `{imp.describe()}` (line {imp.line}){where}{dep}")
            lines.append("")
        else:
            lines += ["**Imports:** _none_", ""]
        if graphs is not None and _is_graph_node(graphs["import"], m.module_name, m.path):
            lines += _edge_list("**Imported by:**", graphs["import"], m.module_name, "in")

        if m.classes:
            lines += ["**Classes:**", ""]
            for c in m.classes:
                bases = f"({', '.join(c.bases)})" if c.bases else ""
                lines.append(f"- `{c.qualified_name}{bases}` (line {c.line})")
                if c.decorators:
                    lines.append(f"  - decorators: {', '.join(f'`@{d}`' for d in c.decorators)}")
                lines.append(f"  - methods: {', '.join(f'`{n}`' for n in c.methods) if c.methods else '_none_'}")
                if c.docstring:
                    lines.append(f"  - docstring: {c.docstring.splitlines()[0]}")
            lines.append("")

        if m.aliases:
            lines += ["**Module-level aliases (candidates):**", ""]
            lines += [f"- `{a.name}` = `{a.target}` (line {a.line})" for a in m.aliases]
            lines.append("")

        if m.module_scope:
            lines += _scope_lines("**Module-level code (`<module>`):**", m.module_scope)
        if m.main_block:
            lines += _scope_lines(
                f'**Main block (`if __name__ == "__main__"`, line {m.main_block.line}):**', m.main_block)
            if not m.main_block.calls and not m.main_block.loops:
                lines += [f'**Main block:** present (line {m.main_block.line}), no calls or loops', ""]

        if not m.functions:
            lines += ["_No functions defined._", ""]
            continue

        for fn in m.functions:
            prefix = "async " if fn.is_async else ""
            sig = f"{prefix}def {fn.qualified_name}({', '.join(fn.args)})"
            if fn.returns:
                sig += f" -> {fn.returns}"
            lines += [f"### `{fn.qualified_name}`  (line {fn.line})", "", "```python", sig, "```", ""]

            if fn.enclosing_class:
                lines += [f"**Method of:** `{fn.enclosing_class}`", ""]
            if fn.decorators:
                lines += [f"**Decorators:** {', '.join(f'`@{d}`' for d in fn.decorators)}", ""]

            if fn.docstring:
                lines += ["**Docstring:**", "", _indent_doc(fn.docstring), ""]
            else:
                lines += ["_No docstring._", ""]

            lines.append(f"**Inputs:** {', '.join(f'`{a}`' for a in fn.args) if fn.args else '_none_'}")
            lines.append("")

            if fn.loops:
                lines += ["**Loops:**", ""] + _loop_lines(fn.loops)
            else:
                lines.append("**Loops:** _none_")
            lines.append("")

            if fn.calls:
                lines += ["**Calls:**", ""] + _call_lines(fn.calls)
            else:
                lines.append("**Calls:** _none_")
            lines.append("")

            if graphs is not None:
                node_id = f"{m.module_name}.{fn.qualified_name}"
                if _is_graph_node(graphs["call"], node_id, m.path):
                    lines += _edge_list("**Called by:**", graphs["call"], node_id, "in")

    if resolver is not None and resolver.symbols:
        lines += ["## Symbol table", "", "| Symbol | Kind | Line |", "|---|---|---:|"]
        for full in sorted(resolver.symbols):
            sym = resolver.symbols[full]
            lines.append(f"| `{full}` | {sym.kind} | {sym.line} |")
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
    parser.add_argument("--no-graphs", action="store_true", help="don't write graph.json / .mmd / .dot files")
    parser.add_argument("--query", nargs=2, metavar=("KIND", "NODE"),
                        help="callers | callees | importers | imports of NODE (full id, or a unique ending/part of it)")
    parser.add_argument("--depth", type=int, default=1, help="levels to follow for --query (default 1, 0 = all)")
    parser.add_argument("--from-graph", metavar="GRAPH_JSON",
                        help="answer --query / --analyze from a saved graph.json, without scanning any code")
    parser.add_argument("--analyze", action="store_true",
                        help="with --from-graph: print the analysis (cycles, recursion, loops, entry points, "
                             "dead code, imports, metrics); a normal scan always includes it")
    parser.add_argument("--no-analysis", action="store_true", help="skip the analysis on a normal scan")
    parser.add_argument("--min-confidence", choices=list(CONFIDENCE_ORDER), default="uncertain",
                        help="only show / save findings at least this confident (default: uncertain = all)")
    args = parser.parse_args(argv)

    if args.query and args.query[0] not in QUERY_KINDS:
        parser.error(f"unknown query kind '{args.query[0]}' (use: {', '.join(QUERY_KINDS)})")
    if args.from_graph:
        if not args.query and not args.analyze:
            parser.error("--from-graph needs --query and/or --analyze")
        try:
            graphs = load_graphs(args.from_graph)
            issues = load_import_issues(args.from_graph) if args.analyze else None
            graph_version = load_tool_version(args.from_graph) if args.analyze else None
        except (OSError, ValueError, KeyError) as exc:
            print(f"Error: cannot read graph file: {exc}", file=sys.stderr)
            return 1
        if args.analyze:
            result = filter_analysis(analyze_graphs(graphs, issues, graph_tool_version=graph_version),
                                     args.min_confidence)
            print("\n".join(analysis_lines(result, limit=None)))
        if args.query:
            if args.analyze:
                print()
            return run_query(graphs, args.query[0], args.query[1], args.depth)
        return 0

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"Error: '{root}' is not a folder", file=sys.stderr)
        return 1

    now = datetime.now()
    modules = analyze_project(root)
    resolver = resolve_project(modules)
    graphs = build_graphs(resolver)
    import_issues = find_import_issues(resolver)
    analysis = None
    if not args.no_analysis:
        analysis = filter_analysis(analyze_graphs(graphs, import_issues), args.min_confidence)
    report = build_report(root, modules, now, resolver, graphs, analysis)

    if not args.quiet:
        print(report)
    path = write_report(report, now)
    st = resolver.stats
    print(f"\nResolved {st.resolved()} of {st.total} calls ({st.percent():.1f}%), "
          f"{len(resolver.symbols)} symbols in the table")
    print(f"Call graph: {len(graphs['call'].nodes)} nodes, {len(graphs['call'].edges)} edges; "
          f"import graph: {len(graphs['import'].nodes)} nodes, {len(graphs['import'].edges)} edges")
    if analysis is not None:
        print(analysis_summary_line(analysis))
    print(f"Report saved to: {path}")
    if not args.no_graphs:
        graph_dir = os.path.join(os.path.dirname(path), f"graphs_{now.strftime('%H-%M-%S')}")
        write_graphs(graphs, os.path.basename(root), graph_dir, import_issues, analysis)
        print(f"Graphs{' and analysis' if analysis is not None else ''} saved to: {graph_dir}")
    if args.query:
        print()
        return run_query(graphs, args.query[0], args.query[1], args.depth)
    return 0


if __name__ == "__main__":
    sys.exit(main())
