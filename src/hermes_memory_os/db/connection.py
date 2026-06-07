"""SQLite connection helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .schema import SCHEMA_SQL


def connect(sqlite_path: Path) -> sqlite3.Connection:
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def initialize_schema(sqlite_path: Path) -> None:
    with connect(sqlite_path) as conn:
        conn.executescript(SCHEMA_SQL)
        _migrate_source_chunks(conn)


def _migrate_source_chunks(conn: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(source_chunks)").fetchall()
    }
    additions = {
        "speaker": "TEXT",
        "metadata_json": "TEXT",
        "chunking_version": "TEXT DEFAULT 'v1'",
        "embedding_provider": "TEXT",
        "embedding_model": "TEXT",
        "indexing_state": "TEXT DEFAULT 'pending'",
    }
    for column, definition in additions.items():
        if column not in columns:
            conn.execute(f"ALTER TABLE source_chunks ADD COLUMN {column} {definition}")
