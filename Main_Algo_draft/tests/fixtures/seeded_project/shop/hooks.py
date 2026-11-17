"""A function that is only passed around as a value."""


def on_done(result):
    return result


def register(callback):
    return callback


HANDLER = register(on_done)
