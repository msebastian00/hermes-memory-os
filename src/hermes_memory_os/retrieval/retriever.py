"""Hybrid retrieval over SQLite FTS with optional vector backend hooks."""

from __future__ import annotations

import time
from typing import Any

from hermes_memory_os.db.store import MemoryStore
from hermes_memory_os.retrieval.ranker import filter_confident, rank_results


class Retriever:
    def __init__(self, store: MemoryStore, retrieval_config: dict[str, Any]):
        self.store = store
        self.config = retrieval_config

    def search(self, query: str, *, limit: int | None = None, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        started = time.perf_counter()
        limit = limit or int(self.config.get("max_injected", 8))
        keyword_results = self.store.search_keyword(_fts_query(query), limit=limit * 2)
        for item in keyword_results:
            item.setdefault("semantic_score", item.get("keyword_score", 0.0))
        ranked = rank_results(keyword_results, self.config.get("weights"))
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
