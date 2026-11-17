"""Inheritance: an overridden base method, and a class that only inherits __init__."""


class Base:
    def run(self):
        return "base"


class Child(Base):
    def run(self):
        return "child"


class Engine:
    def __init__(self):
        self.speed = 1


class Turbo(Engine):
    pass
