"""Markdown/wiki-brain ingestion."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from hermes_memory_os.db.store import MemoryStore

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")


def iter_markdown_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_file() and path.suffix.lower() == ".md":
            yield path
        elif path.is_dir():
            yield from sorted(path.rglob("*.md"))


def chunk_markdown(text: str, *, max_chars: int = 1800) -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []
    current_heading = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        content = "\n".join(line for line in buffer).strip()
        if content:
            chunks.extend(_split_large_chunk(content, current_heading, max_chars=max_chars))
        buffer = []

    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            flush()
            current_heading = match.group(2).strip()
            buffer.append(line)
            continue
        buffer.append(line)
    flush()
    return chunks


def ingest_paths(store: MemoryStore, paths: Iterable[Path]) -> dict[str, int]:
    files = list(iter_markdown_files(paths))
    indexed = 0
    skipped = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        chunks = chunk_markdown(text)
        _, created = store.upsert_source_file(
            source_path=str(path),
            source_type="markdown",
            title=path.stem,
            content=text,
            chunks=chunks,
        )
        if created:
            indexed += 1
        else:
            skipped += 1
    return {"files_seen": len(files), "indexed": indexed, "skipped": skipped}


def _split_large_chunk(text: str, heading: str | None, *, max_chars: int) -> list[dict[str, str]]:
    if len(text) <= max_chars:
        return [{"heading": heading or "", "text": text}]

    pieces = []
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    current = []
    current_len = 0
    for paragraph in paragraphs:
        if current and current_len + len(paragraph) + 2 > max_chars:
            pieces.append({"heading": heading or "", "text": "\n\n".join(current)})
            current = []
            current_len = 0
        current.append(paragraph)
        current_len += len(paragraph) + 2
    if current:
        pieces.append({"heading": heading or "", "text": "\n\n".join(current)})
    return pieces
