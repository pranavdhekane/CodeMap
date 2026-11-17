"""Shared paths and small helpers for the test suite (not a test module itself)."""
import contextlib
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL_DIR = os.path.dirname(HERE)
if TOOL_DIR not in sys.path:
    sys.path.insert(0, TOOL_DIR)

FIXTURES = os.path.join(HERE, "fixtures")
SEEDED = os.path.join(FIXTURES, "seeded_project")
EDGE = os.path.join(FIXTURES, "edge_project")
TYPED = os.path.join(FIXTURES, "typed_project")
GOLDEN = os.path.join(HERE, "golden")


def calls_by_scope(modules):
    """{"module.scope": {call text: CallInfo}} for quick lookups in resolver tests."""
    out = {}
    for m in modules:
        scopes = list(m.functions) + [s for s in (m.module_scope, m.main_block) if s is not None]
        for fn in scopes:
            out.setdefault(f"{m.module_name}.{fn.qualified_name}", {}).update({c.name: c for c in fn.calls})
    return out


@contextlib.contextmanager
def temp_dir():
    path = tempfile.mkdtemp(prefix="codemap_test_")
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@contextlib.contextmanager
def captured():
    """Capture stdout and stderr: `with captured() as (out, err): ...; out.getvalue()`."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


def write(path: str, text: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
