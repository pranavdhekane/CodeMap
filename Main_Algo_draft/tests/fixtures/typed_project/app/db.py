"""Classes whose methods are called through typed variables."""


class Cursor:
    def execute(self):
        return 1


class Database:
    def save(self, row):
        return row

    def cursor(self) -> "Cursor":
        return Cursor()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def connect() -> Database:
    return Database()
