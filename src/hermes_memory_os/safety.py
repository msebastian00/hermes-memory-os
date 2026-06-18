"""Safety helpers for the HTTP adapter boundary."""

from __future__ import annotations

import re
from typing import Any

FORBIDDEN_PAYLOAD_FIELDS = {
    "audio",
    "audio_b64",
    "audio_wav_base64",
    "audio_encoding",
    "embedding",
    "embedding_json",
    "vector",
    "raw_fingerprint",
    "voiceprint",
    "speaker_embedding",
    "anonymous_speaker_cluster",
    "anonymous_speaker_clusters",
    "db_path",
    "database_path",
    "local_db_path",
    "api_key",
    "authorization",
    "token",
    "secret",
}
SUPPRESSED_STATUSES = {"low_confidence", "stale", "archived", "pending", "pending_review", "rejected"}


def forbidden_field_path(value: Any, *, path: str = "") -> str:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).strip().lower()
            current = f"{path}.{key}" if path else str(key)
            if normalized in FORBIDDEN_PAYLOAD_FIELDS:
                return current
            nested = forbidden_field_path(item, path=current)
            if nested:
                return nested
    elif isinstance(value, list):
        for index, item in enumerate(value):
            nested = forbidden_field_path(item, path=f"{path}[{index}]")
            if nested:
                return nested
    return ""


def safe_payload(value: Any, *, max_text_chars: int = 500) -> Any:
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            normalized = str(key).strip().lower()
            if normalized in FORBIDDEN_PAYLOAD_FIELDS:
                continue
            cleaned[str(key)[:80]] = safe_payload(item, max_text_chars=max_text_chars)
        return cleaned
    if isinstance(value, list):
        return [safe_payload(item, max_text_chars=max_text_chars) for item in value[:20]]
    if isinstance(value, str):
        return _clip(value, max_text_chars)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _clip(str(value), max_text_chars)


def normalize_result(raw: dict[str, Any], *, max_summary_chars: int = 700) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    status = str(raw.get("status") or "usable").strip().lower()
    if status in SUPPRESSED_STATUSES:
        return None
    kind = str(raw.get("kind") or "durable_memory").strip().lower()
    if kind == "memory":
        kind = "durable_memory"
    if kind not in {"durable_memory", "source_chunk"}:
        kind = "durable_memory"
    item_id = _safe_identifier(str(raw.get("id") or raw.get("memory_id") or raw.get("chunk_id") or ""))
    if not item_id:
        return None
    summary = str(raw.get("summary") or raw.get("excerpt") or raw.get("text") or raw.get("content") or "").strip()
    source_type = str(raw.get("source_type") or ("memory" if kind == "durable_memory" else "unknown")).strip().lower()
    location = _safe_location(raw, kind=kind, item_id=item_id)
    return {
        "id": item_id,
        "kind": kind,
        "title": _clip(str(raw.get("title") or raw.get("source_title") or ""), 180),
        "summary": _clip(summary, max_summary_chars),
        "source_type": source_type or "unknown",
        "citation": _clip(str(raw.get("citation") or _format_source(raw.get("source"))), 220),
        "score": _score(raw),
        "location": location,
        "status": "usable",
    }


def _safe_location(raw: dict[str, Any], *, kind: str, item_id: str) -> dict[str, Any]:
    if kind == "durable_memory":
        return {"memory_id": item_id}
    location = {}
    source_id = _safe_identifier(str(raw.get("source_id") or ""))
    if source_id:
        location["source_id"] = source_id
    location["chunk_id"] = _safe_identifier(str(raw.get("chunk_id") or item_id))
    for key in ("chapter", "section", "page_start", "page_end", "timestamp_start", "timestamp_end", "speaker"):
        value = raw.get(key)
        if value not in (None, ""):
            location[key] = safe_payload(value, max_text_chars=120)
    return location


def _score(raw: dict[str, Any]) -> float:
    for key in ("final_score", "score", "semantic_score", "keyword_score", "trust_score"):
        try:
            return round(max(0.0, min(1.0, float(raw.get(key)))), 4)
        except (TypeError, ValueError):
            continue
    return 0.0


def _safe_identifier(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]", "", value)[:160]


def _format_source(value: Any) -> str:
    if not value:
        return "local memory"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value[:3]) if value else "local memory"
    text = str(value)
    if text.strip() in {"", "[]"}:
        return "local memory"
    if "/" in text or "\\" in text:
        return "local source"
    return text


def _clip(value: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 1)].rstrip() + "…"
