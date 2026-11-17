"""
code_mapper.py  (Python algorithm, proof-of-concept draft)
==========================================================
What can static analysis alone get out of a Python project?  This single file answers that:
it reads a project with the built-in `ast` module only (no third-party packages, no network,
the code is never run) and records everything it can find.

It is ONE language algorithm.  The CodeMap engine that will host it (and the algorithms for
other languages) is not decided yet, so the file is built around one narrow boundary:

    INPUT   run(root, ignore=..., analyze=..., min_confidence=..., max_bytes=..., previous=...)
    OUTPUT  a plain dict (JSON-safe): see "ENGINE BOUNDARY" at the end of the file

Everything above that boundary (scanner -> parser -> resolver -> graphs -> analyzers -> history
-> dossier) is the algorithm; everything below it (files, markdown, console, CLI) is only one way
of delivering the result and is what an engine would replace.

Stages (sections of this file, in order)
----------------------------------------
  Config / Data models
  Stage 1   scanner + parser   files, modules, imports, classes, functions, docstrings, arguments,
                               decorators, calls, loops, aliases, __all__, main blocks, type hints
  Stage 2   resolver           project symbol table; every call classified local / internal /
                               external / unresolved (with a reason); light type inference
  Stage 3   graphs             call graph and import graph (+ reverse edges, JSON / Mermaid / DOT)
  Stage 4   analyzers          import and call cycles, recursion, loops, entry points, dead code,
                               unused / missing imports, metrics; each finding certain / likely / uncertain
  Report                       markdown and JSON reports
  Stage 6   history, dossier   snapshot per run + diff with the previous run; onboarding dossier
                               with one page per module
  Pipeline / ENGINE BOUNDARY   run(), result_to_dict(), write_outputs()
  CLI

Outputs of one CLI scan (default folder: reports/ next to this file, or --output DIR)
-----------------------------------------------------------------------------------
  <date>/report_<time>.md            human report (or .json with --format json)
  <date>/graphs_<time>/result.json   EVERYTHING the algorithm found, in one file (the engine output)
  <date>/graphs_<time>/graph.json    call + import graph (reload with --from-graph)
  <date>/graphs_<time>/analysis.json findings
  <date>/graphs_<time>/diff.json     changes since the previous run
  <date>/graphs_<time>/*.mmd, *.dot  diagrams
  <date>/dossier_<time>/dossier.md   onboarding dossier (+ modules/<module>.md)
  history/<project>-<hash>/snapshot_<date>_<time>.json

Usage
-----
  python code_mapper.py path/to/project
  python code_mapper.py . --ignore migrations --min-confidence likely
  python code_mapper.py . --format json --no-reports          # the result on stdout only
  python code_mapper.py . --query callers pkg.core.Engine.make --depth 2
  python code_mapper.py --from-graph reports/<date>/graphs_<time>/graph.json --analyze
  python code_mapper.py . --history
  python code_mapper.py --diff OLD_SNAPSHOT.json NEW_SNAPSHOT.json
  python code_mapper.py --help

From code:
  import code_mapper
  result = code_mapper.run("path/to/project")      # dict with everything
  result["facts"]["modules"][0]["functions"][0]["calls"]

Requires Python 3.9+ (ast.unparse).  No external dependencies.  Tests: python -m unittest discover tests
"""
import argparse
import ast
import builtins
import fnmatch
import hashlib
import io
import json
import os
import re
import sys
import time
import tokenize
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set, Tuple

if sys.version_info < (3, 9):
    sys.exit("code_mapper.py needs Python 3.9 or newer (ast.unparse).")


# ==================================================================================================
# Config (constants shared by every stage)
# ==================================================================================================
# Constants shared by every stage.
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

SOURCE_SUFFIXES = (".py", ".pyi")     # .pyi only when there is no .py of the same name
MAX_FILE_BYTES = 5 * 1024 * 1024      # bigger files are listed as errors, not parsed (generated code, data dumps)

MODULE_SCOPE = "<module>"   # pseudo-function: module-level / class-body code
MAIN_SCOPE = "<main>"       # pseudo-function: `if __name__ == "__main__":` block


_STDLIB_NAMES = getattr(sys, "stdlib_module_names", None)     # Python 3.10+ only
_PARAM_RE = re.compile(r"\*{0,2}\s*([A-Za-z_]\w*)")
_IDENT_RE = re.compile(r"[A-Za-z_]\w*")

TOOL_VERSION = "0.7"
GRAPH_SCHEMA_VERSION = 1
MERMAID_EDGE_WARN = 500          # Mermaid refuses to draw more edges than this by default
REPORT_EDGE_LIMIT = 20           # max "Called by" / "Imported by" entries listed per item in the report

QUERY_KINDS = {                  # query name -> (graph, direction)
    "callers": ("call", "in"),
    "callees": ("call", "out"),
    "importers": ("import", "in"),
    "imports": ("import", "out"),
}


# ==================================================================================================
# Data models (filled by the parser, Stage 1, and the resolver, Stage 2)
# ==================================================================================================
# Data models filled by the parser (Stage 1) and the resolver (Stage 2).
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
    inferred: bool = False               # resolved through an inferred type (2.9), e.g. `x = Foo(); x.run()`


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
    # 2.9 type hints: name -> "call:<dotted callee>" (x = Foo()) or "ann:<annotation>" (x: Foo / db: Database);
    # only kept when every binding of the name agrees
    var_types: Dict[str, str] = field(default_factory=dict)
    param_types: Dict[str, str] = field(default_factory=dict)
    end_line: int = 0                 # last line of the def (0 for pseudo-functions)
    fingerprint: str = ""             # hash of the source lines (decorators + def); changes when the code does


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
    attr_types: Dict[str, str] = field(default_factory=dict)   # 2.9: instance attribute -> type hint (self.db = Database())
    end_line: int = 0


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
    is_stub: bool = False                                # a .pyi stub (declarations only)
    line_count: int = 0                                  # lines in the file
    warnings: List[str] = field(default_factory=list)    # parsed, but something was odd (encoding fallback, ...)

    def loop_count(self) -> int:
        scopes = list(self.functions) + [s for s in (self.module_scope, self.main_block) if s]
        return sum(len(s.loops) for s in scopes)


# ==================================================================================================
# Stage 1a: scanner (find the files, name the modules)
# ==================================================================================================
# Finding the files of a project and naming their modules.
#
# Edge cases handled here (5.3):
# - folders in IGNORE_DIRS and user `--ignore` patterns (fnmatch on names and on relative paths)
# - symlinked folders are not followed (no symlink loops); symlinked files that point outside the
#   scanned folder are skipped with a warning (an uploaded zip cannot make us read other files)
# - `.pyi` stubs: read only when there is no `.py` with the same name (stub-only modules); a stub next
#   to its `.py` would only duplicate it
def _is_skipped_dir(path: str, skip: set) -> bool:
    return os.path.normcase(os.path.realpath(path)) in skip


def _matches(patterns: List[str], name: str, rel: str) -> bool:
    rel = rel.replace(os.sep, "/")
    return any(fnmatch.fnmatch(name, p) or fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(rel, p.rstrip("/") + "/*")
               for p in patterns)


def _inside(path: str, root_real: str) -> bool:
    real = os.path.normcase(os.path.realpath(path))
    return real == root_real or real.startswith(root_real.rstrip(os.sep) + os.sep)


def find_python_files(root: str, ignore: Iterable[str] = (), warnings: Optional[List[str]] = None,
                      skip_dirs: Iterable[str] = ()) -> List[str]:
    """Return sorted relative paths of every .py (and stub-only .pyi) file under `root`.

    skip_dirs: absolute folders never entered (this tool's own reports folder always is)."""
    patterns = [p.replace("\\", "/") for p in ignore]
    skip = {OWN_REPORTS_DIR} | {os.path.normcase(os.path.realpath(d)) for d in skip_dirs}
    root_real = os.path.normcase(os.path.realpath(root))
    found = []
    for dirpath, dirnames, filenames in os.walk(root):          # followlinks=False: no symlink loops
        rel_dir = os.path.relpath(dirpath, root)
        rel_dir = "" if rel_dir == "." else rel_dir

        def keep_dir(d: str) -> bool:
            full = os.path.join(dirpath, d)
            return (d not in IGNORE_DIRS and not _is_skipped_dir(full, skip) and not os.path.islink(full)
                    and not _matches(patterns, d, os.path.join(rel_dir, d)))

        dirnames[:] = sorted(d for d in dirnames if keep_dir(d))   # prune in place so os.walk skips them
        names = set(filenames)
        for fname in sorted(filenames):
            stem, suffix = os.path.splitext(fname)
            if suffix not in SOURCE_SUFFIXES:
                continue
            if suffix == ".pyi" and f"{stem}.py" in names:
                continue
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, root)
            if _matches(patterns, fname, rel):
                continue
            if os.path.islink(full) and not _inside(full, root_real):
                if warnings is not None:
                    warnings.append(f"{rel.replace(os.sep, '/')}: symlink to a file outside the scanned folder, skipped")
                continue
            found.append(rel)
    return found


def module_name_from_path(rel_path: str, root: str) -> Tuple[str, bool]:
    """'pkg/sub/mod.py' -> ('pkg.sub.mod', False);  'pkg/__init__.py' -> ('pkg', True)."""
    parts = os.path.splitext(rel_path)[0].split(os.sep)       # drop ".py" / ".pyi"
    is_package = parts[-1] == "__init__"
    if is_package:
        parts = parts[:-1]
    root_name = os.path.basename(os.path.normpath(root))
    if os.path.isfile(os.path.join(root, "__init__.py")) or os.path.isfile(os.path.join(root, "__init__.pyi")):
        parts = [root_name] + parts               # the scanned folder is itself a package
    return ".".join(parts) or root_name, is_package


# ==================================================================================================
# Stage 1b: parser (one file -> ModuleInfo)
# ==================================================================================================
# Stage 1: parse one file with `ast` and record every fact the later stages need.
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


def _value_hint(value: ast.AST) -> str:
    """'call:Foo' for `Foo(...)` / `pkg.make(...)` / `await make(...)` (the type comes from what is called)."""
    if isinstance(value, ast.Await):
        value = value.value
    if isinstance(value, ast.Call) and _is_plain_reference(value.func):
        return "call:" + _dotted_name(value.func)
    return ""


def _agreed_types(hints: Dict[str, List[str]], stores: Counter) -> Dict[str, str]:
    """Keep a hint only if it is safe: a declared annotation (all annotations of the name agree), or
    every binding of the name is the same call (`x = Foo()` everywhere, nothing else assigned to x)."""
    out = {}
    for name in sorted(hints):
        hs = hints[name]
        anns = sorted({h for h in hs if h.startswith("ann:")})
        if anns:
            if len(anns) == 1:
                out[name] = anns[0]
            continue
        if hs and hs[0] and len(set(hs)) == 1 and len(hs) >= stores.get(name, 0):
            out[name] = hs[0]
    return out


def _param_types(args: ast.arguments) -> Dict[str, str]:
    out = {}
    for a in args.posonlyargs + args.args + args.kwonlyargs:
        if a.annotation is not None:
            out[a.arg] = "ann:" + ast.unparse(a.annotation)
    return out


