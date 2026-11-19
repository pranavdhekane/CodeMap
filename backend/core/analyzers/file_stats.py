"""Example algorithm: one module symbol per Python file, with a line count.
Flags very long files. Copy this file as a template for new algorithms.
"""

import hashlib
import os

from ..engine import (
    Algorithm,
    AlgorithmInput,
    AlgorithmOutput,
    FileOut,
    FindingOut,
    SymbolOut,
    register,
)
from ..engine.validation import SKIP_DIRS

LONG_FILE_LINES = 500


@register
class FileStats(Algorithm):
    name = "file_stats"
    version = "1.0"

    def run(self, data: AlgorithmInput) -> AlgorithmOutput:
        files = []
        findings = []

        for root, dirs, names in os.walk(data.project_path):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for name in sorted(names):
                if not name.endswith(".py"):
                    continue
                full_path = os.path.join(root, name)
                rel_path = os.path.relpath(full_path, data.project_path)

                with open(full_path, "rb") as f:
                    raw = f.read()
                lines = raw.count(b"\n") + (1 if raw and not raw.endswith(b"\n") else 0)

                files.append(
                    FileOut(
                        path=rel_path,
                        content_hash=hashlib.sha256(raw).hexdigest(),
                        symbols=[
                            SymbolOut(
                                stable_key=rel_path,
                                name=name,
                                kind="module",
                                metrics={"lines": float(lines)},
                            )
                        ],
                    )
                )
                if lines > LONG_FILE_LINES:
                    findings.append(
                        FindingOut(
                            type="long_file",
                            severity="low",
                            certainty="certain",
                            description=f"File has {lines} lines",
                            symbol_keys=[rel_path],
                        )
                    )

        return AlgorithmOutput(
            algorithm=self.name, version=self.version, files=files, findings=findings
        )
