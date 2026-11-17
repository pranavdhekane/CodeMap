"""5.7 and the product's offline guarantee: code_mapper.py is one self-contained file that imports only
the standard library, never a networking module, and keeps to Python 3.9 syntax."""
import ast
import os
import sys
import unittest

from _helpers import TOOL_DIR

NETWORK_MODULES = {"socket", "ssl", "http", "urllib", "ftplib", "smtplib", "poplib", "imaplib", "telnetlib",
                   "xmlrpc", "asyncio", "socketserver", "requests", "httpx", "aiohttp", "webbrowser"}


def engine_files():
    return [os.path.join(TOOL_DIR, "code_mapper.py")]


def imported_modules(path):
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            yield (node.module or "").split(".")[0]


class Meta(unittest.TestCase):
    def test_stdlib_only(self):
        stdlib = getattr(sys, "stdlib_module_names", None)
        if stdlib is None:
            self.skipTest("needs Python 3.10+ to know the stdlib module names")
        for path in engine_files():
            for mod in imported_modules(path):
                self.assertIn(mod, stdlib, f"{path}: imports {mod}")

    def test_no_network_modules(self):
        for path in engine_files():
            used = set(imported_modules(path)) & NETWORK_MODULES
            self.assertFalse(used, f"{path} imports {used}")

    def test_python_39_syntax(self):
        for path in engine_files():
            with open(path, encoding="utf-8") as f:
                source = f.read()
            ast.parse(source, feature_version=(3, 9))            # no match statements, no except*, ...
            for lineno, line in enumerate(source.splitlines(), 1):
                # before 3.12 an f-string expression may not contain a backslash or reuse its quote
                for start in ('f"', "f'"):
                    i = line.find(start)
                    while i != -1:
                        quote = start[1]
                        end = line.find(quote, i + 2)
                        while end != -1 and line[end - 1] == "\\":
                            end = line.find(quote, end + 1)
                        body = line[i + 2:end if end != -1 else len(line)]
                        depth, expr = 0, []
                        for ch in body:
                            if ch == "{":
                                depth += 1
                            elif ch == "}":
                                depth -= 1
                            elif depth > 0:
                                expr.append(ch)
                        self.assertNotIn("\\", "".join(expr), f"{path}:{lineno}: backslash in f-string expression")
                        i = line.find(start, end + 1) if end != -1 else -1

    def test_version_guard(self):
        import code_mapper
        self.assertRegex(code_mapper.TOOL_VERSION, r"^\d+\.\d+$")
        with open(os.path.join(TOOL_DIR, "code_mapper.py"), encoding="utf-8") as f:
            self.assertIn("sys.version_info < (3, 9)", f.read())


if __name__ == "__main__":
    unittest.main()
