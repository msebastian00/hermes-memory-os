"""Inventory reviewed retrieval chunks that lack a verified Qdrant crosswalk."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from hermes_memory_os.utils import now_iso


def inventory_span_manifest_candidates(vault_root: Path) -> list[dict[str, Any]]:
    """Books with reviewed retrieval chunks and no verified Qdrant point IDs.

    Raw-book manifests without retrieval-chunk metadata are skipped.
    """

    analysis_root = vault_root / "06_GENERATED" / "source-analysis"
    if not analysis_root.is_dir():
        return []
    candidates: list[dict[str, Any]] = []
    for chunks_path in sorted(analysis_root.glob("*/retrieval-chunks.md")):
        source_id = chunks_path.parent.name
        chunks = _parse_retrieval_chunks(chunks_path)
        if not chunks:
            continue
        if not _has_reviewed_source_page(vault_root, source_id):
            continue
        if _has_verified_qdrant_crosswalk(chunks):
            continue
        manifest = _find_manifest(vault_root, source_id)
        candidates.append(
            {
                "source_id": source_id,
                "retrieval_chunks_path": _relative(vault_root, chunks_path),
                "chunk_count": len(chunks),
                "chunks": chunks,
                "manifest_path": _relative(vault_root, manifest) if manifest else None,
                "raw_source_sha256": _manifest_hash(manifest) if manifest else None,
                "raw_source_path": _manifest_source_path(manifest) if manifest else None,
            }
        )
    return candidates


def proposed_span_manifest(candidate: dict[str, Any]) -> dict[str, Any]:
    """Review artifact only. Does not index Qdrant or upsert Neo4j."""

    spans = []
    for chunk in candidate["chunks"]:
        section = str(chunk.get("section") or "")
        start, end = _section_bounds(section)
        spans.append(
            {
                "chunk_id": str(chunk["chunk_id"]),
                "chunk_index": int(chunk["chunk_index"]),
                "section": section,
                "page_start": chunk.get("page_start"),
                "page_end": chunk.get("page_end"),
                "span": {
                    "kind": "logical_section",
                    "start": start,
                    "end": end,
                },
                "character_offsets": None,
                "qdrant_point_id": chunk.get("qdrant_point_id"),
                "review_needed": True,
            }
        )
    return {
        "status": "proposed_review",
        "write_mode": "dry_run",
        "source_id": candidate["source_id"],
        "raw_source_sha256": candidate.get("raw_source_sha256"),
        "raw_source_path": candidate.get("raw_source_path"),
        "retrieval_chunks_path": candidate.get("retrieval_chunks_path"),
        "qdrant_crosswalk": "missing",
        "generated_at": now_iso(),
        "chunks": spans,
        "warnings": [
            "embedding_missing",
            "character_offsets_unverified",
            "review_artifact_only",
        ],
        "indexes_qdrant": False,
        "upserts_neo4j": False,
    }


def write_proposed_span_manifest(payload: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _parse_retrieval_chunks(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"```json\s*(\[.*?\])\s*```", text, flags=re.DOTALL)
    if match is None:
        return []
    parsed = json.loads(match.group(1))
    if not isinstance(parsed, list):
        return []
    required = ("chunk_id", "chunk_index", "section")
    chunks = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        if any(not str(item.get(field, "")).strip() for field in required):
            continue
        chunks.append(item)
    return chunks


def _has_verified_qdrant_crosswalk(chunks: list[dict[str, Any]]) -> bool:
    return any(chunk.get("qdrant_point_id") for chunk in chunks)


def _has_reviewed_source_page(vault_root: Path, source_id: str) -> bool:
    books = vault_root / "02_WIKI" / "sources" / "books"
    if not books.is_dir():
        return False
    for candidate in books.glob("*.md"):
        try:
            frontmatter, _ = _read_frontmatter(candidate)
        except (PermissionError, OSError, yaml.YAMLError):
            continue
        if frontmatter.get("source_id") == source_id:
            return True
    return False


def _find_manifest(vault_root: Path, source_id: str) -> Path | None:
    raw_root = vault_root / "03_RESOURCES" / "books" / "raw"
    if not raw_root.is_dir():
        return None
    for candidate in raw_root.glob("**/manifest.md"):
        try:
            frontmatter, _ = _read_frontmatter(candidate)
        except (PermissionError, OSError, yaml.YAMLError):
            continue
        if frontmatter.get("source_id") == source_id:
            return candidate
    return None


def _read_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    _, raw, body = text.split("---", 2)
    try:
        loaded = yaml.safe_load(raw) or {}
        return loaded if isinstance(loaded, dict) else {}, body
    except yaml.YAMLError:
        values: dict[str, Any] = {}
        for line in raw.splitlines():
            if not line or line.startswith((" ", "-")) or ":" not in line:
                continue
            key, value = line.split(":", 1)
            if key.strip():
                values[key.strip()] = value.strip()
        return values, body


def _manifest_hash(path: Path) -> str | None:
    frontmatter, _ = _read_frontmatter(path)
    value = frontmatter.get("content_hash")
    return str(value) if value else None


def _manifest_source_path(path: Path) -> str | None:
    frontmatter, _ = _read_frontmatter(path)
    value = frontmatter.get("source_path")
    return str(value) if value else None


def _section_bounds(section: str) -> tuple[str, str]:
    parts = [part.strip() for part in section.replace("–", "-").split("-") if part.strip()]
    if len(parts) >= 2:
        return f"section:{parts[0]}", f"section:{parts[1]}"
    if parts:
        return f"section:{parts[0]}", f"section:{parts[0]}"
    return "section:unknown", "section:unknown"


def _relative(root: Path, path: Path) -> str:
    return str(path.relative_to(root))
