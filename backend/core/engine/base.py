"""Base class every algorithm must extend."""

from .schemas import AlgorithmInput, AlgorithmOutput


class Algorithm:
    """Subclass this, set name and version, and implement run()."""

    name: str = ""
    version: str = "1.0"
    input_model = AlgorithmInput  # an algorithm may use a subclass of AlgorithmInput

    def run(self, data: AlgorithmInput) -> AlgorithmOutput:
        raise NotImplementedError("Algorithm must implement run()")
