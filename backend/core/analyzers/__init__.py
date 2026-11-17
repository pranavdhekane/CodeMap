"""Algorithms live here. Every .py file in this folder is imported automatically,
so adding a new algorithm = adding a new file with an @register class."""

import importlib
import pkgutil

for _module in sorted(m.name for m in pkgutil.iter_modules(__path__)):
    importlib.import_module(f"{__name__}.{_module}")
