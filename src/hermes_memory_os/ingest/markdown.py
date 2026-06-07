"""Markdown/wiki-brain ingestion compatibility wrappers."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from hermes_memory_os.db.store import MemoryStore
from hermes_memory_os.ingest.sources import chunk_markdown, ingest_paths as ingest_source_paths


def iter_markdown_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_file() and path.suffix.lower() == ".md":
            yield path
        elif path.is_dir():
            yield from sorted(path.rglob("*.md"))


def ingest_paths(store: MemoryStore, paths: Iterable[Path]) -> dict[str, int]:
    return ingest_source_paths(store, paths, source_type="wiki")
