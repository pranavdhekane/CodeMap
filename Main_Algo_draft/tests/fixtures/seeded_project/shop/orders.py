"""Orders: loops, dead helpers, an unused import and an import-time cycle with billing."""
import os
from . import billing

TAX_RATE = 0.2
__all__ = ["place_order"]


def price_of(item):
    total = 0
    for part in item:
        total += part
    return total


def place_order(items):
    for item in items:
        price_of(item)
    return billing.charge(len(items))


def quote(item):
    return price_of(item) * 2


def total_cost(items):
    result = 0
    for item in items:
        result += quote(item)
    return result


def _unused_helper():
    return 1


def _dead_root():
    return _only_from_dead()


def _only_from_dead():
    return 2


def public_dead():
    return 3
