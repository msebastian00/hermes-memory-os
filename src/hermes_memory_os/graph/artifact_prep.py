"""Deterministic preparation of graph artifacts from already-reviewed book sources."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from hermes_memory_os.utils import now_iso

from .builder import _find_manifest, _find_source_page, _parse_claims, _parse_retrieval_chunks, _read_frontmatter
from .config import GraphConfig

GENERATOR = "hermes-graph-artifact-prep-v1"
DEFAULT_MAX_INPUT_CHARS = 6000
_SECTION_RANGE = re.compile(r"\d+\s*[-–]\s*\d+")


class ArtifactPreparationError(ValueError):
    """Raised when a queued book cannot safely receive derived graph artifacts."""


def embedding_input_limit(memory_app: Any | None = None, override: int | None = None) -> int:
    """Return the configured embedding input limit in Unicode characters."""

    if override is not None:
        return _require_limit(override)
    if memory_app is not None:
        configured = getattr(getattr(memory_app, "config", None), "embeddings", {}) or {}
        raw = configured.get("max_input_chars")
        if raw is not None:
            return _require_limit(int(raw))
    env = os.environ.get("HERMES_EMBEDDING_MAX_INPUT_CHARS")
    if env:
        return _require_limit(int(env))
    return DEFAULT_MAX_INPUT_CHARS


def prepare_book_artifacts(
    config: GraphConfig,
    source_id: str,
    *,
    write_mode: str = "dry_run",
    max_chunk_chars: int | None = None,
    memory_app: Any | None = None,
) -> dict[str, Any]:
    """Plan or write deterministic retrieval and exact-span artifacts for one book.

    Oversized chunks are split before any embedding. Every child keeps an exact
    raw-source span; vector text must equal that span.
    """

    if write_mode not in {"dry_run", "upsert"}:
        raise ArtifactPreparationError("write_mode must be dry_run or upsert")
    limit = embedding_input_limit(memory_app, max_chunk_chars)
    from .autopromote import is_queued_book_source

    if not is_queued_book_source(config.vault_root, source_id):
        raise ArtifactPreparationError(f"source_id is not present in the book-ingestion queue: {source_id}")

    source_page = _find_source_page(config.vault_root, source_id)
    source_metadata, source_body = _read_frontmatter(source_page)
    if not _parse_claims(source_body):
        raise ArtifactPreparationError("canonical source page has no reviewed claims/evidence section")
    manifest_path = _find_manifest(config.vault_root, source_id)
    manifest, _ = _read_frontmatter(manifest_path)
    raw_relative_path = str(manifest.get("source_path") or manifest.get("original_path") or "")
    raw_path = config.vault_root / raw_relative_path
    if not raw_relative_path or not raw_path.is_file():
        raise ArtifactPreparationError(f"missing immutable raw source: {raw_path}")
    raw_text = raw_path.read_text(encoding="utf-8")
    raw_hash = _sha256(raw_text)
    manifest_hash = str(manifest.get("content_hash") or "")
    if manifest_hash and raw_hash != manifest_hash:
        raise ArtifactPreparationError("raw source hash does not match its manifest")

    output_root = config.vault_root / "06_GENERATED" / "source-analysis" / source_id
    chunks_path = output_root / "retrieval-chunks.md"
    bodies_path = output_root / "chunk-bodies.json"
    title = str(source_metadata.get("title") or manifest.get("title") or source_id)
    authors = source_metadata.get("authors") or manifest.get("authors") or manifest.get("author") or []
    chunks = _plan_chunks(source_id, title, authors, raw_text, raw_hash, limit, chunks_path, bodies_path)
    for item in chunks:
        if item["text"] != raw_text[item["span_start"] : item["span_end"]]:
            raise ArtifactPreparationError(f"planned chunk {item['chunk_id']} is not an exact raw span")
        if len(item["text"]) > limit:
            raise ArtifactPreparationError(f"planned chunk {item['chunk_id']} exceeds embedding input limit {limit}")

    metadata = [{key: value for key, value in item.items() if key != "text"} for item in chunks]
    bodies = {
        "source_id": source_id,
        "raw_content_hash": raw_hash,
        "generated_at": now_iso(),
        "generated_by": GENERATOR,
        "max_input_chars": limit,
        "chunks": [
            {
                "chunk_id": item["chunk_id"],
                "text": item["text"],
                "span_start": item["span_start"],
                "span_end": item["span_end"],
                "source_id": source_id,
                "raw_content_hash": raw_hash,
            }
            for item in chunks
        ],
    }
    result = {
        "status": "planned" if write_mode == "dry_run" else "prepared",
        "write_mode": write_mode,
        "source_id": source_id,
        "raw_source_path": raw_relative_path,
        "raw_content_hash": raw_hash,
        "max_input_chars": limit,
        "chunk_count": len(metadata),
        "retrieval_chunks_path": str(chunks_path),
        "chunk_bodies_path": str(bodies_path),
        "split_oversized": any("__p" in item["chunk_id"] for item in chunks),
    }
    if write_mode == "dry_run":
        return result

    output_root.mkdir(parents=True, exist_ok=True)
    _atomic_write(chunks_path, _retrieval_chunks_document(source_id, title, metadata, limit))
    _atomic_write(bodies_path, json.dumps(bodies, indent=2, sort_keys=True) + "\n")
    return result


def _plan_chunks(
    source_id: str,
    title: str,
    authors: Any,
    raw_text: str,
    raw_hash: str,
    limit: int,
    chunks_path: Path,
    bodies_path: Path,
) -> list[dict[str, Any]]:
    existing = _load_existing_exact_chunks(raw_text, raw_hash, source_id, chunks_path, bodies_path)
    if existing is not None:
        return _reindex(_split_existing(existing, raw_text, limit, source_id, title, authors))
    return _chunk_metadata(source_id, title, authors, raw_text, limit)


def _load_existing_exact_chunks(
    raw_text: str,
    raw_hash: str,
    source_id: str,
    chunks_path: Path,
    bodies_path: Path,
) -> list[dict[str, Any]] | None:
    if not chunks_path.is_file() or not bodies_path.is_file():
        return None
    try:
        payload = json.loads(bodies_path.read_text(encoding="utf-8"))
        metadata = _parse_retrieval_chunks(chunks_path)
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("source_id") != source_id:
        return None
    if payload.get("raw_content_hash") and payload.get("raw_content_hash") != raw_hash:
        return None
    bodies = payload.get("chunks")
    if not isinstance(bodies, list) or not metadata:
        return None
    by_id = {str(item.get("chunk_id")): item for item in bodies if isinstance(item, dict)}
    loaded: list[dict[str, Any]] = []
    for meta in metadata:
        chunk_id = str(meta.get("chunk_id") or "")
        body = by_id.get(chunk_id)
        if not body:
            return None
        start, end, text = body.get("span_start"), body.get("span_end"), body.get("text")
        if not isinstance(start, int) or not isinstance(end, int) or not isinstance(text, str):
            return None
        if start < 0 or end <= start or raw_text[start:end] != text:
            return None
        merged = dict(meta)
        merged.update({"chunk_id": chunk_id, "span_start": start, "span_end": end, "text": text})
        loaded.append(merged)
    return loaded


def _split_existing(
    chunks: list[dict[str, Any]],
    raw_text: str,
    limit: int,
    source_id: str,
    title: str,
    authors: Any,
) -> list[dict[str, Any]]:
    author = _author_string(authors)
    out: list[dict[str, Any]] = []
    for chunk in chunks:
        text = chunk["text"]
        start = int(chunk["span_start"])
        if len(text) <= limit:
            out.append(chunk)
            continue
        parts = _character_spans(text, limit)
        parent_id = str(chunk["chunk_id"])
        for index, (local_start, local_end) in enumerate(parts):
            abs_start = start + local_start
            abs_end = start + local_end
            child = dict(chunk)
            child.update(
                {
                    "chunk_id": f"{parent_id}__p{index:02d}",
                    "span_start": abs_start,
                    "span_end": abs_end,
                    "text": raw_text[abs_start:abs_end],
                    "source_id": source_id,
                    "source_type": "book",
                    "title": title,
                    "author": chunk.get("author") or author,
                    "section": _safe_section(chunk.get("section"), index),
                }
            )
            out.append(child)
    return out


def _chunk_metadata(source_id: str, title: str, authors: Any, text: str, max_chunk_chars: int) -> list[dict[str, Any]]:
    spans = _character_spans(text, max_chunk_chars)
    author = _author_string(authors)
    return [
        {
            "chunk_id": f"{source_id}-chunk-{index:04d}",
            "source_id": source_id,
            "source_type": "book",
            "title": title,
            "author": author,
            "section": _safe_section(_heading_before(text, start), index - 1),
            "chunk_index": index - 1,
            "span_start": start,
            "span_end": end,
            "text": text[start:end],
        }
        for index, (start, end) in enumerate(spans, start=1)
    ]


def _character_spans(text: str, max_chunk_chars: int) -> list[tuple[int, int]]:
    """Split text into contiguous spans that never exceed max_chunk_chars."""

    if not text:
        return []
    if max_chunk_chars < 1:
        raise ArtifactPreparationError("max_chunk_chars must be at least 1")
    boundaries = [0]
    offset = 0
    for line in text.splitlines(keepends=True):
        offset += len(line)
        if not line.strip():
            boundaries.append(offset)
    if boundaries[-1] != len(text):
        boundaries.append(len(text))
    return _pack_boundaries(text, boundaries, max_chunk_chars)


def _pack_boundaries(text: str, boundaries: list[int], max_chunk_chars: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    packed_end = 0
    for boundary in boundaries[1:]:
        if boundary <= start:
            continue
        if boundary - start <= max_chunk_chars:
            packed_end = boundary
            continue
        if packed_end > start:
            spans.extend(_force_split(text, start, packed_end, max_chunk_chars))
            start = packed_end
        spans.extend(_force_split(text, start, boundary, max_chunk_chars))
        start = boundary
        packed_end = boundary
    if start < len(text):
        end = packed_end if packed_end > start else len(text)
        spans.extend(_force_split(text, start, end, max_chunk_chars))
    remain = spans[-1][1] if spans else 0
    if remain < len(text):
        spans.extend(_force_split(text, remain, len(text), max_chunk_chars))
    return [(left, right) for left, right in spans if right > left]


def _force_split(text: str, start: int, end: int, max_chunk_chars: int) -> list[tuple[int, int]]:
    if end <= start:
        return []
    if end - start <= max_chunk_chars:
        return [(start, end)]
    out: list[tuple[int, int]] = []
    cursor = start
    while cursor < end:
        limit = min(cursor + max_chunk_chars, end)
        if limit < end:
            split_at = text.rfind("\n", cursor + max(1, max_chunk_chars // 5), limit)
            if split_at > cursor:
                limit = split_at + 1
        out.append((cursor, limit))
        cursor = limit
    return out


def _reindex(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for index, chunk in enumerate(chunks):
        chunk["chunk_index"] = index
    return chunks


def _heading_before(text: str, offset: int) -> str | None:
    heading = None
    for line in text[:offset].splitlines():
        if line.startswith("#"):
            value = line.lstrip("#").strip()
            if value:
                heading = value
    return heading


def _safe_section(value: Any, index: int) -> str:
    text = str(value or "").strip()
    if not text or _SECTION_RANGE.search(text):
        return f"span-{index}"
    return text


def _author_string(authors: Any) -> str:
    if isinstance(authors, list):
        return ", ".join(str(value) for value in authors)
    return str(authors or "")


def _retrieval_chunks_document(source_id: str, title: str, chunks: list[dict[str, Any]], limit: int) -> str:
    return (
        f"---\nsource_id: {source_id}\ntitle: {title}\ngenerated_by: {GENERATOR}\n"
        f"max_input_chars: {limit}\nchunk_count: {len(chunks)}\n---\n\n"
        f"# Retrieval Chunks: {title}\n\n```json\n{json.dumps(chunks, indent=2)}\n```\n"
    )


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _require_limit(value: int) -> int:
    if value < 1000:
        raise ArtifactPreparationError("max_chunk_chars must be at least 1000")
    return value


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
