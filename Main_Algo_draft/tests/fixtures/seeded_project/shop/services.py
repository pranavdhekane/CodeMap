"""Services: imports models at module level."""
from .models import Model


class Service:
    def __init__(self):
        self.model = Model()
