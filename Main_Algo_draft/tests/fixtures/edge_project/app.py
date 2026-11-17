"""Application module: every way of reaching core."""
import core
import nsdir
from core import Engine, helper
from core.util import alias_helper
from nsdir import mod


def run():
    engine = Engine.build()
    engine.start()
    core.helper()
    alias_helper()
    Engine().step()
    mod.ns_func()
    return nsdir


def shadow(helper):
    return helper()


def deep_relative():
    from .. import nowhere
    return nowhere()


if __name__ == "__main__":
    run()
