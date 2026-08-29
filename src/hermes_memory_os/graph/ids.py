"""Stable identifiers for graph objects."""

from __future__ import annotations

import hashlib
import re
from typing import Any


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    value = ":".join(str(part) for part in parts)
    return f"{prefix}:{digest(value)}"


def document_id(source: str, title_or_path: str) -> str:
    return stable_id("document", source, title_or_path)


def chunk_id(document: str, index: int, text_hash: str) -> str:
    return f"chunk:{digest(document)}:{index}:{text_hash}"


def entity_id(entity_type: str, canonical_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", canonical_name.lower()).strip("-")
    return f"entity:{entity_type}:{slug or digest(canonical_name)[:16]}"


def claim_id(normalized_text: str, scope: str) -> str:
    return stable_id("claim", normalized_text, scope)


def evidence_id(chunk: str, span_start: int, span_end: int, quote: str) -> str:
    return stable_id("evidence", chunk, span_start, span_end, quote)


def relationship_id(rel_type: str, from_id: str, to_id: str, evidence: str) -> str:
    return stable_id("relationship", rel_type, from_id, to_id, evidence)