class _ScopeCollector(ast.NodeVisitor):
    """Collects calls and loops of ONE scope (a function body, or the module level).

    - Bodies of nested defs are NOT entered: they are reported as their own functions.
    - Decorators and default values of nested defs run in THIS scope, so they are collected.
    - Class bodies ARE entered: class-body code runs when the enclosing scope runs.
    - Loop depth is tracked so each call knows how deep inside loops it sits.
    """

    def __init__(self, receiver: Optional[str] = None):
        self.calls: List[CallInfo] = []
        self.loops: List[LoopInfo] = []
        self.assigned: Set[str] = set()       # variable names bound in this scope
        self._depth = 0
        # 2.9: what each name / `self.attr` is bound to ("" = something we can't type)
        self.receiver = receiver              # "self" (first parameter) inside a method, else None
        self.hints: Dict[str, List[str]] = defaultdict(list)
        self.stores: Counter = Counter()
        self.attr_hints: Dict[str, List[str]] = defaultdict(list)
        self.attr_stores: Counter = Counter()
        self._class_depth = 0                 # > 0 inside a class body (its names are not our variables)

    def visit_Call(self, node: ast.Call):
        self.calls.append(CallInfo(_dotted_name(node.func), node.lineno, self._depth))
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Store):
            self.assigned.add(node.id)
            self.stores[node.id] += 1

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        if node.name:
            self.assigned.add(node.name)
            self.stores[node.name] += 1
        self.generic_visit(node)

    # -- 2.9 type hints ------------------------------------------------------ #
    def _is_self_attr(self, node: ast.AST) -> bool:
        return (isinstance(node, ast.Attribute) and self.receiver is not None and not self._class_depth
                and isinstance(node.value, ast.Name) and node.value.id == self.receiver)

    def visit_Attribute(self, node: ast.Attribute):
        if isinstance(node.ctx, ast.Store) and self._is_self_attr(node):
            self.attr_stores[node.attr] += 1
        self.generic_visit(node)

    def _record(self, target: ast.AST, hint: str):
        if self._class_depth:
            return
        if isinstance(target, ast.Name):
            self.hints[target.id].append(hint)
        elif self._is_self_attr(target):
            self.attr_hints[target.attr].append(hint)

    def visit_Assign(self, node: ast.Assign):
        hint = _value_hint(node.value)
        for target in node.targets:
            self._record(target, hint)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        self._record(node.target, "ann:" + ast.unparse(node.annotation))
        self.generic_visit(node)

    def _visit_with(self, node):
        for item in node.items:
            if item.optional_vars is not None:          # `as x` is what __enter__ returns
                hint = _value_hint(item.context_expr)
                kind = "aenter:" if isinstance(node, ast.AsyncWith) else "enter:"
                self._record(item.optional_vars, hint.replace("call:", kind, 1))
        self.generic_visit(node)

    visit_With = _visit_with
    visit_AsyncWith = _visit_with

    def visit_ClassDef(self, node: ast.ClassDef):
        self._class_depth += 1
        self.generic_visit(node)
        self._class_depth -= 1

    def var_types(self) -> Dict[str, str]:
        return _agreed_types(self.hints, self.stores)

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

    def __init__(self, lines: Optional[List[bytes]] = None):
        self._lines = lines or []         # source lines, for fingerprints
        self.functions: List[FunctionInfo] = []
        self.classes: List[ClassInfo] = []
        self.imports: List[ImportInfo] = []
        self._scope: List[str] = []       # names of enclosing classes/functions
        self._kinds: List[str] = []       # "class" / "function", parallel to _scope
        self._try_depth = 0               # > 0 while inside the body of a try statement
        self._tc_depth = 0                # > 0 while inside `if TYPE_CHECKING:`
        # 2.9: per class (qualified name): hints for instance attributes, gathered from all its methods
        self._attr_hints: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
        self._attr_stores: Dict[str, Counter] = defaultdict(Counter)

    def _scope_name(self) -> str:
        return ".".join(self._scope) or MODULE_SCOPE

    def _handle_function(self, node, is_async: bool):
        qualified = ".".join(self._scope + [node.name])
        in_class = bool(self._kinds) and self._kinds[-1] == "class"
        receiver = None
        params = node.args.posonlyargs + node.args.args
        decorators = [ast.unparse(d) for d in node.decorator_list]
        if in_class and params and not any(d.split(".")[-1] in ("staticmethod", "classmethod") for d in decorators):
            receiver = params[0].arg
        collector = _ScopeCollector(receiver)
        for stmt in node.body:
            collector.visit(stmt)
        if receiver is not None:
            cls_q = ".".join(self._scope)
            for attr, hs in collector.attr_hints.items():
                self._attr_hints[cls_q][attr].extend(hs)
            self._attr_stores[cls_q].update(collector.attr_stores)

        self.functions.append(FunctionInfo(
            name=node.name,
            qualified_name=qualified,
            line=node.lineno,
            is_async=is_async,
            args=_format_args(node.args),
            returns=ast.unparse(node.returns) if node.returns else None,
            docstring=ast.get_docstring(node),
            decorators=decorators,
            enclosing_class=".".join(self._scope) if in_class else None,
            calls=collector.calls,
            loops=collector.loops,
            local_names=sorted(collector.assigned),
            var_types=collector.var_types(),
            param_types=_param_types(node.args),
            end_line=getattr(node, "end_lineno", None) or node.lineno,
            fingerprint=self._fingerprint(node),
        ))

        self._scope.append(node.name)
        self._kinds.append("function")
        self.generic_visit(node)          # find nested functions / classes
        self._kinds.pop()
        self._scope.pop()

    def _fingerprint(self, node) -> str:
        start = min([d.lineno for d in node.decorator_list] + [node.lineno])
        end = getattr(node, "end_lineno", None) or node.lineno
        text = b"\n".join(line.rstrip() for line in self._lines[start - 1:end])
        return hashlib.sha1(text).hexdigest()[:12]

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
            end_line=getattr(node, "end_lineno", None) or node.lineno,
        )
        self.classes.append(info)
        for stmt in node.body:                 # class-level `attr: Foo` / `attr = Foo()` also type instances
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                self._attr_hints[qualified][stmt.target.id].append("ann:" + ast.unparse(stmt.annotation))
                self._attr_stores[qualified][stmt.target.id] += 1
            elif isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        self._attr_hints[qualified][target.id].append(_value_hint(stmt.value))
                        self._attr_stores[qualified][target.id] += 1

        self._scope.append(node.name)
        self._kinds.append("class")
        self.generic_visit(node)
        self._kinds.pop()
        self._scope.pop()

        info.methods = [f.name for f in self.functions if f.enclosing_class == qualified]
        info.attr_types = _agreed_types(self._attr_hints.get(qualified, {}),
                                        self._attr_stores.get(qualified, Counter()))

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


def _read_tree(full: str, rel_path: str, module: ModuleInfo, max_bytes: int):
    """Parse a file -> (tree, raw bytes); sets module.error (and returns (None, b"")) when it can't be read.

    5.3 edge cases: files over `max_bytes` are not parsed; the encoding comes from the BOM / PEP 263
    `# coding:` line like Python itself does; a file that is not valid in its declared encoding is
    read again as latin-1 (with a warning) so its structure is still mapped.
    """
    try:
        size = os.path.getsize(full)
        if size > max_bytes:
            module.error = f"FileTooLarge: {size / 1048576:.1f} MB, over the {max_bytes / 1048576:.0f} MB limit"
            return None, b""
        with open(full, "rb") as f:
            data = f.read()
    except OSError as exc:
        module.error = f"{type(exc).__name__}: {exc}"
        return None, b""
    module.line_count = data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
    try:
        try:
            encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)     # BOM / `# coding:` / utf-8
        except SyntaxError:                       # bad bytes in the first lines, or an unknown coding name
            encoding = "utf-8"
        try:
            text = data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            text = data.decode("latin-1")
            module.warnings.append(f"not valid {encoding} (the encoding it declares, or Python's default); "
                                   "read as latin-1, so non-ASCII text may look odd")
        if text.startswith("﻿"):
            text = text[1:]
        return ast.parse(text, filename=rel_path), data
    except (SyntaxError, UnicodeDecodeError, ValueError, RecursionError, MemoryError) as exc:
        module.error = f"{type(exc).__name__}: {exc}"
        return None, data


def analyze_module(root: str, rel_path: str, max_bytes: int = MAX_FILE_BYTES) -> ModuleInfo:
    """Parse one file and return its ModuleInfo."""
    module_name, is_package = module_name_from_path(rel_path, root)
    module = ModuleInfo(path=rel_path, module_name=module_name, is_package=is_package,
                        is_stub=rel_path.endswith(".pyi"))
    tree, data = _read_tree(os.path.join(root, rel_path), rel_path, module, max_bytes)
    if tree is None:
        return module
    try:
        _fill_module(module, tree, data.splitlines())
    except RecursionError:                      # absurdly deep nesting (generated code)
        module.error = "RecursionError: the file is nested too deeply to walk"
    return module


def _fill_module(module: ModuleInfo, tree: ast.Module, lines: List[bytes]):
    module.docstring = ast.get_docstring(tree)
    extractor = _FunctionExtractor(lines)
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
    # module variables: bindings in the main block count too (it runs at module level)
    for name, hs in main.hints.items():
        top.hints[name].extend(hs)
    top.stores.update(main.stores)
    module.module_scope = FunctionInfo(
        name=MODULE_SCOPE, qualified_name=MODULE_SCOPE, line=1, calls=top.calls, loops=top.loops,
        local_names=sorted(top.assigned | main.assigned), var_types=top.var_types())
    if main_line is not None:
        module.main_block = FunctionInfo(
            name=MAIN_SCOPE, qualified_name=MAIN_SCOPE, line=main_line,
            calls=main.calls, loops=main.loops, var_types=module.module_scope.var_types)


def analyze_project(root: str, ignore: Iterable[str] = (), warnings: Optional[List[str]] = None,
                    max_bytes: int = MAX_FILE_BYTES, skip_dirs: Iterable[str] = ()) -> List[ModuleInfo]:
    """Task 1 + 2 + 3 combined: scan the whole project.

    ignore    extra fnmatch patterns for folders / files to skip (on names and relative paths)
    warnings  if given, scanner warnings (skipped symlinks, ...) and per-file warnings are appended
    """
    modules = [analyze_module(root, p, max_bytes) for p in find_python_files(root, ignore, warnings, skip_dirs)]
    if warnings is not None:
        for m in modules:
            warnings.extend(f"{m.path.replace(os.sep, '/')}: {w}" for w in m.warnings)
    return modules


# ==================================================================================================
# Stage 2: symbol table, call resolution, light type inference
# ==================================================================================================
# Stage 2: project-wide symbol table and call resolution (purely static).
# Purely static. `self.method()` / `cls.method()` is resolved through the class
# hierarchy of the enclosing class. Light type inference (2.9) types a variable,
# parameter or instance attribute when the code says so unambiguously:
#   x = Foo()  /  x = make_foo()  (with `-> Foo`)  /  x: Foo  /  def f(db: Database)
#   self.db = Database()  /  self.db: Database  /  class-level `db: Database`
#   with Foo() as x
# A name bound to different things (or to something else as well) stays untyped.
# Calls resolved this way are marked `inferred` (one confidence level lower).

