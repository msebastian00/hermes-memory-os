"""Hybrid retrieval over SQLite FTS with optional vector backend hooks."""

from __future__ import annotations

import time
from typing import Any, Protocol

from hermes_memory_os.db.store import MemoryStore
from hermes_memory_os.retrieval.ranker import filter_confident, rank_results


class SemanticBackend(Protocol):
    def search(
        self,
        query: str,
        *,
        limit: int,
        source_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return semantic retrieval candidates."""


class Retriever:
    def __init__(
        self,
        store: MemoryStore,
        retrieval_config: dict[str, Any],
        semantic_backend: SemanticBackend | None = None,
    ):
        self.store = store
        self.config = retrieval_config
        self.semantic_backend = semantic_backend

    def search(
        self,
        query: str,
        *,
        limit: int | None = None,
        context: dict[str, Any] | None = None,
        source_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        started = time.perf_counter()
        limit = limit or int(self.config.get("max_injected", 8))
        context = dict(context or {})
        keyword_results = self.store.search_keyword(
            _fts_query(query),
            limit=limit * 2,
            source_types=source_types,
        )
        semantic_results: list[dict[str, Any]] = []
        if self.semantic_backend is not None:
            try:
                semantic_results = self.semantic_backend.search(
                    query,
                    limit=limit * 2,
                    source_types=source_types,
                )
                context["semantic_result_count"] = len(semantic_results)
            except Exception as exc:
                context["semantic_fallback"] = True
                context["semantic_error"] = exc.__class__.__name__

        if not semantic_results:
            for item in keyword_results:
                item.setdefault("semantic_score", item.get("keyword_score", 0.0))

        ranked = rank_results(
            _merge_results(keyword_results, semantic_results),
            self.config.get("weights"),
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        confident = filter_confident(
            ranked,
            min_score=float(self.config.get("min_final_score", 0.35)),
            limit=limit,
        )
        self.store.log_retrieval(
            query,
            confident,
            latency_ms,
            context=context,
            suppressed=not bool(confident),
        )
        return confident


def _fts_query(query: str) -> str:
    terms = [term.strip().replace('"', "") for term in query.split() if term.strip()]
    if not terms:
        return '""'
    return " OR ".join(f'"{term}"' for term in terms)


def _merge_results(
    keyword_results: list[dict[str, Any]],
    semantic_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in keyword_results:
        key = _canonical_key(item)
        updated = dict(item)
        updated.setdefault("keyword_score", 0.0)
        updated.setdefault("semantic_score", 0.0)
        merged[key] = updated

    for item in semantic_results:
        key = _canonical_key(item)
        if key not in merged:
            updated = dict(item)
            updated.setdefault("keyword_score", 0.0)
            updated.setdefault("semantic_score", 0.0)
            merged[key] = updated
            continue

        existing = merged[key]
        existing["semantic_score"] = max(
            float(existing.get("semantic_score", 0.0)),
            float(item.get("semantic_score", 0.0)),
        )
        if "qdrant_score" in item:
            existing["qdrant_score"] = item["qdrant_score"]
        existing["retrieval_sources"] = sorted(
            set(existing.get("retrieval_sources", ["keyword"])) | {"semantic"}
        )

    for item in merged.values():
        if "retrieval_sources" not in item:
            sources = []
            if item.get("keyword_score", 0.0):
                sources.append("keyword")
            if item.get("semantic_score", 0.0):
                sources.append("semantic")
            item["retrieval_sources"] = sources
    return list(merged.values())


def _canonical_key(item: dict[str, Any]) -> str:
    return f"{item.get('kind')}:{item.get('id')}"
