"""Fixed input and output format that every algorithm must follow.

The output mirrors the database design (Miro ER diagram). Algorithms refer to
symbols by their `stable_key` (a string unique inside one output); the engine
turns those keys into database ids when saving.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class StrictModel(BaseModel):
    """Reject unknown fields everywhere."""

    model_config = {"extra": "forbid"}


class AlgorithmInput(StrictModel):
    """What every algorithm receives."""

    project_path: str = Field(min_length=1)
    options: dict = Field(default_factory=dict)


class SignatureItem(StrictModel):
    role: Literal["parameter", "return", "exception"]
    name: str
    type: str | None = None
    position: int = 0


class SymbolOut(StrictModel):
    stable_key: str = Field(min_length=1)  # unique in the output, e.g. "pkg.mod.func"
    name: str
    kind: Literal["function", "class", "method", "module"]
    parent_key: str | None = None  # stable_key of the containing symbol
    signature: list[SignatureItem] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)


class FileOut(StrictModel):
    path: str  # relative to the project folder
    language: str = "python"
    content_hash: str | None = None
    symbols: list[SymbolOut] = Field(default_factory=list)


class EdgeOut(StrictModel):
    source_key: str
    target_key: str | None = None  # None when the target could not be resolved
    kind: Literal["calls", "imports", "inherits"]
    target_reference: str | None = None  # the raw name seen in the code
    resolution: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class FindingOut(StrictModel):
    type: str = Field(min_length=1)  # e.g. "dead_code", "import_cycle"
    severity: Literal["low", "medium", "high"]
    certainty: Literal["certain", "likely", "uncertain"]
    description: str
    symbol_keys: list[str] = Field(default_factory=list)


class AlgorithmOutput(StrictModel):
    """What every algorithm must return."""

    algorithm: str
    version: str
    files: list[FileOut] = Field(default_factory=list)
    edges: list[EdgeOut] = Field(default_factory=list)
    findings: list[FindingOut] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_symbol_references(self):
        """Every key used anywhere must point to a symbol defined in `files`."""
        keys = set()
        for file in self.files:
            for symbol in file.symbols:
                if symbol.stable_key in keys:
                    raise ValueError(f"Duplicate stable_key: {symbol.stable_key}")
                keys.add(symbol.stable_key)

        for file in self.files:
            for symbol in file.symbols:
                if symbol.parent_key is not None and symbol.parent_key not in keys:
                    raise ValueError(f"Unknown parent_key: {symbol.parent_key}")
        for edge in self.edges:
            if edge.source_key not in keys:
                raise ValueError(f"Unknown edge source_key: {edge.source_key}")
            if edge.target_key is not None and edge.target_key not in keys:
                raise ValueError(f"Unknown edge target_key: {edge.target_key}")
        for finding in self.findings:
            for key in finding.symbol_keys:
                if key not in keys:
                    raise ValueError(f"Unknown finding symbol key: {key}")
        return self