REASON_HELP = {
    "dynamic": "call on the result of an expression, subscript, lambda or module object",
    "variable": "call or attribute on a parameter / local / module variable (type unknown)",
    "name-not-found": "name is not defined in the module and not imported",
    "star-import": "name may come from a `from X import *` of a non-project module",
    "not-in-module": "name not found in a project module it was imported from",
    "member-not-found": "method not found on the class or its project base classes",
    "external-base": "method may be inherited from a base class outside the project",
    "self-attribute": "attribute of an instance attribute whose type is unknown (e.g. self.db.save())",
    "instance-attribute": "attribute of an inferred instance that is not a method and has no known type",
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
    kind: str               # "symbol" | "module" | "external" | "instance" | "unknown"
    target: str = ""        # for "instance": the full name of its class
    reason: str = ""        # reason code when kind == "unknown"
    note: str = ""
    inferred: bool = False  # depends on an inferred type (2.9)


@dataclass
class ResolutionStats:
    total: int = 0
    by_status: Counter = field(default_factory=Counter)
    by_reason: Counter = field(default_factory=Counter)
    external_kinds: Counter = field(default_factory=Counter)
    inferred: int = 0           # resolved local / internal calls that needed an inferred type

    def add(self, call: CallInfo):
        self.total += 1
        if call.inferred:
            self.inferred += 1
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
        self._inferred = False                       # set while resolving a call that used an inferred type
        self._type_cache: Dict[tuple, Optional[str]] = {}
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
            hint = m.module_scope.var_types.get(name) if m.module_scope else None
            inst = self._hint_instance(m, None, hint, depth + 1) if hint else None
            if inst is not None:
                return _Binding("instance", inst, note=f"`{name}` inferred as {inst}", inferred=True)
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
                hint = f.var_types.get(name)
                if hint is None and name not in f.local_names:      # a parameter never re-bound
                    hint = f.param_types.get(name)
                inst = self._hint_instance(m, f, hint, depth + 1) if hint else None
                if inst is not None:
                    return _Binding("instance", inst, note=f"`{name}` inferred as {inst}", inferred=True)
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
        if b.kind == "instance":
            member = self.find_member(b.target, part)
            if member is not None:
                owner = member.rsplit(".", 1)[0]
                note = f"inferred type {self.symbols[b.target].qualified_name}"
                if owner != b.target:
                    note += f", inherited from {owner}"
                return _Binding("symbol", member, note=note, inferred=True)
            inst = self._attr_instance(b.target, part, depth + 1)
            if inst is not None:
                return _Binding("instance", inst, note=f"`{part}` inferred as {inst}", inferred=True)
            if self._has_unknown_base(b.target, {b.target}):
                return _Binding("unknown", reason="external-base",
                                note=f"`{part}` not in {b.target}; may come from a base class outside the project")
            return _Binding("unknown", reason="instance-attribute",
                            note=f"`{part}` of a {b.target} instance is not a method and has no known type")
        if b.kind == "symbol":
            sym = self.symbols[b.target]
            if sym.kind == "class":
                member = self.find_member(b.target, part)
                if member is not None:
                    owner = member.rsplit(".", 1)[0]
                    return _Binding("symbol", member, note=f"inherited from {owner}" if owner != b.target else "",
                                    inferred=b.inferred)
                inst = self._attr_instance(b.target, part, depth + 1)
                if inst is not None:                       # self.db / Foo.registry with a known type
                    return _Binding("instance", inst, note=f"`{part}` inferred as {inst}", inferred=True)
                if self._has_unknown_base(b.target, {b.target}):
                    return _Binding("unknown", reason="external-base",
                                    note=f"`{part}` not in {b.target}; may come from a base class outside the project")
                return _Binding("unknown", reason="member-not-found",
                                note=f"`{part}` not found on {b.target} or its project base classes")
            return _Binding("unknown", reason="function-attribute",
                            note=f"attribute `{part}` of function `{b.target}`")
        return b

    # -- 2.9 light type inference ---------------------------------------------------- #
    def _annotation_class(self, m: ModuleInfo, text: str, owner: Optional[str], depth: int) -> Optional[str]:
        """Project class named by an annotation: `Foo`, `pkg.Foo`, `"Foo"`, `Optional[Foo]`, `Foo | None`,
        `Annotated[Foo, ...]`, `Self` (the owning class). Containers (`List[Foo]`) and `Type[Foo]` give None."""
        try:
            node = ast.parse(text.strip(), mode="eval").body
        except (SyntaxError, ValueError):
            return None
        node = _single_type(node)
        if node is None:
            return None
        parts = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if not isinstance(node, ast.Name):
            return None
        parts.append(node.id)
        parts.reverse()
        if parts in (["Self"], ["typing", "Self"], ["typing_extensions", "Self"]):
            return owner
        b = self._walk(m, None, parts, depth + 1)
        if b.kind == "symbol" and self.symbols[b.target].kind == "class":
            return b.target
        return None

    def _returned_class(self, fn_full: str, depth: int) -> Optional[str]:
        """Class an internal function / method returns, from its return annotation."""
        sym = self.symbols[fn_full]
        fn = self._fn_index.get((sym.module, sym.qualified_name))
        if fn is None or not fn.returns:
            return None
        owner = f"{sym.module}.{fn.enclosing_class}" if fn.enclosing_class else None
        return self._annotation_class(self.mod_by_name[sym.module], fn.returns, owner, depth + 1)

    def _hint_instance(self, m: ModuleInfo, fn: Optional[FunctionInfo], hint: str, depth: int,
                       owner: Optional[str] = None) -> Optional[str]:
        """Full name of the project class a type hint ("call:..." / "ann:...") stands for, or None."""
        if depth > self.MAX_DEPTH:
            return None
        if owner is None and fn is not None:
            owner, _ = self._enclosing_class(m, fn)
        key = (m.module_name, fn.qualified_name if fn else None, hint, owner)
        if key in self._type_cache:
            return self._type_cache[key]
        self._type_cache[key] = None                 # in progress: a self-referencing hint gives None
        result = None
        kind, _, text = hint.partition(":")
        if kind == "ann":
            result = self._annotation_class(m, text, owner, depth + 1)
        elif kind in ("call", "enter", "aenter"):
            parts = text.split(".")
            if owner is not None and parts[0] in ("self", "cls") and len(parts) > 1:
                b = self._class_chain(owner, parts[1:], depth + 1)
            else:
                b = self._walk(m, fn, parts, depth + 1)
            if b.kind == "symbol":
                sym = self.symbols[b.target]
                result = b.target if sym.kind == "class" else self._returned_class(b.target, depth + 1)
            if kind != "call" and result is not None:       # `with Foo() as x`: x = Foo().__enter__()
                enter = self.find_member(result, "__aenter__" if kind == "aenter" else "__enter__")
                if enter is not None:
                    returned = self._returned_class(enter, depth + 1)
                    enter_fn = self._fn_index.get((self.symbols[enter].module, self.symbols[enter].qualified_name))
                    if returned is not None:
                        result = returned
                    elif enter_fn is not None and enter_fn.returns:
                        result = None                       # annotated, but not with a project class
        self._type_cache[key] = result
        return result

    def _attr_instance(self, cls_full: str, attr: str, depth: int, _seen: Optional[Set[str]] = None) -> Optional[str]:
        """Type of instance / class attribute `attr` of a class (own hints first, then project bases)."""
        seen = _seen if _seen is not None else set()
        if cls_full in seen or depth > self.MAX_DEPTH:
            return None
        seen.add(cls_full)
        info = self._classes.get(cls_full)
        if info is not None and attr in info.attr_types:
            m = self.mod_by_name[self.symbols[cls_full].module]
            return self._hint_instance(m, None, info.attr_types[attr], depth + 1, owner=cls_full)
        for kind, ref in self._class_bases(cls_full):
            if kind == "project":
                found = self._attr_instance(ref, attr, depth + 1, seen)
                if found is not None:
                    return found
        return None

    def _class_chain(self, cls_full: str, attrs: List[str], depth: int) -> _Binding:
        """Binding of `self.a.b...` inside class `cls_full` (attrs = ["a", "b", ...])."""
        b = _Binding("symbol", cls_full)
        for part in attrs:
            b = self._attr(b, part, depth)
            if b.kind == "unknown":
                break
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
            self._inferred = self._inferred or b.inferred
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
        if b.kind == "instance":
            return "unresolved", None, "dynamic", f"a {b.target} instance is called (__call__ not tracked)"
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
        first = self._attr(_Binding("symbol", cls_full), parts[1], 0)
        if first.kind == "unknown" and len(parts) > 2:
            return ("unresolved", None, "self-attribute",
                    f"`{parts[0]}.{parts[1]}` is not a method of {cls_full}; "
                    f"it is an instance attribute or comes from outside the project")
        return self._binding_to_result(m, self._class_chain(cls_full, parts[1:], 0))

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
                    self._instantiated, self._inferred = None, False
                    call.status, call.target, call.reason, call.note = self._resolve(m, fn, call.name)
                    call.instantiates = self._instantiated
                    call.inferred = self._inferred and call.status in ("local", "internal")
                    self.stats.add(call)
        return self.stats


def resolve_project(modules: List[ModuleInfo]) -> Resolver:
    """Stage 2: build the symbol table and resolve all calls."""
    resolver = Resolver(modules)
    resolver.resolve_all()
    return resolver


_WRAPPERS = {"Optional", "Annotated", "ClassVar", "Final", "Required", "NotRequired", "ReadOnly"}


def _single_type(node: ast.AST, _depth: int = 0) -> Optional[ast.AST]:
    """Strip Optional / Union-with-None / Annotated / quotes; the one class expression left, or None."""
    if _depth > 5:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            return _single_type(ast.parse(node.value.strip(), mode="eval").body, _depth + 1)
        except (SyntaxError, ValueError):
            return None
    if isinstance(node, (ast.Name, ast.Attribute)):
        return node
    if isinstance(node, ast.Subscript):
        head = node.value.attr if isinstance(node.value, ast.Attribute) else getattr(node.value, "id", "")
        inner = node.slice
        elts = list(inner.elts) if isinstance(inner, ast.Tuple) else [inner]
        if head in _WRAPPERS:
            return _single_type(elts[0], _depth + 1)
        if head == "Union":
            return _one_not_none(elts, _depth)
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        elts, todo = [], [node]
        while todo:
            n = todo.pop()
            if isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr):
                todo += [n.right, n.left]
            else:
                elts.append(n)
        return _one_not_none(elts, _depth)
    return None


def _one_not_none(elts: List[ast.AST], depth: int) -> Optional[ast.AST]:
    rest = [e for e in elts if not (isinstance(e, ast.Constant) and e.value is None)
            and not (isinstance(e, ast.Name) and e.id == "None")]
    return _single_type(rest[0], depth + 1) if len(rest) == 1 else None


# ==================================================================================================
# Stage 3: call graph and import graph (export / load / queries)
# ==================================================================================================
# Stage 3: call graph and import graph as plain data, plus export / load / queries.
# Two graphs, kept as plain data (no AST objects) so they can be saved as JSON
# and queried later without parsing the code again:
#   call graph    nodes = functions / methods / classes (+ "<module>" / "<main>" scopes)
#                 edges = resolved local / internal calls, with every call site
#   import graph  nodes = project modules, edges = project-internal imports
# Everything is sorted and the JSON holds no timestamps or absolute paths, so
# two runs on the same code give byte-identical files.


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
def build_call_graph(resolver: Resolver) -> Graph:
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
        if m.is_stub:
            attrs["stub"] = True
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
                    if c.inferred:
                        site["inferred"] = True
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
def build_import_graph(resolver: Resolver) -> Graph:
    """Nodes: project modules. Edges: imports that point at another project module.

    `import a.b.c` is an edge to a.b.c only (the parent packages that Python also runs are not added).
    A folder without __init__.py (namespace package) gets a node of kind "namespace" when something
    imports it directly (`import nspkg`, `from nspkg import sub` where sub is not a module).
    """
    g = Graph("import")
    mods = [resolver.mod_by_name[n] for n in sorted(resolver.mod_by_name)]
    for m in mods:
        g.add_node(m.module_name, kind="package" if m.is_package else "module", path=_rel(m.path))
    for m in mods:
        for imp in m.imports:
            dst = imp.abs_module
            if imp.origin == "internal" and dst and dst not in g.nodes and dst in resolver._prefixes:
                g.add_node(dst, kind="namespace", path=_rel(dst.replace(".", "/")))
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


def build_graphs(resolver: Resolver) -> Dict[str, Graph]:
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


