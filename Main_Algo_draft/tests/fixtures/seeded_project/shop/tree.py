"""Recursion through self (direct, but only likely: a subclass may override walk)."""


class Tree:
    def __init__(self, children=None):
        self.children = children or []

    def walk(self, depth=0):
        if depth > 3:
            return depth
        return self.walk(depth + 1)
