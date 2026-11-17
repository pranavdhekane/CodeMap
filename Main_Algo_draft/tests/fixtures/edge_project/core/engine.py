"""Inheritance, super(), classmethods and nested functions."""
from .util import helper


class Base:
    def start(self):
        return self.step()

    def step(self):
        return 0


class Engine(Base):
    def __init__(self):
        super().__init__()

    def step(self):
        return helper() + super().step()

    @classmethod
    def build(cls):
        return cls()


def outer():
    def inner():
        return helper()
    return inner()
