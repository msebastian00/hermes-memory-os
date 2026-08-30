"""Verified bridge from reviewed book chunks to existing Memory OS/Qdrant indexing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .builder import BookArtifacts, discover_book
from .config import GraphConfig
from .source_integrity import validate_book_artifacts
from .artifact_prep import embedding_input_limit, prepare_book_artifacts


class CrosswalkError(ValueError):
    """Raised when a chunk-body manifest cannot prove its raw-source provenance."""


def build_crosswalk_plan(
    config: GraphConfig, source_id: str, chunk_bodies_path: Path
) -> dict[str, Any]:
    """Validate supplied chunk bodies against exact spans in the immutable raw source."""
    book = discover_book(config.vault_root, source_id)
    integrity = validate_book_artifacts(book)
    if not integrity["safe_for_qdrant_crosswalk"]:
        raise CrosswalkError(
            "Qdrant crosswalk blocked by source-integrity validation: "
            + ", ".join(integrity["problems"])
        )
    raw_text = book.raw_path.read_text(encoding="utf-8")
    raw_hash = _digest(raw_text)
    payload = _read_manifest(chunk_bodies_path)
    if payload.get("source_id") != source_id:
        raise CrosswalkError("chunk-body manifest source_id does not match the requested book")
    if payload.get("raw_content_hash") != raw_hash:
        raise CrosswalkError("chunk-body manifest raw_content_hash does not match the immutable raw source")

    supplied = payload.get("chunks")
    if not isinstance(supplied, list):
        raise CrosswalkError("chunk-body manifest chunks must be a list")
    expected = {str(chunk["chunk_id"]): chunk for chunk in book.chunks}
    bodies: dict[str, dict[str, Any]] = {}
    for item in supplied:
        if not isinstance(item, dict):
            raise CrosswalkError("each chunk-body manifest entry must be an object")
        chunk_id = str(item.get("chunk_id") or "")
        text = item.get("text")
        start, end = item.get("span_start"), item.get("span_end")
        if chunk_id not in expected or not isinstance(text, str) or not isinstance(start, int) or not isinstance(end, int):
            raise CrosswalkError("each chunk requires known chunk_id, text, span_start, and span_end")
        if start < 0 or end <= start or raw_text[start:end] != text:
            raise CrosswalkError(f"chunk {chunk_id} does not exactly match its declared raw-source span")
        if chunk_id in bodies:
            raise CrosswalkError(f"duplicate chunk-body entry: {chunk_id}")
        bodies[chunk_id] = {"text": text, "span_start": start, "span_end": end}
    if set(bodies) != set(expected):
        raise CrosswalkError("chunk-body manifest must cover every existing retrieval chunk exactly once")

    chunks = []
    for metadata in book.chunks:
        external_id = str(metadata["chunk_id"])
        body = bodies[external_id]
        chunks.append(
            {
                "external_id": external_id,
                "text": body["text"],
                "span_start": body["span_start"],
                "span_end": body["span_end"],
                "metadata": metadata,
            }
        )
    return {"book": book, "raw_hash": raw_hash, "chunks": chunks}


def index_book_crosswalk(
    memory_app: Any,
    config: GraphConfig,
    source_id: str,
    chunk_bodies_path: Path,
    *,
    write_mode: str = "dry_run",
) -> dict[str, Any]:
    """Plan or index exactly one book's verified chunks through Memory OS.

    `dry_run` has no SQLite or Qdrant effects. `upsert` touches only the explicit
    chunks registered under a graph-crosswalk source and never drains the general
    pending-index queue.
    """
    if write_mode not in {"dry_run", "upsert"}:
        raise CrosswalkError("write_mode must be dry_run or upsert")
    limit = embedding_input_limit(memory_app)
    if write_mode == "upsert":
        prepared = prepare_book_artifacts(
            config,
            source_id,
            write_mode="upsert",
            max_chunk_chars=limit,
            memory_app=memory_app,
        )
        chunk_bodies_path = Path(prepared["chunk_bodies_path"])
    plan = build_crosswalk_plan(config, source_id, chunk_bodies_path)
    raw_text = plan["book"].raw_path.read_text(encoding="utf-8")
    for item in plan["chunks"]:
        if item["text"] != raw_text[item["span_start"] : item["span_end"]]:
            raise CrosswalkError(f"chunk {item['external_id']} vector text is not the declared evidence span")
        if len(item["text"]) > limit:
            raise CrosswalkError(
                f"chunk {item['external_id']} exceeds embedding input limit {limit}; prepare artifacts first"
            )
    book: BookArtifacts = plan["book"]
    result = {
        "source_id": source_id,
        "write_mode": write_mode,
        "raw_content_hash": plan["raw_hash"],
        "chunks": [
            {"source_chunk_id": item["external_id"], "span_start": item["span_start"], "span_end": item["span_end"]}
            for item in plan["chunks"]
        ],
        "qdrant_point_ids": {},
        "warnings": [],
    }
    if write_mode == "dry_run":
        result["status"] = "planned"
        return result

    indexer = getattr(memory_app, "semantic_indexer", None)
    if indexer is None:
        raise CrosswalkError("Memory OS semantic indexing must be enabled for crosswalk upsert")
    source_path = f"graph-crosswalk://{source_id}/{plan['raw_hash']}/{_chunkset_digest(plan['chunks'])}"
    chunks = [_memory_chunk(item, book, plan["raw_hash"]) for item in plan["chunks"]]
    memory_source_id, created = memory_app.store.upsert_source_file(
        source_path=source_path,
        source_type="book",
        title=book.title,
        content=book.raw_path.read_text(encoding="utf-8"),
        chunks=chunks,
        source_metadata={
            "graph_source_id": source_id,
            "raw_source_path": book.raw_relative_path,
            "raw_content_hash": plan["raw_hash"],
            "adapter": "hermes-graph-crosswalk-v1",
        },
        chunking_version="graph-crosswalk-v1",
    )
    persisted = memory_app.store.list_source_chunks(memory_source_id)
    by_external = {
        str(chunk.get("metadata", {}).get("graph_source_chunk_id")): chunk for chunk in persisted
    }
    if set(by_external) != {item["external_id"] for item in plan["chunks"]}:
        raise CrosswalkError("Memory OS crosswalk source does not contain the expected verified chunks")
    indexing = indexer.index_source_chunks(list(by_external.values()))
    refreshed = {key: memory_app.store.get_source_chunk(value["id"]) for key, value in by_external.items()}
    point_ids = {key: value.get("qdrant_point_id") for key, value in refreshed.items() if value}
    complete = (not indexing["semantic_failed"]) and point_ids and all(point_ids.values())
    superseded_ids: list[str] = []
    if complete:
        prefix = f"graph-crosswalk://{source_id}/"
        for prior in memory_app.store.list_sources_by_path_prefix(prefix, status="active"):
            if prior["id"] != memory_source_id:
                if memory_app.store.supersede_source(
                    prior["id"],
                    replaced_by=memory_source_id,
                    reason="replaced by complete graph-crosswalk",
                ):
                    superseded_ids.append(prior["id"])
    result.update(
        {
            "status": "indexed" if complete else "partially_indexed",
            "memory_os_source_id": memory_source_id,
            "memory_os_source_created": created,
            "indexing": indexing,
            "qdrant_point_ids": point_ids,
            "superseded_source_ids": superseded_ids,
        }
    )
    result["warnings"] = [
        f"embedding_missing:{key}" for key, value in result["qdrant_point_ids"].items() if value is None
    ]
    return result


def write_crosswalk(result: dict[str, Any], output_path: Path) -> Path:
    points = result.get("qdrant_point_ids") or {}
    if not points or any(point is None for point in points.values()):
        raise CrosswalkError("refusing to write an incomplete Qdrant crosswalk")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(points, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _memory_chunk(item: dict[str, Any], book: BookArtifacts, raw_hash: str) -> dict[str, Any]:
    metadata = item["metadata"]
    return {
        "text": item["text"],
        "heading": f"Sections {metadata['section']}",
        "chapter": metadata.get("chapter"),
        "section": metadata.get("section"),
        "page_start": metadata.get("page_start"),
        "page_end": metadata.get("page_end"),
        "metadata": {
            "graph_source_chunk_id": item["external_id"],
            "raw_span": [item["span_start"], item["span_end"]],
            "raw_content_hash": raw_hash,
            "raw_source_path": book.raw_relative_path,
        },
        "chunking_version": "graph-crosswalk-v1",
    }


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CrosswalkError(f"cannot read chunk-body manifest: {path}") from exc
    if not isinstance(raw, dict):
        raise CrosswalkError("chunk-body manifest root must be an object")
    return raw


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _chunkset_digest(chunks: list[dict[str, Any]]) -> str:
    joined = "|".join(f"{item['external_id']}:{item['span_start']}:{item['span_end']}" for item in chunks)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]
