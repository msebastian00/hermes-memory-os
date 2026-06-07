"""Retrieval ranking."""

from __future__ import annotations

from typing import Any


DEFAULT_WEIGHTS = {
    "semantic": 0.45,
    "keyword": 0.20,
    "entity": 0.15,
    "scope": 0.10,
    "recency": 0.05,
    "trust": 0.05,
}


def rank_results(results: list[dict[str, Any]], weights: dict[str, float] | None = None) -> list[dict[str, Any]]:
    weights = weights or DEFAULT_WEIGHTS
    ranked = []
    for item in results:
        score = (
            weights.get("semantic", 0) * float(item.get("semantic_score", 0.0))
            + weights.get("keyword", 0) * float(item.get("keyword_score", 0.0))
            + weights.get("entity", 0) * float(item.get("entity_score", 0.0))
            + weights.get("scope", 0) * float(item.get("scope_score", 0.0))
            + weights.get("recency", 0) * float(item.get("recency_score", 0.0))
            + weights.get("trust", 0) * float(item.get("trust_score", 0.5))
        )
        updated = dict(item)
        updated["final_score"] = round(score, 6)
        ranked.append(updated)
    return sorted(ranked, key=lambda row: row["final_score"], reverse=True)


def filter_confident(results: list[dict[str, Any]], min_score: float, limit: int) -> list[dict[str, Any]]:
    return [item for item in results if item.get("final_score", 0.0) >= min_score][:limit]
