"""Deterministic structural checks before a book can receive graph/Qdrant source spans."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from hermes_memory_os.utils import now_iso

from .config import GraphConfig

_SECTION_MARKER = re.compile(r"^\s*(?:#{1,6}\s*)?(\d{1,4})\s*$")
_SECTION_RANGE = re.compile(r"(\d+)\s*[-–]\s*(\d+)")


def validate_book_source(config: GraphConfig, source_id: str) -> dict[str, Any]:
    """Verify raw-source hash and recoverable section markers without writing data."""
    # Import locally so the graph builder can use the artifact-level validator.
    from .builder import discover_book

    book = discover_book(config.vault_root, source_id)
    return validate_book_artifacts(book)


def validate_book_artifacts(book: Any) -> dict[str, Any]:
    """Validate discovered book artifacts without writing to a source system."""
    text = book.raw_path.read_text(encoding="utf-8")
    actual_hash = _digest(text)
    expected = _expected_sections(book.chunks)
    markers = _section_markers(text)
    observed = sorted(set(markers))
    missing = sorted(expected - set(observed))
    first_expected = min(expected) if expected else None
    first_observed = observed[0] if observed else None
    problems = []
    if actual_hash != book.checksum:
        problems.append("raw_source_hash_mismatch")
    if missing:
        problems.append("section_markers_incomplete")
    if first_expected is not None and first_observed is not None and first_observed > first_expected:
        problems.append("source_begins_after_expected_first_section")
    status = "ready_for_span_review" if not problems else "blocked"
    return {
        "source_id": book.source_id,
        "status": status,
        "write_mode": "dry_run",
        "raw_source_path": book.raw_relative_path,
        "raw_source_sha256": actual_hash,
        "manifest_sha256": book.checksum,
        "expected_section_count": len(expected),
        "expected_section_min": first_expected,
        "expected_section_max": max(expected) if expected else None,
        "observed_marker_count": len(observed),
        "observed_marker_min": first_observed,
        "observed_marker_max": max(observed) if observed else None,
        "missing_sections": missing,
        "problems": problems,
        "generated_at": now_iso(),
        "safe_for_qdrant_crosswalk": status == "ready_for_span_review",
        "safe_for_neo4j_book_upsert": status == "ready_for_span_review",
    }


def write_source_integrity_report(result: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _expected_sections(chunks: tuple[dict[str, Any], ...]) -> set[int]:
    values: set[int] = set()
    for chunk in chunks:
        match = _SECTION_RANGE.search(str(chunk.get("section") or ""))
        if match is None:
            continue
        start, end = (int(match.group(1)), int(match.group(2)))
        values.update(range(min(start, end), max(start, end) + 1))
    return values


def _section_markers(text: str) -> list[int]:
    values = []
    for line in text.splitlines():
        match = _SECTION_MARKER.match(line)
        if match:
            values.append(int(match.group(1)))
    return values


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
