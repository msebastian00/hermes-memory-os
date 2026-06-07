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
