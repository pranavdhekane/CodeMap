"""Billing: closes an import-time cycle with orders, and holds a dead call cycle."""
from .orders import TAX_RATE


def round_money(value):
    return round(value, 2)


def charge(amount):
    return round_money(amount * (1 + TAX_RATE))


def refund(amount):
    if amount > 10:
        return partial_refund(amount / 2)
    return amount


def partial_refund(amount):
    return refund(amount)
