"""HTTP adapter request/response models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SOURCE_TYPE_ALIASES = {
    "memory": ["memory"],
    "book": ["book"],
    "lecture": ["lecture"],
    "transcript": ["transcript"],
    "subtitle": ["subtitle"],
    "article": ["article"],
    "note": ["note", "wiki", "markdown"],
    "unknown": ["unknown"],
}
VALID_MODES = {"recall", "source_lookup", "adjacent_chunks", "synthesis_seed"}


@dataclass(frozen=True)
class AdapterSettings:
    host: str = "127.0.0.1"
    port: int = 8765
    api_key: str = ""
    config_path: str = ""
    data_dir: str = ""
    max_query_chars: int = 1200
    max_results: int = 20
    max_summary_chars: int = 700

    @property
    def auth_required(self) -> bool:
        return bool(self.api_key)


@dataclass(frozen=True)
class SearchRequest:
    query: str
    source_types: list[str] = field(default_factory=list)
    limit: int = 5
    mode: str = "recall"
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdjacentChunkRequest:
    source_id: str
    chunk_id: str
    direction: str = "after"
    limit: int = 3
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CandidateRequest:
    candidate_id: str
    kind: str
    content: str
    source_text: str = ""
    confidence: float = 0.5
    session_id: str = ""
    turn_id: str = ""
    speaker: dict[str, Any] = field(default_factory=dict)
    source: str = "reachy"


def parse_search_request(data: Any, *, max_query_chars: int, max_results: int) -> SearchRequest:
    if not isinstance(data, dict):
        raise ValueError("request_body_must_be_object")
    query = _required_text(data, "query", max_chars=max_query_chars)
    source_types = _source_types(data.get("source_types"))
    limit = _bounded_int(data.get("limit"), default=5, minimum=1, maximum=max_results)
    mode = str(data.get("mode") or "recall").strip()
    if mode not in VALID_MODES:
        raise ValueError("invalid_mode")
    context = data.get("context") if isinstance(data.get("context"), dict) else {}
    return SearchRequest(query=query, source_types=source_types, limit=limit, mode=mode, context=context)


def parse_adjacent_request(data: Any, *, max_results: int) -> AdjacentChunkRequest:
    if not isinstance(data, dict):
        raise ValueError("request_body_must_be_object")
    source_id = _required_text(data, "source_id", max_chars=120)
    chunk_id = _required_text(data, "chunk_id", max_chars=120)
    direction = str(data.get("direction") or "after").strip().lower()
    if direction not in {"before", "after", "around"}:
        raise ValueError("invalid_direction")
    limit = _bounded_int(data.get("limit"), default=3, minimum=1, maximum=max_results)
    context = data.get("context") if isinstance(data.get("context"), dict) else {}
    return AdjacentChunkRequest(source_id=source_id, chunk_id=chunk_id, direction=direction, limit=limit, context=context)


def parse_candidate_request(data: Any, *, max_content_chars: int = 2000) -> CandidateRequest:
    if not isinstance(data, dict):
        raise ValueError("request_body_must_be_object")
    content = _required_text(data, "content", max_chars=max_content_chars)
    candidate_id = str(data.get("candidate_id") or "").strip()[:120]
    kind = str(data.get("kind") or "semantic").strip()[:80] or "semantic"
    confidence = _bounded_float(data.get("confidence"), default=0.5, minimum=0.0, maximum=1.0)
    speaker = data.get("speaker") if isinstance(data.get("speaker"), dict) else {}
    return CandidateRequest(
        candidate_id=candidate_id,
        kind=kind,
        content=content,
        source_text=str(data.get("source_text") or "")[:max_content_chars],
        confidence=confidence,
        session_id=str(data.get("session_id") or "").strip()[:120],
        turn_id=str(data.get("turn_id") or "").strip()[:120],
        speaker=speaker,
        source=str(data.get("source") or "reachy").strip()[:80] or "reachy",
    )


def expand_source_types(source_types: list[str]) -> list[str]:
    expanded: list[str] = []
    for item in source_types:
        for value in SOURCE_TYPE_ALIASES.get(item, [item]):
            if value not in expanded:
                expanded.append(value)
    return expanded


def _source_types(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("source_types_must_be_list")
    normalized = []
    for item in value:
        text = str(item or "").strip().lower()
        if not text:
            continue
        if text not in SOURCE_TYPE_ALIASES:
            raise ValueError(f"unsupported_source_type:{text}")
        if text not in normalized:
            normalized.append(text)
    return normalized


def _required_text(data: dict[str, Any], key: str, *, max_chars: int) -> str:
    value = str(data.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key}_required")
    if len(value) > max_chars:
        raise ValueError(f"{key}_too_large")
    return value


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _bounded_float(value: Any, *, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))
