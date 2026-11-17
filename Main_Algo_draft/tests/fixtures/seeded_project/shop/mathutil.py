"""Recursion, mutual recursion and nested loops."""


def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)


def sum_factorials(n):
    total = 0
    for i in range(n):
        total += factorial(i)
    return total


def is_even(n):
    return True if n == 0 else is_odd(n - 1)


def is_odd(n):
    return False if n == 0 else is_even(n - 1)


def parity(n):
    return "even" if is_even(n) else "odd"


def grid(rows, cols):
    cells = []
    for r in range(rows):
        for c in range(cols):
            cells.append((r, c))
    return cells