# ==================================================================================================
# Stage 4: analyzers (cycles, recursion, loops, entry points, dead code, imports, metrics)
# ==================================================================================================
# Stage 4: analyzers on the saved graph data (cycles, recursion, loops, entry points,
# dead code, imports, metrics), every finding labelled certain / likely / uncertain.
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
    self. / cls. / super() (the call may really reach an override) or an inferred type (2.9)."""
    sites = edge.get("sites", [])
    if only_loop_sites:
        sites = [s for s in sites if s.get("loop_depth", 0) > 0]
    for s in sites:
        if not s.get("name", "").startswith(SELF_RECEIVERS) and not s.get("inferred"):
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
        if a.get("stub"):
            return "declarations in .pyi stubs"
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
def find_import_issues(resolver: Resolver) -> List[dict]:
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
        "Call edges are a lower bound: light type inference resolves `x = Foo(); x.run()`, annotated "
        "parameters and typed `self.attr`, but calls on values of unknown type are not edges. Dead-code "
        "findings are labelled with that in mind; read `uncertain` as 'check by hand'.",
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


# ==================================================================================================
# Report (markdown + JSON)
# ==================================================================================================
# Markdown output: the analysis section and the full per-module report.
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


def _coverage_lines(resolver: Resolver) -> List[str]:
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
        f"  - of the local / internal ones, resolved through an inferred type: {st.inferred}",
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
        lines += [f"- `{_rel(path)}` (module `{name}`)" for name, path in resolver.duplicate_modules]
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
                 resolver: Optional[Resolver] = None,
                 graphs: Optional[Dict[str, Graph]] = None,
                 analysis: Optional[dict] = None,
                 diff: Optional[dict] = None,
                 warnings: Optional[List[str]] = None) -> str:
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
    if diff is not None:
        lines.append(f"- **{diff_summary_line(diff)}**")
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
            f"| `{_rel(m.path)}` | `{m.module_name}` | {len(m.imports)} | {len(m.classes)} "
            f"| {len(m.functions)} | {m.loop_count()} | {status} |")
    lines.append("")
    if warnings:
        lines += ["## Warnings", ""] + [f"- {_cell(w)}" for w in warnings] + [""]
    if diff is not None:
        lines += diff_lines(diff)
    if resolver is not None:
        lines += _coverage_lines(resolver)
    if analysis is not None:
        lines += analysis_lines(analysis, limit=REPORT_ANALYSIS_LIMIT)

    for m in modules:
        lines += [f"## Module: `{_rel(m.path)}`", ""]
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
def build_report_data(root: str, modules: List[ModuleInfo], generated_at: datetime,
                      resolver: Resolver, graphs: Dict[str, Graph], analysis: Optional[dict] = None,
                      diff: Optional[dict] = None, warnings: Optional[List[str]] = None) -> dict:
    """The report as data: per-module summary, resolution coverage, analysis, diff
    (its totals and coverage are reused by result_to_dict)."""
    st = resolver.stats
    return {
        "report_schema_version": 1,
        "tool": "code_mapper",
        "tool_version": TOOL_VERSION,
        "project": os.path.basename(os.path.normpath(root)),
        "generated_at": generated_at.strftime("%Y-%m-%d %H:%M:%S"),
        "totals": {
            "modules": len(modules), "modules_with_errors": sum(1 for m in modules if m.error),
            "lines": sum(m.line_count for m in modules),
            "classes": sum(len(m.classes) for m in modules), "functions": sum(len(m.functions) for m in modules),
            "imports": sum(len(m.imports) for m in modules), "loops": sum(m.loop_count() for m in modules),
        },
        "resolution": {
            "calls": st.total, "resolved": st.resolved(), "percent": round(st.percent(), 1),
            "by_status": dict(sorted(st.by_status.items())), "unresolved_reasons": dict(sorted(st.by_reason.items())),
            "external_kinds": dict(sorted(st.external_kinds.items())), "through_inferred_types": st.inferred,
        },
        "graphs": {k: {"nodes": len(g.nodes), "edges": len(g.edges)} for k, g in sorted(graphs.items())},
        "modules": [{
            "path": _rel(m.path), "module": m.module_name, "package": m.is_package, "lines": m.line_count,
            "error": m.error, "docstring": bool(m.docstring), "imports": len(m.imports), "classes": len(m.classes),
            "functions": len(m.functions), "loops": m.loop_count(), "warnings": list(m.warnings),
        } for m in modules],
        "analysis": analysis,
        "diff": diff,
        "warnings": list(warnings or []),
    }


def write_report(content: str, generated_at: datetime, output_dir: Optional[str] = None, ext: str = "md") -> str:
    """Save to <output>/<YYYY-MM-DD>/report_<HH-MM-SS>.<ext> and return the path.

    The default output folder is reports/ next to code_mapper.py, NOT inside the scanned project.
    """
    day_dir = os.path.join(output_dir or os.path.join(TOOL_DIR, REPORTS_DIR_NAME), generated_at.strftime("%Y-%m-%d"))
    os.makedirs(day_dir, exist_ok=True)
    path = os.path.join(day_dir, f"report_{generated_at.strftime('%H-%M-%S')}.{ext}")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content if content.endswith("\n") else content + "\n")
    return path


# ==================================================================================================
# Stage 6.1: run snapshots and diffs
# ==================================================================================================
# Stage 6.1: a snapshot of every run, and the difference between two runs.
#
# A snapshot is a compact JSON summary of one scan: modules, symbols (with signature and a
# fingerprint of their source lines), call / import edges and the findings. Snapshots live in
#
#     <output>/history/<project-key>/snapshot_<YYYY-MM-DD>_<HH-MM-SS>.json
#
# so each scan can be compared with the one before it ("what changed since last time?").
# A function counts as changed when its signature or its source lines changed; moving it
# (only its line number changes) is not a change.
SNAPSHOT_SCHEMA_VERSION = 1
HISTORY_DIR_NAME = "history"
DIFF_LIST_LIMIT = 30                  # rows per list in the markdown diff (the JSON has everything)


def _signature(fn) -> str:
    text = f"{'async ' if fn.is_async else ''}def {fn.name}({', '.join(fn.args)})"
    return text + (f" -> {fn.returns}" if fn.returns else "")


def build_snapshot(result, generated_at: datetime) -> dict:
    """Snapshot of one pipeline result (see run_pipeline)."""
    modules, symbols = {}, {}
    for m in sorted(result.modules, key=lambda m: m.path):
        entry = {"path": _rel(m.path), "lines": m.line_count}
        if m.error:
            entry["error"] = m.error
        modules.setdefault(m.module_name, entry)
        if m.error or result.resolver.mod_by_name.get(m.module_name) is not m:
            continue
        for c in m.classes:
            symbols[f"{m.module_name}.{c.qualified_name}"] = {
                "kind": "class", "path": _rel(m.path), "line": c.line,
                "signature": f"class {c.name}({', '.join(c.bases)})" if c.bases else f"class {c.name}"}
        for fn in m.functions:
            symbols.setdefault(f"{m.module_name}.{fn.qualified_name}", {
                "kind": "method" if fn.enclosing_class else "function", "path": _rel(m.path), "line": fn.line,
                "signature": _signature(fn), "fingerprint": fn.fingerprint})
    cg, ig = result.graphs["call"], result.graphs["import"]
    findings: Dict[str, list] = {}
    a = result.analysis
    if a is not None:
        findings = {
            "dead_code": sorted(f"{f['id']} [{f['confidence']}]" for f in a["dead_code"]),
            "import_cycles": sorted(f"{' <-> '.join(c['members'])} [{c['kind']}]" for c in a["cycles"]["import"]),
            "call_cycles": sorted(" <-> ".join(c["members"]) for c in a["cycles"]["call"]),
            "direct_recursion": sorted(d["id"] for d in a["recursion"]["direct"]),
            "calls_in_loops": sorted(f"{r['caller']} -> {r['callee']}" for r in a["loops"]["calls_in_loops"]),
        }
        if a.get("imports") is not None:
            findings["unused_imports"] = sorted(f"{i['module']}: {i['statement']}" for i in a["imports"]["unused"])
            findings["missing_modules"] = sorted(f"{i['module']}: {i['statement']}" for i in a["imports"]["missing"])
    st = result.resolver.stats
    return {
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "project": os.path.basename(os.path.normpath(result.root)),
        "generated_at": generated_at.strftime("%Y-%m-%d %H:%M:%S"),
        "stats": {
            "modules": len(result.modules),
            "modules_with_errors": sum(1 for m in result.modules if m.error),
            "lines": sum(m.line_count for m in result.modules),
            "classes": sum(1 for s in symbols.values() if s["kind"] == "class"),
            "functions": sum(1 for s in symbols.values() if s["kind"] != "class"),
            "calls": st.total,
            "calls_resolved_percent": round(st.percent(), 1),
            "call_graph_edges": len(cg.edges),
            "import_graph_edges": len(ig.edges),
            "dead_code": len(a["dead_code"]) if a else None,
        },
        "modules": modules,
        "symbols": dict(sorted(symbols.items())),
        "call_edges": sorted(f"{s} -> {d}" for s, d in cg.edges),
        "import_edges": sorted(f"{s} -> {d}" for s, d in ig.edges),
        "findings": findings,
    }


# -- storage -------------------------------------------------------------------------- #
def project_key(root: str) -> str:
    """Folder name for a project's history: its name plus a short hash of its absolute path
    (two different projects with the same folder name don't share a history)."""
    real = os.path.normcase(os.path.realpath(root))
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", os.path.basename(real.rstrip("\\/")) or "project")
    return f"{name}-{hashlib.sha1(real.encode('utf-8')).hexdigest()[:8]}"


def history_dir(output_dir: str, root: str) -> str:
    return os.path.join(output_dir, HISTORY_DIR_NAME, project_key(root))


def list_snapshots(output_dir: str, root: str) -> List[str]:
    folder = history_dir(output_dir, root)
    if not os.path.isdir(folder):
        return []
    return [os.path.join(folder, f) for f in sorted(os.listdir(folder))
            if f.startswith("snapshot_") and f.endswith(".json")]


def save_snapshot(snapshot: dict, output_dir: str, root: str, generated_at: datetime) -> str:
    folder = history_dir(output_dir, root)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"snapshot_{generated_at.strftime('%Y-%m-%d_%H-%M-%S')}.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(snapshot, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    return path


def load_snapshot(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("snapshot_schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError(f"{path}: not a code_mapper snapshot (schema "
                         f"{data.get('snapshot_schema_version')!r}, expected {SNAPSHOT_SCHEMA_VERSION})")
    return data


# -- diff --------------------------------------------------------------------------- #
def _added_removed(old: List[str], new: List[str]) -> dict:
    o, n = set(old), set(new)
    return {"added": sorted(n - o), "removed": sorted(o - n)}


def diff_snapshots(old: dict, new: dict) -> dict:
    """What changed from snapshot `old` to snapshot `new`."""
    osym, nsym = old.get("symbols", {}), new.get("symbols", {})
    changed = []
    for sid in sorted(set(osym) & set(nsym)):
        a, b = osym[sid], nsym[sid]
        if a.get("signature") != b.get("signature"):
            changed.append({"id": sid, "what": "signature", "old": a.get("signature"), "new": b.get("signature"),
                            "path": b.get("path"), "line": b.get("line")})
        elif a.get("fingerprint") != b.get("fingerprint"):
            changed.append({"id": sid, "what": "body", "path": b.get("path"), "line": b.get("line")})
    findings = {}
    for cat in sorted(set(old.get("findings", {})) | set(new.get("findings", {}))):
        ar = _added_removed(old.get("findings", {}).get(cat, []), new.get("findings", {}).get(cat, []))
        findings[cat] = {"new": ar["added"], "gone": ar["removed"]}
    stats = {k: [old.get("stats", {}).get(k), v] for k, v in new.get("stats", {}).items()
             if old.get("stats", {}).get(k) != v}
    diff = {
        "from": old.get("generated_at"), "to": new.get("generated_at"), "project": new.get("project"),
        "modules": _added_removed(list(old.get("modules", {})), list(new.get("modules", {}))),
        "symbols": dict(_added_removed(list(osym), list(nsym)), changed=changed),
        "call_edges": _added_removed(old.get("call_edges", []), new.get("call_edges", [])),
        "import_edges": _added_removed(old.get("import_edges", []), new.get("import_edges", [])),
        "findings": findings,
        "stats": stats,
    }
    diff["summary"] = {
        "modules_added": len(diff["modules"]["added"]), "modules_removed": len(diff["modules"]["removed"]),
        "symbols_added": len(diff["symbols"]["added"]), "symbols_removed": len(diff["symbols"]["removed"]),
        "symbols_changed": len(changed),
        "call_edges_added": len(diff["call_edges"]["added"]),
        "call_edges_removed": len(diff["call_edges"]["removed"]),
        "import_edges_added": len(diff["import_edges"]["added"]),
        "import_edges_removed": len(diff["import_edges"]["removed"]),
        "new_findings": sum(len(v["new"]) for v in findings.values()),
        "gone_findings": sum(len(v["gone"]) for v in findings.values()),
    }
    return diff


def diff_is_empty(diff: dict) -> bool:
    return not any(diff["summary"].values())


def diff_summary_line(diff: dict) -> str:
    s = diff["summary"]
    if diff_is_empty(diff):
        return f"No changes since {diff['from']}"
    parts = [f"+{s['symbols_added']} / -{s['symbols_removed']} / ~{s['symbols_changed']} functions & classes",
             f"+{s['call_edges_added']} / -{s['call_edges_removed']} call edges",
             f"+{s['import_edges_added']} / -{s['import_edges_removed']} import edges",
             f"{s['new_findings']} new / {s['gone_findings']} fixed findings"]
    if s["modules_added"] or s["modules_removed"]:
        parts.insert(0, f"+{s['modules_added']} / -{s['modules_removed']} modules")
    return f"Since {diff['from']}: " + ", ".join(parts)


def _bullets(items: List[str], limit: Optional[int], fmt=lambda x: f"`{x}`") -> List[str]:
    shown = items if limit is None else items[:limit]
    out = [f"- {fmt(i)}" for i in shown]
    if limit is not None and len(items) > limit:
        out.append(f"- _... and {len(items) - limit} more (diff.json has the full list)_")
    return out


def diff_lines(diff: dict, limit: Optional[int] = DIFF_LIST_LIMIT, heading: str = "##") -> List[str]:
    """Markdown for a diff."""
    lines = [f"{heading} Changes since the previous run", "",
             f"Compared with the run of **{diff['from']}** (this run: {diff['to']}).", ""]
    if diff_is_empty(diff):
        return lines + ["_Nothing changed: same modules, functions, edges and findings._", ""]
    lines += [f"**{diff_summary_line(diff)}**", ""]
    if diff["stats"]:
        lines += ["| Measure | Before | Now |", "|---|---:|---:|"]
        for k, (a, b) in sorted(diff["stats"].items()):
            lines.append(f"| {k.replace('_', ' ')} | {a} | {b} |")
        lines.append("")
    sections = [
        ("Modules added", diff["modules"]["added"]), ("Modules removed", diff["modules"]["removed"]),
        ("Functions / classes added", diff["symbols"]["added"]),
        ("Functions / classes removed", diff["symbols"]["removed"]),
    ]
    for title, items in sections:
        if items:
            lines += [f"**{title}** ({len(items)}):", ""] + _bullets(items, limit) + [""]
    changed = diff["symbols"]["changed"]
    if changed:
        lines += [f"**Functions / classes changed** ({len(changed)}):", ""]
        for c in (changed if limit is None else changed[:limit]):
            if c["what"] == "signature":
                lines.append(f"- `{c['id']}`: signature `{c['old']}` -> `{c['new']}`")
            else:
                lines.append(f"- `{c['id']}`: body changed")
        if limit is not None and len(changed) > limit:
            lines.append(f"- _... and {len(changed) - limit} more_")
        lines.append("")
    for title, key in (("Call edges", "call_edges"), ("Import edges", "import_edges")):
        for verb in ("added", "removed"):
            items = diff[key][verb]
            if items:
                lines += [f"**{title} {verb}** ({len(items)}):", ""] + _bullets(items, limit) + [""]
    for cat, ch in diff["findings"].items():
        name = cat.replace("_", " ")
        if ch["new"]:
            lines += [f"**New {name}** ({len(ch['new'])}):", ""] + _bullets(ch["new"], limit) + [""]
        if ch["gone"]:
            lines += [f"**{name.capitalize()} no longer found** ({len(ch['gone'])}):", ""] + \
                     _bullets(ch["gone"], limit) + [""]
    return lines


# ==================================================================================================
# Stage 6.2 / 6.3: onboarding dossier and module pages
# ==================================================================================================
# Stage 6.2 / 6.3: onboarding dossier and per-module pages.
#
#     dossier_<time>/dossier.md           one document a new developer reads first
#     dossier_<time>/modules/<name>.md    one page per module: what it holds, what it uses, who uses it
#
# Everything comes from the rule-based engine (parser, graphs, analyzers); nothing is guessed by AI.
MAX_COMPONENTS = 25        # architecture view: collapse packages until at most this many boxes
FLOW_CANDIDATES = 40       # entry points considered for the main flows (reach is computed for these only)
FLOW_ENTRIES = 8           # main flows shown
FLOW_DEPTH = 3             # call-tree depth per flow
FLOW_CHILDREN = 6          # callees shown per node
TOP = 10
ENTRY_PRIORITY = {"main-module": 0, "main-block": 1, "main-function": 2, "handler": 3, "exported": 4, "test": 9}


def _doc_summary(doc: Optional[str], limit: int = 160) -> str:
    """First paragraph of a docstring on one line (cut at `limit` characters)."""
    if not doc or not doc.strip():
        return ""
    para = " ".join(doc.strip().split("\n\n")[0].split())
    return para if len(para) <= limit else para[:limit - 3].rsplit(" ", 1)[0] + "..."


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def _page_name(module_name: str) -> str:
    return f"{module_name}.md"


def _link(module_name: str, prefix: str = "modules/") -> str:
    return f"[`{module_name}`]({prefix}{_page_name(module_name)})"


class _Facts:
    """Lookups shared by the dossier and the module pages."""

    def __init__(self, result):
        self.r = result
        self.modules = [m for m in result.modules
                        if not m.error and result.resolver.mod_by_name.get(m.module_name) is m]
        self.broken = [m for m in result.modules if m.error]
        self.mod = {m.module_name: m for m in self.modules}
        self.cg: Graph = result.graphs["call"]
        self.ig: Graph = result.graphs["import"]
        self.a = result.analysis or {}
        self.entries = [e for e in self.a.get("entry_points", [])]
        self.fn_info = {}
        for m in self.modules:
            for fn in m.functions:
                self.fn_info[f"{m.module_name}.{fn.qualified_name}"] = (m, fn)

    def module_of(self, node_id: str) -> str:
        return self.cg.nodes.get(node_id, {}).get("module") or node_id.rsplit(".", 1)[0]

    def size(self, node_id: str) -> int:
        info = self.fn_info.get(node_id)
        return info[1].end_line - info[1].line + 1 if info and info[1].end_line else 0


# -- 6.2 dossier ------------------------------------------------------------------- #
def _components(f: _Facts) -> Tuple[Dict[str, str], int]:
    """Collapse modules into components: the deepest package level with at most MAX_COMPONENTS groups;
    when that leaves only 1-3 groups (one big package), one level deeper even if it has more."""
    names = sorted(f.mod)
    best, level = {n: n.split(".")[0] for n in names}, 1
    max_depth = max((n.count(".") + 1 for n in names), default=1)
    for lvl in range(1, max_depth + 1):
        mapping = {n: ".".join(n.split(".")[:lvl]) for n in names}
        count = len(set(mapping.values()))
        if count > MAX_COMPONENTS and not (len(set(best.values())) <= 3 and count <= 2 * MAX_COMPONENTS):
            break
        best, level = mapping, lvl
        if count > MAX_COMPONENTS:
            break
    return best, level


def _overview(f: _Facts, project: str) -> List[str]:
    a, st = f.a, f.r.resolver.stats
    entries = [e for e in f.entries if e["type"] != "test"]
    tests = [e for e in f.entries if e["type"] == "test"]
    n_classes = sum(len(m.classes) for m in f.modules)
    n_funcs = sum(len(m.functions) for m in f.modules)
    lines = ["## 1. At a glance", "",
             "| | |", "|---|---|",
             f"| Modules | {len(f.modules)} ({_plural(sum(1 for m in f.modules if m.is_package), 'package')})"
             + (f", {len(f.broken)} could not be parsed" if f.broken else "") + " |",
             f"| Lines of Python | {sum(m.line_count for m in f.modules):,} |",
             f"| Classes / functions and methods | {n_classes} / {n_funcs} |",
             f"| Entry points | {len(entries)} (plus {len(tests)} tests and fixtures) |",
             f"| Calls resolved | {st.resolved()} of {st.total} ({st.percent():.1f}%) |"]
    if a:
        s = a["summary"]["findings"]
        lines.append(f"| Findings | {s['import cycles']['total']} import cycles, {s['call cycles']['total']} call "
                     f"cycles, {s['dead code']['total']} dead-code candidates"
                     + (f", {s['unused imports']['total']} unused imports" if "unused imports" in s else "") + " |")
    lines.append("")
    tops = defaultdict(list)
    for m in f.modules:
        tops[m.module_name.split(".")[0]].append(m)
    lines += ["**Top-level layout:**", "", "| Package / module | Modules | Lines | What it is |", "|---|---:|---:|---|"]
    for top in sorted(tops):
        mods = tops[top]
        head = f.mod.get(top)
        doc = _doc_summary(head.docstring) if head else ""
        lines.append(f"| {_link(top) if head else f'`{top}`'} | {len(mods)} | {sum(m.line_count for m in mods):,} "
                     f"| {_cell(doc) or '_no docstring_'} |")
    return lines + [""]


def _entry_section(f: _Facts) -> List[str]:
    lines = ["## 2. Where execution starts", ""]
    groups = defaultdict(list)
    for e in f.entries:
        groups[e["type"]].append(e)
    titles = {"main-module": "`python -m` modules", "main-block": "`if __name__ == \"__main__\"` blocks",
              "main-function": "`main()` functions", "handler": "Handlers registered by decorators",
              "exported": "Public API (`__all__`)", "test": "Tests and fixtures"}
    if not f.entries:
        return lines + ["_No entry points found: this looks like a library without scripts, tests or `__all__`._",
                        ""]
    for kind in sorted(groups, key=lambda k: ENTRY_PRIORITY.get(k, 5)):
        items = groups[kind]
        if kind == "test":
            mods = sorted({f.module_of(e["id"]) for e in items})
            lines += [f"**{titles[kind]}:** {len(items)} in {len(mods)} modules "
                      f"({', '.join(f'`{m}`' for m in mods[:8])}{', ...' if len(mods) > 8 else ''})", ""]
            continue
        lines += [f"**{titles.get(kind, kind)}** ({len(items)}):", ""]
        for e in items[:15]:
            lines.append(f"- `{e['id']}` ({e['path']}:{e['line']}) - {e['detail']}")
        if len(items) > 15:
            lines.append(f"- _... and {len(items) - 15} more_")
        lines.append("")
    return lines


def _flow_tree(f: _Facts, start: str, seen: set) -> List[str]:
    out = []

    def walk(node: str, depth: int):
        kids = [k for k in f.cg.successors(node) if k != node]
        kids.sort(key=lambda k: (-len(f.cg.successors(k)), k))
        for kid in kids[:FLOW_CHILDREN]:
            mark = ""
            if kid in seen:
                mark = " _(already shown)_"
            elif f.cg.edge(node, kid) and f.cg.edge(node, kid).get("in_loop"):
                mark = " _(in a loop)_"
            out.append(f"{'  ' * depth}- `{kid}`{mark}")
            if kid not in seen:
                seen.add(kid)
                if depth + 1 < FLOW_DEPTH:
                    walk(kid, depth + 1)
        if len(kids) > FLOW_CHILDREN:
            out.append(f"{'  ' * depth}- _... and {len(kids) - FLOW_CHILDREN} more calls_")

    seen.add(start)
    walk(start, 0)
    return out


def _flows(f: _Facts) -> List[str]:
    lines = ["## 3. Main flows", "",
             "What each entry point calls inside the project (resolved calls only, "
             f"{FLOW_DEPTH} levels, busiest callees first).", ""]
    candidates = sorted((e for e in f.entries if e["type"] != "test" and e["id"] in f.cg.nodes
                         and f.cg.successors(e["id"])),
                        key=lambda e: (ENTRY_PRIORITY.get(e["type"], 5), e["id"]))[:FLOW_CANDIDATES]
    reach_of = {e["id"]: len(f.cg.reach(e["id"], "out", 0)) for e in candidates}
    starts = sorted(candidates, key=lambda e: (ENTRY_PRIORITY.get(e["type"], 5), -reach_of[e["id"]], e["id"]))
    shown, seen = set(), set()
    for e in starts:
        if e["id"] in shown or len(shown) >= FLOW_ENTRIES:
            continue
        shown.add(e["id"])
        lines += [f"**`{e['id']}`** ({e['type']}, reaches {reach_of[e['id']]} functions)", ""]
        lines += _flow_tree(f, e["id"], seen) + [""]
    if not shown:
        # a library without scripts / __all__: start from the public functions that reach the most code
        public = [n for n, a in f.cg.nodes.items() if a.get("kind") in ("function", "method")
                  and not any(p.startswith("_") for p in a.get("qualified_name", "_").split("."))
                  and not a.get("stub") and f.cg.successors(n)]
        public.sort(key=lambda n: (-len([s for s in f.cg.successors(n) if s != n]), n))
        reach_of = {n: len(f.cg.reach(n, "out", 0)) for n in public[:FLOW_CANDIDATES]}
        best = sorted(reach_of, key=lambda n: (-reach_of[n], n))[:min(FLOW_ENTRIES, 5)]
        if best:
            lines += ["_No entry point calls into the project's own code, so here are the public functions that "
                      "reach the most of it (a library's main operations)._", ""]
        for n in best:
            lines += [f"**`{n}`** (public, reaches {reach_of[n]} functions)", ""]
            lines += _flow_tree(f, n, seen) + [""]
        if not best:
            lines += ["_No entry point or public function calls into the project's own code._", ""]
    return lines


def _architecture(f: _Facts) -> List[str]:
    comp, level = _components(f)
    members = defaultdict(list)
    for m, c in comp.items():
        members[c].append(m)
    edges = Counter()
    for (src, dst), e in f.ig.edges.items():
        cs, cd = comp.get(src), comp.get(dst)
        if cs and cd and cs != cd:
            edges[(cs, cd)] += e["count"]
    succ = defaultdict(list)
    for (a, b) in sorted(edges):
        succ[a].append(b)
    order = _scc(sorted(members), lambda n: succ.get(n, []))       # foundations (no internal deps) first
    in_cycle = {n for c in order if len(c) > 1 for n in c}
    lines = ["## 4. Architecture", "",
             f"Modules grouped by the first {_plural(level, 'part')} of their dotted name, and how the "
             "groups import each other. Listed foundations first: a group only depends on groups above it, "
             "unless it is marked as part of a cycle.", ""]
    if len(members) > 1 and edges:
        alias = {c: f"c{i}" for i, c in enumerate(sorted(members))}
        lines += ["```mermaid", "flowchart LR"]
        for c in sorted(members):
            lines.append(f'    {alias[c]}["{c} ({len(members[c])})"]')
        for (a, b), n in sorted(edges.items()):
            lines.append(f"    {alias[a]} -->|{n}| {alias[b]}")
        lines += ["```", ""]
    lines += ["| Group | Modules | Lines | Depends on | Used by |", "|---|---:|---:|---|---|"]
    used_by = defaultdict(set)
    for (a, b) in edges:
        used_by[b].add(a)
    for comp_list in order:
        for c in comp_list:
            lines_count = sum(f.mod[m].line_count for m in members[c])
            deps = ", ".join(f"`{d}`" for d in succ.get(c, [])) or "-"
            users = ", ".join(f"`{u}`" for u in sorted(used_by[c])) or "-"
            flag = " (cycle)" if c in in_cycle else ""
            lines.append(f"| `{c}`{flag} | {len(members[c])} | {lines_count:,} | {deps} | {users} |")
    return lines + [""]


def _key_modules(f: _Facts) -> List[str]:
    rows = []
    for name, m in f.mod.items():
        fan_in = len([p for p in f.ig.predecessors(name) if p != name])
        fan_out = len([s for s in f.ig.successors(name) if s != name])
        rows.append((fan_in, m.line_count, name, fan_out, m))
    rows.sort(key=lambda r: (-r[0], -r[1], r[2]))
    lines = ["## 5. Key modules", "", "Most imported first (other modules depend on them), then the biggest.", "",
             "| Module | Imported by | Imports | Lines | Functions | Purpose |", "|---|---:|---:|---:|---:|---|"]
    for fan_in, loc, name, fan_out, m in rows[:TOP]:
        lines.append(f"| {_link(name)} | {fan_in} | {fan_out} | {loc:,} | {len(m.functions)} | "
                     f"{_cell(_doc_summary(m.docstring)) or '_no docstring_'} |")
    return lines + [""]


def _hotspots(f: _Facts) -> List[str]:
    funcs = [n for n, a in f.cg.nodes.items() if a.get("kind") in ("function", "method")]
    fan_in = {n: len([p for p in f.cg.predecessors(n) if p != n]) for n in funcs}
    fan_out = {n: len([s for s in f.cg.successors(n) if s != n]) for n in funcs}
    lines = ["## 6. Hot spots", ""]

    def table(title: str, hint: str, values: Dict[str, int], label: str):
        rows = sorted(((n, v) for n, v in values.items() if v > 0), key=lambda kv: (-kv[1], kv[0]))[:TOP]
        if not rows:
            return []
        out = [f"**{title}** - {hint}", "", f"| Function | {label} | Where |", "|---|---:|---|"]
        for n, v in rows:
            a = f.cg.nodes[n]
            out.append(f"| `{n}` | {v} | {a.get('path')}:{a.get('line')} |")
        return out + [""]

    lines += table("Most called", "central code: a change here affects many callers", fan_in, "Callers")
    lines += table("Calls the most", "coordinators: read these to see how parts fit together", fan_out, "Callees")
    lines += table("Largest functions", "candidates for splitting", {n: f.size(n) for n in funcs}, "Lines")
    nested = f.a.get("loops", {}).get("nested", [])
    if nested:
        lines += ["**Deepest nested loops** - check these for performance", "",
                  "| Scope | Loops | Max depth |", "|---|---:|---:|"]
        lines += [f"| `{r['id']}` | {r['loops']} | {r['max_depth']} |" for r in nested[:TOP]] + [""]
    return lines


def _problems(f: _Facts) -> List[str]:
    a = f.a
    lines = ["## 7. Known problems", ""]
    if not a:
        return lines + ["_Analysis was skipped for this run._", ""]
    ic, cc = a["cycles"]["import"], a["cycles"]["call"]
    lines += [f"**Import cycles:** {len(ic) or 'none'}", ""]
    for c in ic[:TOP]:
        lines.append(f"- {c['kind']} ({c['confidence']}): " + " -> ".join(f"`{n}`" for n in c["example_cycle"]))
    lines += ([""] if ic else []) + [f"**Call cycles (mutual recursion):** {len(cc) or 'none'}", ""]
    for c in cc[:TOP]:
        lines.append(f"- {c['confidence']}: " + " -> ".join(f"`{n}`" for n in c["example_cycle"]))
    dead = a["dead_code"]
    by = Counter(d["confidence"] for d in dead)
    lines += ([""] if cc else []) + [
        f"**Dead code candidates:** {len(dead)} ({by.get('certain', 0)} certain, {by.get('likely', 0)} likely, "
        f"{by.get('uncertain', 0)} uncertain)", ""]
    for d in [d for d in dead if d["confidence"] != "uncertain"][:15]:
        lines.append(f"- {d['confidence']}: `{d['id']}` ({d['path']}:{d['line']})")
    if a.get("imports"):
        un, mi = a["imports"]["unused"], a["imports"]["missing"]
        lines += ["", f"**Unused imports:** {len(un)}; **imports of missing project modules:** {len(mi)}", ""]
        for i in mi[:TOP]:
            lines.append(f"- missing: `{i['statement']}` in `{i['module']}` (line {i['line']})")
    if f.broken:
        lines += ["", f"**Files that could not be parsed:** {len(f.broken)}", ""]
        lines += [f"- `{_rel(m.path)}`: {m.error}" for m in f.broken[:TOP]]
    return lines + ["", "_Full details: the report and analysis.json of this run._", ""]


def _reading_order(f: _Facts) -> List[str]:
    """Top-down: modules holding entry points first, then what they import (breadth-first)."""
    lines = ["## 8. Suggested reading order", ""]
    start = []
    for e in sorted(f.entries, key=lambda e: (ENTRY_PRIORITY.get(e["type"], 5), e["id"])):
        if e["type"] in ("test", "exported"):
            continue
        mod = f.module_of(e["id"])
        if mod in f.mod and mod not in start:
            start.append(mod)
    if not start:                                   # a library: start from the modules nothing imports
        start = sorted((n for n in f.mod if not f.ig.predecessors(n)), key=lambda n: (-f.mod[n].line_count, n))[:3]
        label = "top of the package (no other module imports it)"
    else:
        label = "entry point"
    order, why, queue = [], {}, list(start)
    for s in start:
        why[s] = label
    while queue and len(order) < 20:
        cur = queue.pop(0)
        if cur in order:
            continue
        order.append(cur)
        for dep in f.ig.successors(cur):
            if dep in f.mod and dep not in why:
                why[dep] = f"used by `{cur}`"
                queue.append(dep)
    for i, n in enumerate(order, 1):
        lines.append(f"{i}. {_link(n)} - {why[n]}"
                     + (f": {_cell(_doc_summary(f.mod[n].docstring))}" if f.mod[n].docstring else ""))
    foundations = sorted((n for n in f.mod if not [s for s in f.ig.successors(n) if s in f.mod]
                          and len(f.ig.predecessors(n)) >= 2), key=lambda n: (-len(f.ig.predecessors(n)), n))
    if foundations:
        lines += ["", "**Foundations** (used by many modules, depend on no other project module): "
                  + ", ".join(_link(n) for n in foundations[:8])]
    return lines + [""]


def _module_index(f: _Facts) -> List[str]:
    lines = ["## 10. All modules", "", "| Module | Lines | Classes | Functions | Purpose |", "|---|---:|---:|---:|---|"]
    for name in sorted(f.mod):
        m = f.mod[name]
        lines.append(f"| {_link(name)} | {m.line_count:,} | {len(m.classes)} | {len(m.functions)} | "
                     f"{_cell(_doc_summary(m.docstring)) or '-'} |")
    return lines + [""]


def build_dossier(result, generated_at: datetime, diff: Optional[dict] = None,
                  _facts: Optional[_Facts] = None) -> str:
    f = _facts or _Facts(result)
    project = os.path.basename(os.path.normpath(result.root))
    lines = [f"# Onboarding dossier: {project}", "",
             f"_Generated {generated_at.strftime('%Y-%m-%d %H:%M')} by code_mapper {TOOL_VERSION} from static "
             "analysis of the code only (nothing was run, nothing left this machine). Findings marked likely or "
             "uncertain are hints to check by hand._", ""]
    lines += _overview(f, project) + _entry_section(f) + _flows(f) + _architecture(f) + _key_modules(f)
    lines += _hotspots(f) + _problems(f) + _reading_order(f)
    lines += ["## 9. Changes since the previous run", ""]
    if diff is None:
        lines += ["_First run for this project (no earlier snapshot to compare with)._", ""]
    else:
        lines += [diff_summary_line(diff) + ". The report of this run lists every change.", ""]
    lines += _module_index(f)
    return "\n".join(lines)


# -- 6.3 module pages --------------------------------------------------------------- #
def build_module_page(result, module_name: str, _facts: Optional[_Facts] = None) -> str:
    f = _facts or _Facts(result)
    m = f.mod[module_name]
    a = f.a
    kind = "package (`__init__`)" if m.is_package else ("stub (.pyi)" if m.is_stub else "module")
    lines = [f"# `{module_name}`", "", f"[Back to the dossier](../dossier.md)", "",
             f"- **File:** `{_rel(m.path)}` ({kind}, {m.line_count:,} lines)",
             f"- **Defines:** {len(m.classes)} classes, {len(m.functions)} functions / methods", ""]
    if m.docstring:
        lines += [("> " + m.docstring.strip()).replace("\n", "\n> "), ""]
    else:
        lines += ["_No module docstring._", ""]

    # dependencies
    internal, external = defaultdict(list), defaultdict(set)
    for imp in m.imports:
        if imp.origin == "internal" and imp.abs_module:
            internal[imp.abs_module].append(imp)
        elif imp.origin and imp.origin != "unresolved":
            external[imp.origin].add((imp.abs_module or imp.module).split(".")[0])
    lines += ["## Depends on", ""]
    if internal:
        for dep in sorted(internal):
            where = ", ".join(f"line {i.line}" + ("" if i.scope == MODULE_SCOPE else f" in `{i.scope}`")
                              for i in internal[dep][:4])
            target = _link(dep, "") if dep in f.mod else f"`{dep}`"
            lines.append(f"- {target} ({where})")
    else:
        lines.append("- _no other project module_")
    for origin in sorted(external):
        lines.append(f"- {origin}: {', '.join(f'`{x}`' for x in sorted(external[origin]))}")
    users = [p for p in f.ig.predecessors(module_name) if p != module_name]
    lines += ["", "## Used by", ""]
    lines += [f"- {_link(u, '') if u in f.mod else f'`{u}`'}" for u in users] or ["- _no other project module "
                                                                                 "imports it_"]
    lines.append("")

    # classes and functions
    if m.classes:
        lines += ["## Classes", ""]
        for c in m.classes:
            lines.append(f"### `{c.qualified_name}`" + (f"({', '.join(c.bases)})" if c.bases else "")
                         + f" - line {c.line}")
            lines.append("")
            if c.docstring:
                lines += [_doc_summary(c.docstring), ""]
            if c.methods:
                lines.append("Methods: " + ", ".join(f"`{n}`" for n in c.methods))
                lines.append("")
    funcs = [fn for fn in m.functions]
    if funcs:
        lines += ["## Functions and methods", ""]
        for fn in funcs:
            nid = f"{module_name}.{fn.qualified_name}"
            size = fn.end_line - fn.line + 1 if fn.end_line else 0
            lines += [f"### `{fn.qualified_name}` - line {fn.line}" + (f", {size} lines" if size else ""), "",
                      "```python", _signature(fn), "```", ""]
            if fn.docstring:
                lines += [_doc_summary(fn.docstring), ""]
            callees = [s for s in f.cg.successors(nid) if s != nid]
            callers = [p for p in f.cg.predecessors(nid) if p != nid]
            if callees:
                lines.append("Calls: " + ", ".join(f"`{c}`" for c in callees[:12])
                             + (f", ... ({len(callees)} in total)" if len(callees) > 12 else ""))
            ext = f.cg.nodes.get(nid, {}).get("external_calls", {})
            if ext:
                top_ext = sorted(ext, key=lambda k: (-ext[k], k))[:6]
                lines.append("Uses outside the project: " + ", ".join(f"`{k}`" for k in top_ext))
            if callers:
                lines.append("Called by: " + ", ".join(f"`{c}`" for c in callers[:12])
                             + (f", ... ({len(callers)} in total)" if len(callers) > 12 else ""))
            elif f.cg.nodes.get(nid, {}).get("kind") in ("function", "method"):
                lines.append("Called by: _no resolved caller in the project_")
            lines.append("")
    for scope, title in ((f"{module_name}.{MODULE_SCOPE}", "Module-level code"),
                         (f"{module_name}.{MAIN_SCOPE}", 'The `if __name__ == "__main__"` block')):
        callees = f.cg.successors(scope) if scope in f.cg.nodes else []
        if callees:
            lines += [f"## {title}", "", "Calls: " + ", ".join(f"`{c}`" for c in callees[:12]), ""]

    # findings
    found = []
    if a:
        prefix = module_name + "."
        found += [f"dead code ({d['confidence']}): `{d['id']}` (line {d['line']})"
                  for d in a["dead_code"] if d["id"].startswith(prefix) and f.module_of(d["id"]) == module_name]
        if a.get("imports"):
            found += [f"unused import ({i['confidence']}): `{i['statement']}` (line {i['line']})"
                      for i in a["imports"]["unused"] if i["module"] == module_name]
            found += [f"missing module: `{i['statement']}` (line {i['line']})"
                      for i in a["imports"]["missing"] if i["module"] == module_name]
        found += [f"in import cycle `{c['id']}` ({c['kind']}, {c['confidence']}) with "
                  + ", ".join(f"`{x}`" for x in c["members"] if x != module_name)
                  for c in a["cycles"]["import"] if module_name in c["members"]]
        found += [f"direct recursion ({d['confidence']}): `{d['id']}`" for d in a["recursion"]["direct"]
                  if f.module_of(d["id"]) == module_name]
        found += [f"call in a loop ({r['confidence']}): `{r['caller']}` -> `{r['callee']}` ({', '.join(r['why'])})"
                  for r in a["loops"]["calls_in_loops"] if f.module_of(r["caller"]) == module_name]
    lines += ["## Findings", ""] + ([f"- {x}" for x in found] or ["_None._"]) + [""]
    return "\n".join(lines)


def write_dossier(result, out_dir: str, generated_at: datetime, diff: Optional[dict] = None) -> str:
    """Write dossier.md and modules/*.md into out_dir; returns the path of dossier.md."""
    f = _Facts(result)
    os.makedirs(os.path.join(out_dir, "modules"), exist_ok=True)
    path = os.path.join(out_dir, "dossier.md")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(build_dossier(result, generated_at, diff, f) + "\n")
    for name in sorted(f.mod):
        with open(os.path.join(out_dir, "modules", _page_name(name)), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(build_module_page(result, name, f) + "\n")
    return path


# ==================================================================================================
# Pipeline and ENGINE BOUNDARY
# ==================================================================================================
# Everything above this section is the algorithm.  This section is the only place an engine
# needs to touch:
#
#   run(root, ...)              -> dict   everything the algorithm found (JSON-safe), see result_to_dict
#   run_pipeline(root, ...)     -> PipelineResult   the same, as live Python objects (graphs you can query)
#   write_outputs(...)                    one way of delivering it: the files of a CLI scan
#
# When the engine is built, replace the inputs (a folder path today; a zip / file list / stream
# later) and the outputs (files today; database rows / API responses later) here, and keep the
# result dict as the contract every language algorithm returns.
RESULT_SCHEMA_VERSION = 1
ALGORITHM = {"name": "code_mapper", "language": "python", "version": TOOL_VERSION,
             "method": "static analysis with the standard-library ast module (code is never executed)"}


@dataclass
class PipelineResult:
    root: str
    modules: List[ModuleInfo]
    resolver: Resolver
    graphs: Dict[str, Graph]
    import_issues: List[dict]
    analysis: Optional[dict] = None
    warnings: List[str] = field(default_factory=list)
    timings: Dict[str, float] = field(default_factory=dict)      # seconds per stage
    options: Dict[str, object] = field(default_factory=dict)


def run_pipeline(root: str, ignore: Iterable[str] = (), analyze: bool = True,
                 min_confidence: str = "uncertain", max_bytes: int = MAX_FILE_BYTES,
                 skip_dirs: Iterable[str] = ()) -> PipelineResult:
    """Run every stage on the project folder `root`.

    ignore          extra folder / file name patterns to skip (fnmatch style, e.g. "migrations", "*_pb2.py")
    analyze         False skips Stage 4 (graphs only)
    min_confidence  drop findings below this level ("certain" | "likely" | "uncertain")
    max_bytes       files bigger than this are listed as errors, not parsed
    skip_dirs       absolute folders never scanned (e.g. the output folder when it sits inside the project)
    """
    timings: Dict[str, float] = {}
    clock = time.perf_counter()

    def lap(stage: str):
        nonlocal clock
        now = time.perf_counter()
        timings[stage] = round(now - clock, 4)
        clock = now

    warnings: List[str] = []
    ignore, skip_dirs = list(ignore), list(skip_dirs)
    modules = analyze_project(root, ignore=ignore, warnings=warnings, max_bytes=max_bytes, skip_dirs=skip_dirs)
    lap("1_scan_and_parse")
    resolver = resolve_project(modules)
    lap("2_resolve")
    graphs = build_graphs(resolver)
    lap("3_graphs")
    issues = find_import_issues(resolver)
    analysis = filter_analysis(analyze_graphs(graphs, issues), min_confidence) if analyze else None
    lap("4_analyze")
    for name, path in resolver.duplicate_modules:
        warnings.append(f"{path.replace(os.sep, '/')}: module name `{name}` is already used by another file; "
                        "this file is ignored for lookups")
    options = {"ignore": ignore, "analyze": analyze, "min_confidence": min_confidence, "max_bytes": max_bytes}
    return PipelineResult(root, modules, resolver, graphs, issues, analysis, warnings, timings, options)


# -- everything the parser and resolver recorded, as plain data -------------------------------- #
def _call_dict(c: CallInfo) -> dict:
    out = {"name": c.name, "line": c.line, "loop_depth": c.loop_depth, "status": c.status, "target": c.target}
    for key in ("reason", "note", "instantiates"):
        if getattr(c, key):
            out[key] = getattr(c, key)
    if c.inferred:
        out["inferred"] = True
    return out


def _function_dict(fn: FunctionInfo) -> dict:
    return {
        "name": fn.name, "qualified_name": fn.qualified_name, "line": fn.line, "end_line": fn.end_line,
        "lines": fn.end_line - fn.line + 1 if fn.end_line else 0,
        "is_async": fn.is_async, "args": list(fn.args), "returns": fn.returns, "docstring": fn.docstring,
        "decorators": list(fn.decorators), "enclosing_class": fn.enclosing_class,
        "signature": _signature(fn) if fn.name not in (MODULE_SCOPE, MAIN_SCOPE) else None,
        "fingerprint": fn.fingerprint, "local_names": list(fn.local_names),
        "var_types": dict(fn.var_types), "param_types": dict(fn.param_types),
        "loops": [{"kind": lp.kind, "line": lp.line, "depth": lp.depth} for lp in fn.loops],
        "calls": [_call_dict(c) for c in fn.calls],
    }


def facts_to_dict(modules: List[ModuleInfo], resolver: Resolver) -> dict:
    """Every fact Stage 1 and Stage 2 recorded: per module its imports (with origin), classes (with
    resolved bases and typed attributes), functions (signature, docstring, decorators, loops, type hints,
    every call and how it was resolved), aliases, `__all__`, names used, ...; plus the symbol table."""
    mods = []
    for m in modules:
        entry = {
            "path": _rel(m.path), "module": m.module_name, "is_package": m.is_package, "is_stub": m.is_stub,
            "lines": m.line_count, "error": m.error, "warnings": list(m.warnings), "docstring": m.docstring,
            "ignored_duplicate": resolver.mod_by_name.get(m.module_name) is not m and not m.error,
        }
        if m.error:
            mods.append(entry)
            continue
        entry.update({
            "imports": [{"statement": i.describe(), "kind": i.kind, "module": i.module, "name": i.name,
                         "alias": i.alias, "level": i.level, "line": i.line, "scope": i.scope,
                         "bound_name": i.bound_name, "abs_module": i.abs_module, "origin": i.origin,
                         "type_checking": i.type_checking, "in_try": i.in_try} for i in m.imports],
            "classes": [{
                "name": c.name, "qualified_name": c.qualified_name, "line": c.line, "end_line": c.end_line,
                "bases": list(c.bases), "decorators": list(c.decorators), "docstring": c.docstring,
                "methods": list(c.methods), "attr_types": dict(c.attr_types),
                "resolved_bases": [{"kind": k, "ref": r} for k, r in resolver._class_bases(
                    f"{m.module_name}.{c.qualified_name}")]
                if f"{m.module_name}.{c.qualified_name}" in resolver._classes else [],
            } for c in m.classes],
            "functions": [_function_dict(fn) for fn in m.functions],
            "module_scope": _function_dict(m.module_scope) if m.module_scope else None,
            "main_block": _function_dict(m.main_block) if m.main_block else None,
            "aliases": [{"name": a.name, "target": a.target, "line": a.line} for a in m.aliases],
            "exports": m.exports, "uses_dynamic_names": m.uses_dynamic_names,
            "used_names": sorted(m.used_names), "value_refs": sorted(m.value_refs),
        })
        mods.append(entry)
    return {
        "modules": mods,
        "symbols": {k: {"kind": s.kind, "module": s.module, "qualified_name": s.qualified_name, "line": s.line}
                    for k, s in sorted(resolver.symbols.items())},
        "duplicate_modules": [{"module": n, "path": _rel(p)} for n, p in resolver.duplicate_modules],
    }


def result_to_dict(result: PipelineResult, generated_at: datetime, snapshot: Optional[dict] = None,
                   diff: Optional[dict] = None) -> dict:
    """THE OUTPUT CONTRACT: one JSON-safe dict with everything the algorithm found."""
    summary = build_report_data(result.root, result.modules, generated_at, result.resolver, result.graphs,
                                result.analysis, diff, result.warnings)
    return {
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "algorithm": dict(ALGORITHM),
        "project": {"name": os.path.basename(os.path.normpath(result.root)), "root": _rel(result.root),
                    "generated_at": generated_at.strftime("%Y-%m-%d %H:%M:%S")},
        "run": {"options": dict(result.options), "timings_s": dict(result.timings)},
        "warnings": list(result.warnings),
        "totals": summary["totals"],
        "resolution": dict(summary["resolution"], reason_help=dict(REASON_HELP)),
        "facts": facts_to_dict(result.modules, result.resolver),
        "graphs": {"call": result.graphs["call"].to_dict(), "import": result.graphs["import"].to_dict()},
        "import_issues": list(result.import_issues),
        "analysis": result.analysis,
        "snapshot": snapshot,
        "diff": diff,
    }


def run(root: str, ignore: Iterable[str] = (), analyze: bool = True, min_confidence: str = "uncertain",
        max_bytes: int = MAX_FILE_BYTES, skip_dirs: Iterable[str] = (), previous=None,
        generated_at: Optional[datetime] = None) -> dict:
    """INPUT -> OUTPUT of this algorithm: scan the project folder `root` and return everything as a dict.

    previous   an earlier snapshot (dict, or path to a snapshot file) to compare with; the result then
               has a "diff".  Every result carries its own "snapshot" to pass as `previous` next time.
    """
    when = generated_at or datetime.now()
    result = run_pipeline(root, ignore, analyze, min_confidence, max_bytes, skip_dirs)
    snapshot = build_snapshot(result, when)
    if isinstance(previous, str):
        previous = load_snapshot(previous)
    diff = diff_snapshots(previous, snapshot) if previous else None
    return result_to_dict(result, when, snapshot, diff)


def write_outputs(result: PipelineResult, data: dict, out_day_dir: str, stamp: str,
                  graphs: bool = True, dossier: bool = True) -> Dict[str, str]:
    """One way of delivering a result: the files of a CLI scan. Returns {kind: path}."""
    paths = {}
    os.makedirs(out_day_dir, exist_ok=True)
    paths["result"] = os.path.join(out_day_dir, f"result_{stamp}.json")
    with open(paths["result"], "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    if graphs:
        paths["graphs"] = os.path.join(out_day_dir, f"graphs_{stamp}")
        write_graphs(result.graphs, os.path.basename(result.root), paths["graphs"], result.import_issues,
                     result.analysis)
        if data.get("diff") is not None:
            with open(os.path.join(paths["graphs"], "diff.json"), "w", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(data["diff"], indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    if dossier:
        when = datetime.strptime(data["project"]["generated_at"], "%Y-%m-%d %H:%M:%S")
        paths["dossier"] = write_dossier(result, os.path.join(out_day_dir, f"dossier_{stamp}"), when,
                                         data.get("diff"))
    return paths


# ==================================================================================================
# CLI
# ==================================================================================================
# Command-line interface.
DESCRIPTION = """Map a Python project: functions, classes, imports, call graph, import graph,
cycles, recursion, loops, entry points, dead code, unused imports, metrics, run history
and an onboarding dossier. Static analysis only (the code is never run or sent anywhere)."""

EPILOG = """examples:
  python code_mapper.py path/to/project
  python code_mapper.py . --ignore migrations --ignore "*_pb2.py" --min-confidence likely
  python code_mapper.py . --format json --no-reports > result.json
  python code_mapper.py . --query callers pkg.core.Engine.make --depth 2
  python code_mapper.py --from-graph reports/<date>/graphs_<time>/graph.json --analyze
  python code_mapper.py . --history
  python code_mapper.py --diff old_snapshot.json new_snapshot.json
"""


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="code_mapper", description=DESCRIPTION, epilog=EPILOG,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("root", nargs="?", default=".", help="project folder (default: .)")
    p.add_argument("--version", action="version", version=f"code_mapper {TOOL_VERSION}")

    out = p.add_argument_group("output")
    out.add_argument("--format", choices=("md", "json"), default="md",
                     help="md: the human report; json: the full result (everything the algorithm found), "
                          "for the console and the saved report (default: md)")
    out.add_argument("--output", metavar="DIR",
                     help=f"folder for reports, graphs, dossiers and history (default: {REPORTS_DIR_NAME}/ next to "
                          "code_mapper.py)")
    out.add_argument("--quiet", action="store_true", help="don't print the report to the console")
    out.add_argument("--no-reports", action="store_true",
                     help="write no files at all, not even result_<time>.json (console output only; implies "
                          "--no-graphs --no-dossier --no-history)")
    out.add_argument("--no-graphs", action="store_true",
                     help="don't write graph.json / .mmd / .dot / analysis.json (result_<time>.json is still written)")
    out.add_argument("--no-dossier", action="store_true", help="don't write the onboarding dossier")
    out.add_argument("--no-history", action="store_true",
                     help="don't save a snapshot of this run and don't compare with the previous one")

    scan = p.add_argument_group("scanning")
    scan.add_argument("--ignore", action="append", default=[], metavar="PATTERN",
                      help="skip folders / files matching PATTERN (fnmatch on the name or relative path; "
                           "repeat or separate with commas), e.g. migrations, 'tests/*', '*_pb2.py'")
    scan.add_argument("--max-file-mb", type=float, default=MAX_FILE_BYTES / 1048576,
                      help=f"files bigger than this are listed as errors, not parsed (default: "
                           f"{MAX_FILE_BYTES / 1048576:.0f})")

    an = p.add_argument_group("analysis")
    an.add_argument("--no-analysis", action="store_true", help="skip the analyzers (graphs only)")
    an.add_argument("--min-confidence", choices=list(CONFIDENCE_ORDER), default="uncertain",
                    help="only show / save findings at least this confident (default: uncertain = all)")

    q = p.add_argument_group("queries and saved results")
    q.add_argument("--query", nargs=2, metavar=("KIND", "NODE"),
                   help="callers | callees | importers | imports of NODE (full id, or a unique ending/part of it)")
    q.add_argument("--depth", type=int, default=1, help="levels to follow for --query (default 1, 0 = all)")
    q.add_argument("--from-graph", metavar="GRAPH_JSON",
                   help="answer --query / --analyze from a saved graph.json, without scanning any code")
    q.add_argument("--analyze", action="store_true",
                   help="with --from-graph: print the analysis; a normal scan always includes it")
    q.add_argument("--history", action="store_true", help="list the saved snapshots of the project and exit")
    q.add_argument("--diff", nargs="+", metavar="SNAPSHOT",
                   help="OLD NEW: print the difference between two snapshot files and exit; "
                        "OLD only: scan the project and compare with OLD instead of the previous run")
    return p


def _print_json(data):
    print(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False))


def _from_graph(args) -> int:
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
        if args.format == "json":
            _print_json(result)
        else:
            print("\n".join(analysis_lines(result, limit=None)))
    if args.query:
        if args.analyze:
            print()
        return run_query(graphs, args.query[0], args.query[1], args.depth)
    return 0


def _diff_files(args) -> int:
    try:
        old, new = load_snapshot(args.diff[0]), load_snapshot(args.diff[1])
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    diff = diff_snapshots(old, new)
    if args.format == "json":
        _print_json(diff)
    else:
        print("\n".join(diff_lines(diff, limit=None)))
    return 0


def _list_history(output_dir: str, root: str) -> int:
    snaps = list_snapshots(output_dir, root)
    if not snaps:
        print(f"No snapshots saved for {root} in {output_dir}")
        return 0
    print(f"{len(snaps)} snapshots of {root}:")
    for path in snaps:
        try:
            s = load_snapshot(path)["stats"]
            print(f"  {path}\n      {s['modules']} modules, {s['functions']} functions, {s['classes']} classes, "
                  f"{s['calls_resolved_percent']}% calls resolved, dead code: {s['dead_code']}")
        except (OSError, ValueError, KeyError) as exc:
            print(f"  {path} (unreadable: {exc})")
    return 0


def main(argv=None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.query and args.query[0] not in QUERY_KINDS:
        parser.error(f"unknown query kind '{args.query[0]}' (use: {', '.join(QUERY_KINDS)})")
    if args.diff and len(args.diff) > 2:
        parser.error("--diff takes one or two snapshot files")
    if args.from_graph:
        if not args.query and not args.analyze:
            parser.error("--from-graph needs --query and/or --analyze")
        return _from_graph(args)
    if args.diff and len(args.diff) == 2:
        return _diff_files(args)

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"Error: '{root}' is not a folder", file=sys.stderr)
        return 1
    output_dir = os.path.abspath(args.output) if args.output else os.path.join(TOOL_DIR, REPORTS_DIR_NAME)
    if args.history:
        return _list_history(output_dir, root)
    if args.no_reports:
        args.no_graphs = args.no_dossier = args.no_history = True
    ignore = [p.strip() for item in args.ignore for p in item.split(",") if p.strip()]

    now = datetime.now()
    result = run_pipeline(root, ignore=ignore, analyze=not args.no_analysis, min_confidence=args.min_confidence,
                          max_bytes=int(args.max_file_mb * 1048576), skip_dirs=[output_dir])
    for w in result.warnings:
        print(f"Warning: {w}", file=sys.stderr)

    # 6.1 run history: compare with the previous snapshot (or the one given with --diff OLD)
    snapshot, diff = build_snapshot(result, now), None
    try:
        previous = args.diff[0] if args.diff else None
        if previous is None and not args.no_history:
            older = list_snapshots(output_dir, root)
            previous = older[-1] if older else None
        if previous:
            diff = diff_snapshots(load_snapshot(previous), snapshot)
    except (OSError, ValueError) as exc:
        print(f"Warning: cannot compare with the previous run: {exc}", file=sys.stderr)
    data = result_to_dict(result, now, snapshot, diff)            # everything, as one dict

    md = args.format == "md"
    if md:
        content = build_report(root, result.modules, now, result.resolver, result.graphs, result.analysis,
                               diff=diff, warnings=result.warnings)
    else:
        content = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    if not args.quiet:
        print(content)

    st = result.resolver.stats
    log = sys.stderr if (not md and not args.quiet) else sys.stdout      # keep stdout pure JSON
    print(f"\nResolved {st.resolved()} of {st.total} calls ({st.percent():.1f}%, {st.inferred} through inferred "
          f"types), {len(result.resolver.symbols)} symbols in the table", file=log)
    cg, ig = result.graphs["call"], result.graphs["import"]
    print(f"Call graph: {len(cg.nodes)} nodes, {len(cg.edges)} edges; "
          f"import graph: {len(ig.nodes)} nodes, {len(ig.edges)} edges", file=log)
    if result.analysis is not None:
        print(analysis_summary_line(result.analysis), file=log)
    if diff is not None:
        print(diff_summary_line(diff), file=log)
    print("Time: " + ", ".join(f"{k} {v:.2f}s" for k, v in result.timings.items()), file=log)
    if args.no_reports:
        return run_query(result.graphs, args.query[0], args.query[1], args.depth) if args.query else 0

    path = write_report(content, now, output_dir, "md" if md else "json")
    print(f"Report saved to: {path}", file=log)
    paths = write_outputs(result, data, os.path.dirname(path), now.strftime("%H-%M-%S"),
                          graphs=not args.no_graphs, dossier=not args.no_dossier)
    print(f"Everything (result.json) saved to: {paths['result']}", file=log)
    if "graphs" in paths:
        print(f"Graphs{' and analysis' if result.analysis is not None else ''} saved to: {paths['graphs']}",
              file=log)
    if "dossier" in paths:
        print(f"Onboarding dossier saved to: {paths['dossier']}", file=log)
    if not args.no_history:
        print(f"Snapshot saved to: {save_snapshot(snapshot, output_dir, root, now)}", file=log)
    if args.query:
        print(file=log)
        return run_query(result.graphs, args.query[0], args.query[1], args.depth)
    return 0


if __name__ == "__main__":
    sys.exit(main())
