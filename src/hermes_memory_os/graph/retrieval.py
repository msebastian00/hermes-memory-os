"""Qdrant-first graph expansion with compact, provenance-rich context packets."""

from __future__ import annotations

import re
from typing import Any

DEFAULT_MIN_CONFIDENCE = 0.75
UNSUPPORTED_STATUSES = frozenset(
    {"unsupported", "contradicted", "rejected", "stale", "superseded", "draft", "unverified-unsupported"}
)


class GraphRetrievalAdapter:
    """Preserve Memory OS progressive loading, adding one graph expansion pass."""

    def __init__(self, memory_app: Any, graph_client: Any):
        self.memory_app = memory_app
        self.graph_client = graph_client

    def retrieve(
        self,
        query: str,
        *,
        profile: str = "minimal",
        max_context_tokens: int = 4000,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        include_low_confidence: bool = False,
    ) -> dict[str, Any]:
        limits = {"minimal": 5, "project": 10, "research": 20, "maintenance": 10}
        limit = limits.get(profile, limits["minimal"])
        semantic_backend = getattr(getattr(self.memory_app, "retriever", None), "semantic_backend", None)
        semantic_hits: list[dict[str, Any]] = []
        warnings: list[str] = []
        if semantic_backend is not None:
            try:
                semantic_hits = semantic_backend.search(query, limit=limit)
            except Exception as exc:
                warnings.append(f"qdrant_unavailable:{exc.__class__.__name__}")

        if not semantic_hits:
            semantic_hits = self.memory_app.retriever.search(query, limit=limit)
            if not any(item.startswith("qdrant_unavailable:") for item in warnings):
                warnings.append("qdrant_no_hits_or_disabled")

        chunk_ids, point_ids = _expansion_ids(self.memory_app, semantic_hits)

        graph_rows: list[dict[str, Any]] = []
        if self.graph_client is not None and (chunk_ids or point_ids):
            try:
                graph_rows = self.graph_client.expand_context(chunk_ids, point_ids)
            except Exception as exc:
                warnings.append(f"graph_unavailable:{exc.__class__.__name__}")

        excluded = 0
        supported_rows: list[dict[str, Any]] = []
        for row in graph_rows:
            if _supported_row(row, min_confidence=min_confidence, include_low_confidence=include_low_confidence):
                supported_rows.append(row)
            else:
                excluded += 1
        if excluded:
            warnings.append(f"excluded_unsupported_or_low_confidence:{excluded}")

        supported_rows.sort(key=lambda row: _claim_relevance(query, row), reverse=True)

        claims = _unique(supported_rows, "claim_id")
        provenance = [
            {
                "claim_id": row.get("claim_id"),
                "claim_text": row.get("claim_text"),
                "claim_basis": row.get("claim_basis") or "author-framework",
                "verification_status": row.get("verification_status") or "unverified",
                "evidence_id": row.get("evidence_id"),
                "quote": row.get("evidence_quote"),
                "chunk_id": row.get("chunk_id"),
                "source_chunk_id": row.get("source_chunk_id"),
                "source_id": row.get("source_id"),
                "qdrant_point_id": row.get("qdrant_point_id"),
                "confidence": row.get("claim_confidence"),
            }
            for row in supported_rows
            if row.get("claim_id") and row.get("evidence_id")
        ]
        return {
            "query": query,
            "profile": profile,
            "context_budget_tokens": max_context_tokens,
            "semantic_hits": semantic_hits[:limit],
            "graph_hits": supported_rows[:limit],
            "claims": claims[:limit],
            "policies": [],
            "open_questions": [],
            "review_warnings": warnings,
            "provenance": provenance[:limit],
            "result_counts": {
                "semantic_hits": len(semantic_hits[:limit]),
                "graph_hits": len(supported_rows[:limit]),
                "claims": len(claims[:limit]),
                "provenance": len(provenance[:limit]),
                "excluded": excluded,
            },
        }


def _expansion_ids(memory_app: Any, semantic_hits: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Expand only from source-chunk IDs or verified Qdrant point IDs."""

    chunk_ids: list[str] = []
    point_ids: list[str] = []
    store = getattr(memory_app, "store", None)
    for hit in semantic_hits:
        kind = hit.get("kind")
        hit_id = str(hit.get("id") or "")
        if kind != "source_chunk" or not hit_id or store is None:
            continue
        chunk = store.get_source_chunk(hit_id)
        if chunk is None:
            continue
        chunk_ids.append(str(chunk["id"]))
        verified_point = chunk.get("qdrant_point_id")
        if verified_point:
            point_ids.append(str(verified_point))
    return chunk_ids, point_ids


def _supported_row(
    row: dict[str, Any],
    *,
    min_confidence: float,
    include_low_confidence: bool,
) -> bool:
    if not row.get("claim_id") or not row.get("evidence_id"):
        return False
    status = str(row.get("claim_status") or "active").strip().lower()
    if status in UNSUPPORTED_STATUSES:
        return False
    confidence = row.get("claim_confidence")
    if confidence is not None and not include_low_confidence:
        try:
            if float(confidence) < min_confidence:
                return False
        except (TypeError, ValueError):
            return False
    return True


def _unique(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result = []
    for row in rows:
        value = str(row.get(key) or "")
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(
            {
                "id": value,
                "text": row.get("claim_text"),
                "confidence": row.get("claim_confidence"),
                "status": row.get("claim_status"),
                "entity": row.get("entity_name"),
                "claim_basis": row.get("claim_basis") or "author-framework",
                "verification_status": row.get("verification_status") or "unverified",
            }
        )
    return result


def _claim_relevance(query: str, row: dict[str, Any]) -> tuple[int, float]:
    """Prefer claims that directly address the original Qdrant query."""

    query_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    claim_terms = set(re.findall(r"[a-z0-9]+", str(row.get("claim_text") or "").lower()))
    confidence = row.get("claim_confidence")
    try:
        numeric_confidence = float(confidence) if confidence is not None else 0.0
    except (TypeError, ValueError):
        numeric_confidence = 0.0
    return len(query_terms & claim_terms), numeric_confidence
