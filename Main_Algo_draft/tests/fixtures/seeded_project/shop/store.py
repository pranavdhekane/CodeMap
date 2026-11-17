"""Store: imports cache at module level."""
from . import cache


def load(key):
    return cache.get(key)
