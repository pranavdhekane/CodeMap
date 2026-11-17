"""Half of a circular alias."""
from .loop_b import y as x


def use_x():
    return x()
