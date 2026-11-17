"""Models: imports services only for type checking (typing-only cycle)."""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .services import Service


class Model:
    def __init__(self, service: "Service" = None):
        self.service = service
