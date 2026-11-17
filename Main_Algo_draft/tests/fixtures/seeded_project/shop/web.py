"""Web handler: calls into most of the package, has an unused and a missing import."""
from framework import app

from . import orders
from .nonexistent import thing
from .mathutil import grid, parity, sum_factorials
from .plugins import Child, Turbo
from .services import Service
from .store import load
from .tree import Tree


@app.route("/")
def index():
    load("key")
    parity(3)
    sum_factorials(3)
    grid(2, 2)
    Service()
    Tree().walk()
    Child()
    Turbo()
    return thing()
