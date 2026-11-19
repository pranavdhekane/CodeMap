"""SQLite storage that follows the Miro ER design (plain sqlite3).

Tables: project, analysis_run, file, symbol, signature_item, metric, edge,
finding, finding_symbol.
"""

import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "..", "codemap.db")


def _db_path() -> str:
    return os.getenv("CODEMAP_DB", DEFAULT_DB)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    """Create the tables if they do not exist yet."""
    conn = _connect()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS project (
            project_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            repo_url TEXT
        );
        CREATE TABLE IF NOT EXISTS analysis_run (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES project(project_id),
            commit_hash TEXT,
            scanned_at TEXT NOT NULL,
            status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS file (
            file_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES analysis_run(run_id),
            path TEXT NOT NULL,
            language TEXT,
            content_hash TEXT
        );
        CREATE TABLE IF NOT EXISTS symbol (
            symbol_id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL REFERENCES file(file_id),
            parent_symbol_id INTEGER REFERENCES symbol(symbol_id),
            stable_key TEXT NOT NULL,
            name TEXT NOT NULL,
            kind TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS signature_item (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol_id INTEGER NOT NULL REFERENCES symbol(symbol_id),
            role TEXT NOT NULL,
            name TEXT,
            type TEXT,
            position INTEGER
        );
        CREATE TABLE IF NOT EXISTS metric (
            metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol_id INTEGER NOT NULL REFERENCES symbol(symbol_id),
            name TEXT NOT NULL,
            value REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS edge (
            edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_symbol_id INTEGER NOT NULL REFERENCES symbol(symbol_id),
            target_symbol_id INTEGER REFERENCES symbol(symbol_id),
            kind TEXT NOT NULL,
            target_reference TEXT,
            resolution TEXT,
            confidence REAL
        );
        CREATE TABLE IF NOT EXISTS finding (
            finding_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES analysis_run(run_id),
            type TEXT NOT NULL,
            severity TEXT NOT NULL,
            certainty TEXT NOT NULL,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS finding_symbol (
            finding_id INTEGER NOT NULL REFERENCES finding(finding_id),
            symbol_id INTEGER NOT NULL REFERENCES symbol(symbol_id),
            PRIMARY KEY (finding_id, symbol_id)
        );
        """
    )
    conn.commit()
    conn.close()


# ---------- projects ----------

def create_project(name: str, description: str | None, repo_url: str | None) -> int:
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO project (name, description, repo_url) VALUES (?, ?, ?)",
        (name, description, repo_url),
    )
    conn.commit()
    project_id = cur.lastrowid
    conn.close()
    return project_id


def get_project(project_id: int) -> dict | None:
    conn = _connect()
    row = conn.execute("SELECT * FROM project WHERE project_id = ?", (project_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_projects() -> list[dict]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM project ORDER BY project_id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- runs ----------

def create_run(project_id: int, commit_hash: str | None) -> int:
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO analysis_run (project_id, commit_hash, scanned_at, status)"
        " VALUES (?, ?, ?, 'queued')",
        (project_id, commit_hash, _now()),
    )
    conn.commit()
    run_id = cur.lastrowid
    conn.close()
    return run_id


def set_status(run_id: int, status: str) -> None:
    conn = _connect()
    conn.execute("UPDATE analysis_run SET status = ? WHERE run_id = ?", (status, run_id))
    conn.commit()
    conn.close()


def save_results(run_id: int, output) -> None:
    """Save everything from a validated AlgorithmOutput in ONE transaction,
    then mark the run 'done'. If anything fails, nothing is saved."""
    conn = _connect()
    try:
        key_to_id = {}
        parents = []  # (symbol_id, parent_key) filled in after all symbols exist

        for file in output.files:
            cur = conn.execute(
                "INSERT INTO file (run_id, path, language, content_hash) VALUES (?, ?, ?, ?)",
                (run_id, file.path, file.language, file.content_hash),
            )
            file_id = cur.lastrowid

            for sym in file.symbols:
                cur = conn.execute(
                    "INSERT INTO symbol (file_id, stable_key, name, kind) VALUES (?, ?, ?, ?)",
                    (file_id, sym.stable_key, sym.name, sym.kind),
                )
                symbol_id = cur.lastrowid
                key_to_id[sym.stable_key] = symbol_id
                if sym.parent_key is not None:
                    parents.append((symbol_id, sym.parent_key))

                for item in sym.signature:
                    conn.execute(
                        "INSERT INTO signature_item (symbol_id, role, name, type, position)"
                        " VALUES (?, ?, ?, ?, ?)",
                        (symbol_id, item.role, item.name, item.type, item.position),
                    )
                for name, value in sym.metrics.items():
                    conn.execute(
                        "INSERT INTO metric (symbol_id, name, value) VALUES (?, ?, ?)",
                        (symbol_id, name, value),
                    )

        for symbol_id, parent_key in parents:
            conn.execute(
                "UPDATE symbol SET parent_symbol_id = ? WHERE symbol_id = ?",
                (key_to_id[parent_key], symbol_id),
            )

        for edge in output.edges:
            target_id = key_to_id[edge.target_key] if edge.target_key else None
            conn.execute(
                "INSERT INTO edge (source_symbol_id, target_symbol_id, kind,"
                " target_reference, resolution, confidence) VALUES (?, ?, ?, ?, ?, ?)",
                (key_to_id[edge.source_key], target_id, edge.kind,
                 edge.target_reference, edge.resolution, edge.confidence),
            )

        for finding in output.findings:
            cur = conn.execute(
                "INSERT INTO finding (run_id, type, severity, certainty, description)"
                " VALUES (?, ?, ?, ?, ?)",
                (run_id, finding.type, finding.severity, finding.certainty,
                 finding.description),
            )
            for key in sorted(set(finding.symbol_keys)):
                conn.execute(
                    "INSERT INTO finding_symbol (finding_id, symbol_id) VALUES (?, ?)",
                    (cur.lastrowid, key_to_id[key]),
                )

        conn.execute("UPDATE analysis_run SET status = 'done' WHERE run_id = ?", (run_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_run(run_id: int) -> dict | None:
    """Return the run with its files, symbols (with metrics), edges and findings."""
    conn = _connect()
    run = conn.execute("SELECT * FROM analysis_run WHERE run_id = ?", (run_id,)).fetchone()
    if run is None:
        conn.close()
        return None
    result = dict(run)

    result["files"] = [
        dict(r)
        for r in conn.execute(
            "SELECT file_id, path, language, content_hash FROM file"
            " WHERE run_id = ? ORDER BY file_id", (run_id,))
    ]

    symbols = []
    for r in conn.execute(
        "SELECT s.symbol_id, s.stable_key, s.name, s.kind, f.path AS file,"
        " p.stable_key AS parent_key FROM symbol s"
        " JOIN file f ON f.file_id = s.file_id"
        " LEFT JOIN symbol p ON p.symbol_id = s.parent_symbol_id"
        " WHERE f.run_id = ? ORDER BY s.symbol_id", (run_id,)):
        sym = dict(r)
        sym["metrics"] = {
            m["name"]: m["value"]
            for m in conn.execute(
                "SELECT name, value FROM metric WHERE symbol_id = ? ORDER BY metric_id",
                (sym["symbol_id"],))
        }
        sym["signature"] = [
            dict(i)
            for i in conn.execute(
                "SELECT role, name, type, position FROM signature_item"
                " WHERE symbol_id = ? ORDER BY item_id", (sym["symbol_id"],))
        ]
        del sym["symbol_id"]
        symbols.append(sym)
    result["symbols"] = symbols

    result["edges"] = [
        dict(r)
        for r in conn.execute(
            "SELECT s.stable_key AS source, t.stable_key AS target, e.kind,"
            " e.target_reference, e.resolution, e.confidence FROM edge e"
            " JOIN symbol s ON s.symbol_id = e.source_symbol_id"
            " JOIN file f ON f.file_id = s.file_id"
            " LEFT JOIN symbol t ON t.symbol_id = e.target_symbol_id"
            " WHERE f.run_id = ? ORDER BY e.edge_id", (run_id,))
    ]

    findings = []
    for r in conn.execute(
        "SELECT finding_id, type, severity, certainty, description FROM finding"
        " WHERE run_id = ? ORDER BY finding_id", (run_id,)):
        finding = dict(r)
        finding["symbols"] = [
            x["stable_key"]
            for x in conn.execute(
                "SELECT s.stable_key FROM finding_symbol fs"
                " JOIN symbol s ON s.symbol_id = fs.symbol_id"
                " WHERE fs.finding_id = ? ORDER BY s.symbol_id", (finding["finding_id"],))
        ]
        findings.append(finding)
    result["findings"] = findings

    conn.close()
    return result
