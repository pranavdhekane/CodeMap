"""Every form of light type inference, plus cases that must stay unresolved."""
from typing import Optional

from .db import Database, connect


class Repo:
    store: Database                       # class-level annotation types instances

    def __init__(self):
        self.db = Database()              # instance attribute from a constructor call
        self.backup = connect()           # instance attribute from a return annotation

    def put(self, row):
        self.db.save(row)
        self.backup.save(row)
        self.store.save(row)


class SubRepo(Repo):
    def put_twice(self, row):
        self.db.save(row)                 # attribute type inherited from Repo


def use_param(db: Database):
    db.save(1)


def use_optional(db: Optional[Database] = None):
    db.save(2)


def use_local():
    d = Database()
    d.save(3)
    c = d.cursor()                        # method return annotation (a string)
    c.execute()


def use_with():
    with Database() as conn:
        conn.save(4)


GLOBAL_DB = Database()


def use_global():
    GLOBAL_DB.save(5)


def ambiguous(flag):
    x = Database()
    if flag:
        x = 5
    x.save(6)                             # x is bound to two different things: stays unresolved


def rebound(db: Database):
    db = object()
    db.save(7)                            # parameter re-bound: the annotation no longer holds


def container(items: "list[Database]"):
    items.save(8)                         # a list of Database is not a Database
