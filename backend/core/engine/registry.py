"""Registry of available algorithms. New algorithms plug in here via @register."""

from .base import Algorithm

_ALGORITHMS: dict[str, type[Algorithm]] = {}


def register(cls: type[Algorithm]) -> type[Algorithm]:
    """Class decorator: add an algorithm to the registry under its name."""
    if not cls.name:
        raise ValueError("Algorithm must have a name")
    if cls.name in _ALGORITHMS:
        raise ValueError(f"Algorithm '{cls.name}' is already registered")
    _ALGORITHMS[cls.name] = cls
    return cls


def get_algorithm(name: str) -> Algorithm:
    """Return a new instance of the named algorithm."""
    if name not in _ALGORITHMS:
        raise KeyError(f"Unknown algorithm: {name}")
    return _ALGORITHMS[name]()


def list_algorithms() -> list[str]:
    return sorted(_ALGORITHMS)
