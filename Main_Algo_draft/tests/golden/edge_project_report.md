# Code Mapper Report

- **Project:** `<edge_project>`
- **Generated:** 2026-01-01 00:00:00
- **Modules scanned:** 12
- **Classes found:** 2
- **Functions found:** 17
- **Imports found:** 12
- **Loops found:** 0
- **Calls resolved:** 16 of 20 (80.0%)
- **Call graph:** 20 nodes, 12 edges
- **Import graph:** 12 nodes, 9 edges
- **Analysis: 1 import cycles, 8 dead code, 1 unused imports, 1 missing modules; 3 entry points**

## Summary

| Module | Dotted name | Imports | Classes | Functions | Loops | Module docstring |
|---|---|---:|---:|---:|---:|:---:|
| `app.py` | `app` | 7 | 0 | 3 | 0 | yes |
| `broken.py` | `broken` | 0 | 0 | 0 | 0 | error |
| `cookie.py` | `cookie` | 0 | 0 | 1 | 0 | no |
| `legacy.py` | `legacy` | 0 | 0 | 1 | 0 | no |
| `core/__init__.py` | `core` | 2 | 0 | 0 | 0 | yes |
| `core/engine.py` | `core.engine` | 1 | 2 | 7 | 0 | yes |
| `core/loop_a.py` | `core.loop_a` | 1 | 0 | 1 | 0 | yes |
| `core/loop_b.py` | `core.loop_b` | 1 | 0 | 0 | 0 | yes |
| `core/util.py` | `core.util` | 0 | 0 | 1 | 0 | yes |
| `nsdir/mod.py` | `nsdir.mod` | 0 | 0 | 1 | 0 | no |
| `stubs/fast.pyi` | `stubs.fast` | 0 | 0 | 1 | 0 | no |
| `stubs/slow.py` | `stubs.slow` | 0 | 0 | 1 | 0 | no |

## Warnings

