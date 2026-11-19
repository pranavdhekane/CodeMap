"""Algorithm basic_algo_1: AST-based static analysis for Python projects.

Uses the POC code_mapper static analysis pipeline to extract modules, classes,
functions, methods, call graphs, import graphs, inheritance, and code findings
(cycles, dead code, unused imports, recursion), returning a validated
AlgorithmOutput conforming to the CodeMap database and engine schemas.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Any

# Ensure repository root is on sys.path so Main_Algo_draft is always importable
_REPO_ROOT = str(Path(__file__).resolve().parents[3])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from Main_Algo_draft import code_mapper  # noqa: E402
from ..engine import (  # noqa: E402
    Algorithm,
    AlgorithmInput,
    AlgorithmOutput,
    EdgeOut,
    FileOut,
    FindingOut,
    SignatureItem,
    SymbolOut,
    register,
)
from ..engine.validation import SKIP_DIRS  # noqa: E402

LONG_FILE_THRESHOLD = 500


@register
class BasicAlgo1(Algorithm):
    name = "basic_algo_1"
    version = "1.0"

    def run(self, data: AlgorithmInput) -> AlgorithmOutput:
        project_root = os.path.abspath(data.project_path)
        options = data.options or {}

        # Parse user options with sensible defaults
        ignore_patterns = list(options.get("ignore", []))
        min_confidence = options.get("min_confidence", "uncertain")
        max_bytes = int(options.get("max_bytes", code_mapper.MAX_FILE_BYTES))

        # Run the full POC AST pipeline
        pipeline_result = code_mapper.run_pipeline(
            project_root,
            ignore=ignore_patterns,
            analyze=True,
            min_confidence=min_confidence,
            max_bytes=max_bytes,
            skip_dirs=SKIP_DIRS,
        )

        files: list[FileOut] = []
        known_keys: set[str] = set()

        # Phase 1: Build Files and Symbols
        for mod in pipeline_result.modules:
            rel_path = mod.path.replace("\\", "/")
            full_path = os.path.join(project_root, mod.path)

            content_hash: str | None = None
            if os.path.isfile(full_path):
                try:
                    with open(full_path, "rb") as fh:
                        content_hash = hashlib.sha256(fh.read()).hexdigest()
                except OSError:
                    content_hash = None

            mod_key = mod.module_name
            symbols: list[SymbolOut] = []

            # Module symbol
            if mod_key not in known_keys:
                known_keys.add(mod_key)
                symbols.append(
                    SymbolOut(
                        stable_key=mod_key,
                        name=mod.module_name.split(".")[-1],
                        kind="module",
                        parent_key=None,
                        metrics={"lines": float(mod.line_count)},
                    )
                )

            # Class symbols
            for cls in mod.classes:
                cls_key = f"{mod.module_name}.{cls.qualified_name}"
                if cls_key in known_keys:
                    continue
                known_keys.add(cls_key)

                # Determine parent: enclosing class if nested, otherwise module
                if "." in cls.qualified_name:
                    parent_candidate = f"{mod.module_name}.{cls.qualified_name.rsplit('.', 1)[0]}"
                    parent_key = parent_candidate if parent_candidate in known_keys else mod_key
                else:
                    parent_key = mod_key

                symbols.append(
                    SymbolOut(
                        stable_key=cls_key,
                        name=cls.name,
                        kind="class",
                        parent_key=parent_key,
                        metrics={
                            "methods": float(len(cls.methods)),
                            "bases": float(len(cls.bases)),
                        },
                    )
                )

            # Function and method symbols
            for fn in mod.functions:
                fn_key = f"{mod.module_name}.{fn.qualified_name}"
                if fn_key in known_keys:
                    continue
                known_keys.add(fn_key)

                is_method = bool(fn.enclosing_class)
                if fn.enclosing_class:
                    parent_candidate = f"{mod.module_name}.{fn.enclosing_class}"
                    parent_key = parent_candidate if parent_candidate in known_keys else mod_key
                elif "." in fn.qualified_name:
                    parent_candidate = f"{mod.module_name}.{fn.qualified_name.rsplit('.', 1)[0]}"
                    parent_key = parent_candidate if parent_candidate in known_keys else mod_key
                else:
                    parent_key = mod_key

                # Signatures
                sig_items: list[SignatureItem] = []
                for idx, arg_str in enumerate(fn.args):
                    param_name = arg_str.split(":")[0].split("=")[0].strip()
                    param_type = fn.param_types.get(param_name)
                    if param_type:
                        if param_type.startswith("ann:"):
                            param_type = param_type[4:].strip()
                        elif param_type.startswith("call:"):
                            param_type = param_type[5:].strip()
                    elif ":" in arg_str:
                        param_type = arg_str.split(":", 1)[1].split("=")[0].strip()

                    sig_items.append(
                        SignatureItem(
                            role="parameter",
                            name=param_name,
                            type=param_type,
                            position=idx,
                        )
                    )

                if fn.returns:
                    sig_items.append(
                        SignatureItem(
                            role="return",
                            name="",
                            type=fn.returns,
                            position=0,
                        )
                    )

                fn_lines = float(fn.end_line - fn.line + 1 if fn.end_line else 0)
                symbols.append(
                    SymbolOut(
                        stable_key=fn_key,
                        name=fn.name,
                        kind="method" if is_method else "function",
                        parent_key=parent_key,
                        signature=sig_items,
                        metrics={
                            "lines": fn_lines,
                            "calls": float(len(fn.calls)),
                            "loops": float(len(fn.loops)),
                        },
                    )
                )

            files.append(
                FileOut(
                    path=rel_path,
                    language="python",
                    content_hash=content_hash,
                    symbols=symbols,
                )
            )

        # Phase 2: Build Edges
        edges: list[EdgeOut] = []
        seen_edges: set[tuple[str, str | None, str, str | None]] = set()

        def add_edge(
            src: str,
            dst: str | None,
            kind: str,
            target_ref: str | None = None,
            resolution: str | None = None,
            confidence: float = 1.0,
        ) -> None:
            if src not in known_keys:
                return
            target_key = dst if (dst and dst in known_keys) else None
            edge_tuple = (src, target_key, kind, target_ref)
            if edge_tuple in seen_edges:
                return
            seen_edges.add(edge_tuple)
            edges.append(
                EdgeOut(
                    source_key=src,
                    target_key=target_key,
                    kind=kind,  # type: ignore[arg-type]
                    target_reference=target_ref,
                    resolution=resolution,
                    confidence=confidence,
                )
            )

        # 2a: Inherits edges from class bases
        resolver = pipeline_result.resolver
        for mod in pipeline_result.modules:
            for cls in mod.classes:
                cls_key = f"{mod.module_name}.{cls.qualified_name}"
                if cls_key not in known_keys:
                    continue
                resolved_bases = resolver._class_bases(cls_key)
                for res_kind, ref in resolved_bases:
                    add_edge(
                        src=cls_key,
                        dst=ref if res_kind == "internal" else None,
                        kind="inherits",
                        target_ref=ref,
                        resolution=res_kind,
                        confidence=1.0,
                    )

        # 2b: Import edges between modules
        if "import" in pipeline_result.graphs:
            for (src_mod, dst_mod), edge_info in pipeline_result.graphs["import"].edges.items():
                add_edge(
                    src=src_mod,
                    dst=dst_mod if dst_mod in known_keys else None,
                    kind="imports",
                    target_ref=dst_mod,
                    resolution="internal" if dst_mod in known_keys else "external",
                    confidence=1.0,
                )

        # 2c: Call edges from call graph and functions
        if "call" in pipeline_result.graphs:
            for (src, dst), edge_info in pipeline_result.graphs["call"].edges.items():
                source_key = src
                if source_key not in known_keys and source_key.endswith(".<module>"):
                    source_key = source_key[:-len(".<module>")]
                if source_key not in known_keys and source_key.endswith(".__main__"):
                    source_key = source_key[:-len(".__main__")]

                sites = edge_info.get("sites", [{}])
                target_ref = sites[0].get("name", dst) if sites else dst

                add_edge(
                    src=source_key,
                    dst=dst if dst in known_keys else None,
                    kind="calls",
                    target_ref=target_ref,
                    resolution="internal" if dst in known_keys else "external",
                    confidence=1.0,
                )

        # 2d: External/unresolved calls recorded on functions
        for mod in pipeline_result.modules:
            for fn in mod.functions:
                fn_key = f"{mod.module_name}.{fn.qualified_name}"
                if fn_key not in known_keys:
                    continue
                for call in fn.calls:
                    if call.status in ("external", "builtin", "unresolved"):
                        add_edge(
                            src=fn_key,
                            dst=None,
                            kind="calls",
                            target_ref=call.name,
                            resolution=call.status,
                            confidence=0.5 if call.status == "unresolved" else 0.9,
                        )

        # Phase 3: Build Findings
        findings: list[FindingOut] = []
        analysis = pipeline_result.analysis or {}

        # 3a: Import Cycles
        for cycle in analysis.get("cycles", {}).get("import", []):
            members = [m for m in cycle.get("members", []) if m in known_keys]
            cycle_kind = cycle.get("kind", "")
            severity = "high" if cycle_kind == "import-time" else ("medium" if cycle_kind == "deferred" else "low")
            certainty = cycle.get("confidence", "certain")
            example = " -> ".join(cycle.get("example_cycle", members))
            findings.append(
                FindingOut(
                    type="import_cycle",
                    severity=severity,
                    certainty=certainty if certainty in ("certain", "likely", "uncertain") else "certain",
                    description=f"Import cycle ({cycle_kind}): {example}",
                    symbol_keys=members,
                )
            )

        # 3b: Call Cycles
        for cycle in analysis.get("cycles", {}).get("call", []):
            members = [m for m in cycle.get("members", []) if m in known_keys]
            certainty = cycle.get("confidence", "certain")
            example = " -> ".join(cycle.get("example_cycle", members))
            findings.append(
                FindingOut(
                    type="call_cycle",
                    severity="high",
                    certainty=certainty if certainty in ("certain", "likely", "uncertain") else "certain",
                    description=f"Call cycle of size {cycle.get('size', len(members))}: {example}",
                    symbol_keys=members,
                )
            )

        # 3c: Recursion
        rec = analysis.get("recursion", {})
        for r in rec.get("direct", []):
            sym_id = r.get("id")
            keys = [sym_id] if sym_id in known_keys else []
            certainty = r.get("confidence", "certain")
            findings.append(
                FindingOut(
                    type="recursion",
                    severity="medium",
                    certainty=certainty if certainty in ("certain", "likely", "uncertain") else "certain",
                    description=f"Direct recursion in '{sym_id}' at line(s) {r.get('call_lines', [])}",
                    symbol_keys=keys,
                )
            )

        for r in rec.get("indirect", []):
            sym_id = r.get("id")
            keys = [sym_id] if sym_id in known_keys else []
            certainty = r.get("confidence", "certain")
            findings.append(
                FindingOut(
                    type="indirect_recursion",
                    severity="medium",
                    certainty=certainty if certainty in ("certain", "likely", "uncertain") else "certain",
                    description=f"Indirect recursion in '{sym_id}' via cycle {r.get('cycle', '')}",
                    symbol_keys=keys,
                )
            )

        # 3d: Dead Code
        for d in analysis.get("dead_code", []):
            sym_id = d.get("id")
            keys = [sym_id] if sym_id in known_keys else []
            confidence = d.get("confidence", "likely")
            reasons = "; ".join(d.get("reasons", []))
            category = d.get("category", "unreachable")
            findings.append(
                FindingOut(
                    type="dead_code",
                    severity="low" if confidence == "uncertain" else "medium",
                    certainty=confidence if confidence in ("certain", "likely", "uncertain") else "likely",
                    description=f"Unreferenced {d.get('kind', 'symbol')} '{sym_id}' ({category}): {reasons}",
                    symbol_keys=keys,
                )
            )

        # 3e: Import Issues (unused and missing)
        imp_issues = analysis.get("imports", {})
        for u in imp_issues.get("unused", []):
            mod_key = u.get("module")
            keys = [mod_key] if mod_key in known_keys else []
            findings.append(
                FindingOut(
                    type="unused_import",
                    severity="low",
                    certainty="certain",
                    description=f"Unused import '{u.get('name')}' in {mod_key} ({u.get('statement')})",
                    symbol_keys=keys,
                )
            )

        for m in imp_issues.get("missing", []):
            mod_key = m.get("module")
            keys = [mod_key] if mod_key in known_keys else []
            findings.append(
                FindingOut(
                    type="missing_import",
                    severity="high",
                    certainty="likely",
                    description=f"Missing module '{m.get('name')}' in {mod_key}: {m.get('reason')}",
                    symbol_keys=keys,
                )
            )

        # 3f: Flag files exceeding threshold
        for mod in pipeline_result.modules:
            if mod.line_count > LONG_FILE_THRESHOLD and mod.module_name in known_keys:
                findings.append(
                    FindingOut(
                        type="long_file",
                        severity="low",
                        certainty="certain",
                        description=f"Module '{mod.module_name}' is {mod.line_count} lines long (threshold: {LONG_FILE_THRESHOLD})",
                        symbol_keys=[mod.module_name],
                    )
                )

        return AlgorithmOutput(
            algorithm=self.name,
            version=self.version,
            files=files,
            edges=edges,
            findings=findings,
        )
