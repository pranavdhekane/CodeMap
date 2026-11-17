"""Cache: imports store inside a function (deferred import cycle)."""
MEMO = {}


def get(key):
    from .store import load
    if key not in MEMO:
        MEMO[key] = load(key)
    return MEMO[key]