- legacy.py: not valid utf-8 (the encoding it declares, or Python's default); read as latin-1, so non-ASCII text may look odd

## Resolution coverage

- **Calls analysed:** 20
- **Resolved:** 16 (80.0%)
  - local (same module): 5
  - internal (other project module): 8
  - external: 3 (builtin 2, builtin, via super() 1)
  - of the local / internal ones, resolved through an inferred type: 0
- **Unresolved:** 4 (20.0%)

| Unresolved reason | Calls | Meaning |
|---|---:|---|
| `variable` | 2 | call or attribute on a parameter / local / module variable (type unknown) |
| `relative-import` | 1 | relative import goes above the scanned folder |
| `cycle` | 1 | alias / re-export chain is circular or too deep |

## Analysis

Findings are labelled **certain** (exact facts), **likely** (right unless the code is dynamic or the call graph missed an edge) or **uncertain** (signs of a false positive, check by hand).

- Call edges are a lower bound: light type inference resolves `x = Foo(); x.run()`, annotated parameters and typed `self.attr`, but calls on values of unknown type are not edges. Dead-code findings are labelled with that in mind; read `uncertain` as 'check by hand'.
- Dead code is judged inside the scanned project only: public names may be used by outside code.

| Finding | Total | certain | likely | uncertain |
|---|---:|---:|---:|---:|
| import cycles | 1 | 1 | 0 | 0 |
| call cycles | 0 | 0 | 0 | 0 |
| direct recursion | 0 | 0 | 0 | 0 |
| calls in loops | 0 | 0 | 0 | 0 |
| dead code | 8 | 0 | 7 | 1 |
| unused imports | 1 | 1 | 0 | 0 |
| missing modules | 1 | 0 | 1 | 0 |

Entry points: 3; functions inside call cycles: 0; scopes with nested loops: 0

### Entry points

| Type | Node | Why | Confidence |
|---|---|---|---|
| exported | `core.engine.Engine` | listed in __all__ | certain |
| exported | `core.util.helper` | listed in __all__ | certain |
| main-block | `app.<main>` | if __name__ == "__main__" block | certain |

### Circular dependencies

**Import cycles (modules):** 1

- `import-cycle-1` (import-time, certain, 2 members): `core.loop_a` -> `core.loop_b` -> `core.loop_a`
  - `core.loop_a` -> `core.loop_b` (line 2, `from .loop_b import y as x`)
  - `core.loop_b` -> `core.loop_a` (line 2, `from .loop_a import x as y`)

**Call cycles (mutual recursion):** _none_


### Recursion

**Direct (a function calls itself):** _none_

**Indirect (cycle length > 1):** _none_

### Loops

0 loops in 0 scopes; 0 scopes with nested loops; 0 calls inside loops into code that loops or recurses.

### Dead code candidates

Not reported: 1 classes used as a base class, 1 declarations in .pyi stubs, 2 entry points, 1 methods overriding a project base-class method, 1 special (dunder) methods.

| Confidence | Kind | Node | Line | Notes |
|---|---|---|---:|---|
| likely | function | `app.shadow` | 19 | public name: code outside the project may use it |
| likely | function | `app.deep_relative` | 23 | public name: code outside the project may use it |
| likely | function | `cookie.with_cookie` | 5 | public name: code outside the project may use it |
| likely | function | `core.engine.outer` | 25 | public name: code outside the project may use it; contains `outer.inner` |
| likely | function | `core.loop_a.use_x` | 5 | public name: code outside the project may use it |
| likely | function | `legacy.legacy` | 4 | public name: code outside the project may use it |
| likely | function | `stubs.slow.crawl` | 1 | public name: code outside the project may use it |
| uncertain | method | `core.engine.Base.start` | 6 | public name: code outside the project may use it; 1 unresolved call(s) end in `.start` and may reach it |

### Imports

**Unused imports:** 1

| Confidence | Module | Line | Import | Notes |
|---|---|---:|---|---|
| certain | `core.loop_b` | 2 | `from .loop_a import x as y` |  |

**Imports of missing project modules:** 1

| Confidence | Module | Line | Import | Notes |
|---|---|---:|---|---|
| likely | `app` | 24 | `from .. import nowhere` | points into the project but no such module was found (or the relative import leaves the scanned folder) |

### Metrics

**Call graph:** 20 nodes, 12 edges, 0 nodes in cycles, longest chain 3 steps

Longest chain (`~>` = moves inside a cycle):

`app.<main> -> app.run -> core.engine.Engine.build -> core.engine.Engine.__init__`

**Highest fan-in (most used)**

| Node | Score | Fan-in | Fan-out |
|---|---:|---:|---:|
| `core.util.helper` | 3 | 3 | 0 |
| `core.engine.Base.step` | 2 | 2 | 0 |
| `core.engine.Engine.__init__` | 2 | 2 | 0 |
| `app.run` | 1 | 1 | 5 |
| `core.engine.Engine.build` | 1 | 1 | 1 |
| `core.engine.Engine.step` | 1 | 1 | 2 |
| `core.engine.outer.inner` | 1 | 1 | 1 |
| `nsdir.mod.ns_func` | 1 | 1 | 0 |

**Highest fan-out (uses the most)**

| Node | Score | Fan-in | Fan-out |
|---|---:|---:|---:|
| `app.run` | 5 | 1 | 5 |
| `core.engine.Engine.step` | 2 | 1 | 2 |
| `app.<main>` | 1 | 0 | 1 |
| `core.engine.Base.start` | 1 | 0 | 1 |
| `core.engine.Engine.build` | 1 | 1 | 1 |
| `core.engine.outer` | 1 | 0 | 1 |
| `core.engine.outer.inner` | 1 | 1 | 1 |

**Most connected**

| Node | In + out | Fan-in | Fan-out |
|---|---:|---:|---:|
| `app.run` | 6 | 1 | 5 |
| `core.engine.Engine.step` | 3 | 1 | 2 |
| `core.util.helper` | 3 | 3 | 0 |
| `core.engine.Base.step` | 2 | 2 | 0 |
| `core.engine.Engine.__init__` | 2 | 2 | 0 |
| `core.engine.Engine.build` | 2 | 1 | 1 |
| `core.engine.outer.inner` | 2 | 1 | 1 |
| `app.<main>` | 1 | 0 | 1 |
| `core.engine.Base.start` | 1 | 0 | 1 |
| `core.engine.outer` | 1 | 0 | 1 |

**Deepest call / import chains below them**

| Node | Depth | Fan-in | Fan-out |
|---|---:|---:|---:|
| `app.<main>` | 3 | 0 | 1 |
| `app.run` | 2 | 1 | 5 |
| `core.engine.outer` | 2 | 0 | 1 |
| `core.engine.Base.start` | 1 | 0 | 1 |
| `core.engine.Engine.build` | 1 | 1 | 1 |
| `core.engine.Engine.step` | 1 | 1 | 2 |
| `core.engine.outer.inner` | 1 | 1 | 1 |

**Import graph:** 12 nodes, 9 edges, 2 nodes in cycles, longest chain 3 steps

Longest chain (`~>` = moves inside a cycle):

`app -> core -> core.engine -> core.util`

**Highest fan-in (most used)**

| Node | Score | Fan-in | Fan-out |
|---|---:|---:|---:|
| `core.util` | 3 | 3 | 0 |
| `core` | 1 | 1 | 2 |
| `core.engine` | 1 | 1 | 1 |
| `core.loop_a` | 1 | 1 | 1 |
| `core.loop_b` | 1 | 1 | 1 |
| `nsdir` | 1 | 1 | 0 |
| `nsdir.mod` | 1 | 1 | 0 |

**Highest fan-out (uses the most)**

| Node | Score | Fan-in | Fan-out |
|---|---:|---:|---:|
| `app` | 4 | 0 | 4 |
| `core` | 2 | 1 | 2 |
| `core.engine` | 1 | 1 | 1 |
| `core.loop_a` | 1 | 1 | 1 |
| `core.loop_b` | 1 | 1 | 1 |

**Most connected**

| Node | In + out | Fan-in | Fan-out |
|---|---:|---:|---:|
| `app` | 4 | 0 | 4 |
| `core` | 3 | 1 | 2 |
| `core.util` | 3 | 3 | 0 |
| `core.engine` | 2 | 1 | 1 |
| `core.loop_a` | 2 | 1 | 1 |
| `core.loop_b` | 2 | 1 | 1 |
| `nsdir` | 1 | 1 | 0 |
| `nsdir.mod` | 1 | 1 | 0 |

**Deepest call / import chains below them**

| Node | Depth | Fan-in | Fan-out |
|---|---:|---:|---:|
| `app` | 3 | 0 | 4 |
| `core` | 2 | 1 | 2 |
| `core.engine` | 1 | 1 | 1 |

## Module: `app.py`

**Dotted name:** `app` (module)

**Module docstring:**

> Application module: every way of reaching core.

**Imports:**

- `import core` (line 2) -> internal `core`
- `import nsdir` (line 3) -> internal `nsdir`
- `from core import Engine` (line 4) -> internal `core`
- `from core import helper` (line 4) -> internal `core`
- `from core.util import alias_helper` (line 5) -> internal `core.util`
- `from nsdir import mod` (line 6) -> internal `nsdir.mod`
- `from .. import nowhere` (line 24) - inside `deep_relative` -> unresolved

**Imported by:** _none found_

**Main block (`if __name__ == "__main__"`, line 28):**

Calls:

- `run()` (line 29) -> `app.run` [local]

### `run`  (line 9)

```python
def run()
```

_No docstring._

**Inputs:** _none_

**Loops:** _none_

**Calls:**

- `Engine.build()` (line 10) -> `core.engine.Engine.build` [internal]
- `engine.start()` (line 11) -> unresolved (variable): `engine` is a parameter or local variable (type unknown)
- `core.helper()` (line 12) -> `core.util.helper` [internal]
- `alias_helper()` (line 13) -> `core.util.helper` [internal]
- `Engine().step()` (line 14) -> `core.engine.Engine.step` [internal]
- `Engine()` (line 14) -> `core.engine.Engine.__init__` [internal: instantiates Engine]
- `mod.ns_func()` (line 15) -> `nsdir.mod.ns_func` [internal]

**Called by:**

- `app.<main>` (line 29)

### `shadow`  (line 19)

```python
def shadow(helper)
```

_No docstring._

**Inputs:** `helper`

**Loops:** _none_

**Calls:**

- `helper()` (line 20) -> unresolved (variable): `helper` is a parameter or local variable (type unknown)

**Called by:** _none found_

### `deep_relative`  (line 23)

```python
def deep_relative()
```

_No docstring._

**Inputs:** _none_

**Loops:** _none_

**Calls:**

- `nowhere()` (line 25) -> unresolved (relative-import): `from .. import nowhere` goes above the scanned folder

**Called by:** _none found_

## Module: `broken.py`

Could not parse: `SyntaxError: invalid syntax (broken.py, line 1)`

## Module: `cookie.py`

**Dotted name:** `cookie` (module)

_No module docstring._

**Imports:** _none_

**Imported by:** _none found_

### `with_cookie`  (line 5)

```python
def with_cookie()
```

_No docstring._

**Inputs:** _none_

**Loops:** _none_

**Calls:** _none_

**Called by:** _none found_

## Module: `legacy.py`

**Dotted name:** `legacy` (module)

_No module docstring._

**Imports:** _none_

**Imported by:** _none found_

### `legacy`  (line 4)

```python
def legacy()
```

_No docstring._

**Inputs:** _none_

**Loops:** _none_

**Calls:** _none_

**Called by:** _none found_

## Module: `core/__init__.py`

**Dotted name:** `core` (package `__init__`)

**Module docstring:**

> Core package: re-exports the engine and the helpers.

**Imports:**

- `from .engine import Engine as Engine` (line 2) -> internal `core.engine`
- `from .util import *` (line 3) -> internal `core.util`

**Imported by:**

- `app` (lines 2, 4)

_No functions defined._

## Module: `core/engine.py`

**Dotted name:** `core.engine` (module)

**Module docstring:**

> Inheritance, super(), classmethods and nested functions.

**Imports:**

- `from .util import helper` (line 2) -> internal `core.util`

**Imported by:**

- `core` (line 2)

**Classes:**

- `Base` (line 5)
  - methods: `start`, `step`
- `Engine(Base)` (line 13)
  - methods: `__init__`, `step`, `build`

### `Base.start`  (line 6)

```python
def Base.start(self)
```

**Method of:** `Base`

_No docstring._

**Inputs:** `self`

**Loops:** _none_

**Calls:**

- `self.step()` (line 7) -> `core.engine.Base.step` [local]

**Called by:** _none found_

### `Base.step`  (line 9)

```python
def Base.step(self)
```

**Method of:** `Base`

_No docstring._

**Inputs:** `self`

**Loops:** _none_

**Calls:** _none_

**Called by:**

- `core.engine.Base.start` (line 7)
- `core.engine.Engine.step` (line 18)

### `Engine.__init__`  (line 14)

```python
def Engine.__init__(self)
```

**Method of:** `Engine`

_No docstring._

**Inputs:** `self`

**Loops:** _none_

**Calls:**

- `super().__init__()` (line 15) -> `builtins.object.__init__` [external: builtin, via super()]
- `super()` (line 15) -> `builtins.super` [external: builtin]

**Called by:**

- `app.run` (line 14)
- `core.engine.Engine.build` (line 22)

### `Engine.step`  (line 17)

```python
def Engine.step(self)
```

**Method of:** `Engine`

_No docstring._

**Inputs:** `self`

**Loops:** _none_

**Calls:**

- `helper()` (line 18) -> `core.util.helper` [internal]
- `super().step()` (line 18) -> `core.engine.Base.step` [local: via super()]
- `super()` (line 18) -> `builtins.super` [external: builtin]

**Called by:**

- `app.run` (line 14)

### `Engine.build`  (line 21)

```python
def Engine.build(cls)
```

**Method of:** `Engine`

**Decorators:** `@classmethod`

_No docstring._

**Inputs:** `cls`

**Loops:** _none_

**Calls:**

- `cls()` (line 22) -> `core.engine.Engine.__init__` [local: instantiates Engine]

**Called by:**

- `app.run` (line 10)

### `outer`  (line 25)

```python
def outer()
```

_No docstring._

**Inputs:** _none_

**Loops:** _none_

**Calls:**

- `inner()` (line 28) -> `core.engine.outer.inner` [local]

**Called by:** _none found_

### `outer.inner`  (line 26)

```python
def outer.inner()
```

_No docstring._

**Inputs:** _none_

**Loops:** _none_

**Calls:**

- `helper()` (line 27) -> `core.util.helper` [internal]

**Called by:**

- `core.engine.outer` (line 28)

## Module: `core/loop_a.py`

**Dotted name:** `core.loop_a` (module)

**Module docstring:**

> Half of a circular alias.

**Imports:**

- `from .loop_b import y as x` (line 2) -> internal `core.loop_b`

**Imported by:**

- `core.loop_b` (line 2)

### `use_x`  (line 5)

```python
def use_x()
```

_No docstring._

**Inputs:** _none_

**Loops:** _none_

**Calls:**

- `x()` (line 6) -> unresolved (cycle): `core.loop_b.y`: circular alias or re-export

**Called by:** _none found_

## Module: `core/loop_b.py`

**Dotted name:** `core.loop_b` (module)

**Module docstring:**

> Other half of a circular alias.

**Imports:**

- `from .loop_a import x as y` (line 2) -> internal `core.loop_a`

**Imported by:**

- `core.loop_a` (line 2)

_No functions defined._

## Module: `core/util.py`

**Dotted name:** `core.util` (module)

**Module docstring:**

> Helpers and a module-level alias.

**Imports:** _none_

**Imported by:**

- `app` (line 5)
- `core` (line 3)
- `core.engine` (line 2)

**Module-level aliases (candidates):**

- `alias_helper` = `helper` (line 9)

### `helper`  (line 5)

```python
def helper()
```

_No docstring._

**Inputs:** _none_

**Loops:** _none_

**Calls:** _none_

**Called by:**

- `app.run` (lines 12, 13)
- `core.engine.Engine.step` (line 18)
- `core.engine.outer.inner` (line 27)

## Module: `nsdir/mod.py`

**Dotted name:** `nsdir.mod` (module)

_No module docstring._

**Imports:** _none_

**Imported by:**

- `app` (line 6)

### `ns_func`  (line 1)

```python
def ns_func()
```

_No docstring._

**Inputs:** _none_

**Loops:** _none_

**Calls:** _none_

**Called by:**

- `app.run` (line 15)

## Module: `stubs/fast.pyi`

**Dotted name:** `stubs.fast` (module)

_No module docstring._

**Imports:** _none_

**Imported by:** _none found_

### `speed`  (line 1)

```python
def speed() -> int
```

_No docstring._

**Inputs:** _none_

**Loops:** _none_

**Calls:** _none_

**Called by:** _none found_

## Module: `stubs/slow.py`

**Dotted name:** `stubs.slow` (module)

_No module docstring._

**Imports:** _none_

**Imported by:** _none found_

### `crawl`  (line 1)

```python
def crawl()
```

_No docstring._

**Inputs:** _none_

**Loops:** _none_

**Calls:** _none_

**Called by:** _none found_

## Symbol table

| Symbol | Kind | Line |
|---|---|---:|
| `app.deep_relative` | function | 23 |
| `app.run` | function | 9 |
| `app.shadow` | function | 19 |
| `cookie.with_cookie` | function | 5 |
| `core.engine.Base` | class | 5 |
| `core.engine.Base.start` | method | 6 |
| `core.engine.Base.step` | method | 9 |
| `core.engine.Engine` | class | 13 |
| `core.engine.Engine.__init__` | method | 14 |
| `core.engine.Engine.build` | method | 21 |
| `core.engine.Engine.step` | method | 17 |
| `core.engine.outer` | function | 25 |
| `core.engine.outer.inner` | function | 26 |
| `core.loop_a.use_x` | function | 5 |
| `core.util.helper` | function | 5 |
| `legacy.legacy` | function | 4 |
| `nsdir.mod.ns_func` | function | 1 |
| `stubs.fast.speed` | function | 1 |
| `stubs.slow.crawl` | function | 1 |
