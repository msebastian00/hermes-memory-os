"""Reachy-facing HTTP adapter for Hermes Memory OS."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
import uvicorn

from hermes_memory_os.app import MemoryApp
from hermes_memory_os.config import ConfigError
from hermes_memory_os.http_models import (
    AdapterSettings,
    expand_source_types,
    parse_adjacent_request,
    parse_candidate_request,
    parse_search_request,
)
from hermes_memory_os.safety import forbidden_field_path, normalize_result, safe_payload


def settings_from_env(environ: dict[str, str] | None = None) -> AdapterSettings:
    env = environ or os.environ
    return AdapterSettings(
        host=str(env.get("HERMES_MEMORY_HTTP_HOST") or "127.0.0.1").strip(),
        port=_env_int(env.get("HERMES_MEMORY_HTTP_PORT"), 8765, minimum=1, maximum=65535),
        api_key=str(env.get("HERMES_MEMORY_HTTP_API_KEY") or "").strip(),
        config_path=str(env.get("HERMES_MEMORY_CONFIG") or "").strip(),
        data_dir=str(env.get("HERMES_MEMORY_HOME") or "").strip(),
        max_query_chars=_env_int(env.get("HERMES_MEMORY_HTTP_MAX_QUERY_CHARS"), 1200, minimum=100, maximum=8000),
        max_results=_env_int(env.get("HERMES_MEMORY_HTTP_MAX_RESULTS"), 20, minimum=1, maximum=100),
        max_summary_chars=_env_int(env.get("HERMES_MEMORY_HTTP_MAX_SUMMARY_CHARS"), 700, minimum=120, maximum=4000),
    )


def create_app(settings: AdapterSettings | None = None) -> FastAPI:
    settings = settings or settings_from_env()
    api = FastAPI(title="Hermes Memory OS HTTP Adapter")
    api.state.settings = settings
    api.state.memory_app = None
    api.state.startup_error = ""

    try:
        app = MemoryApp.from_config(
            config_path=settings.config_path or None,
            data_dir=settings.data_dir or None,
        )
        app.init_storage()
        api.state.memory_app = app
    except Exception as exc:
        api.state.startup_error = str(exc)

    @api.exception_handler(ValueError)
    async def _value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    @api.get("/health")
    def health() -> dict[str, Any]:
        app = _memory_app_or_none(api)
        status = {
            "ok": app is not None,
            "storage_ready": app is not None,
            "retrieval_ready": app is not None,
            "semantic_ready": False,
            "candidate_ready": app is not None,
            "auth_required": settings.auth_required,
            "degraded": False,
            "degraded_reasons": [],
            "version": _version(),
        }
        if app is None:
            status["degraded"] = True
            status["degraded_reasons"] = [_safe_reason(api.state.startup_error or "memory_app_unavailable")]
            return status
        status["semantic_ready"] = bool(app.semantic_enabled)
        if not app.semantic_enabled:
            status["degraded"] = True
            status["degraded_reasons"] = ["semantic_disabled"]
        return status

    @api.post("/v1/search")
    def search(
        request_body: dict[str, Any],
        _authorized: None = Depends(_auth_dependency(api)),
    ) -> dict[str, Any]:
        _reject_forbidden(_without_context(request_body))
        app = _require_memory_app(api)
        request = parse_search_request(
            request_body,
            max_query_chars=settings.max_query_chars,
            max_results=settings.max_results,
        )
        started = time.perf_counter()
        context = safe_payload(request.context, max_text_chars=500)
        expanded_source_types = expand_source_types(request.source_types)
        results = app.retriever.search(
            request.query,
            limit=request.limit,
            context=context if isinstance(context, dict) else {},
            source_types=expanded_source_types or None,
        )
        normalized = [
            item
            for item in (
                normalize_result(result, max_summary_chars=settings.max_summary_chars)
                for result in results
            )
            if item is not None
        ]
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "results": normalized,
            "latency_ms": latency_ms,
            "semantic_fallback": bool(isinstance(context, dict) and context.get("semantic_fallback")),
            "degraded_reasons": [],
        }

    @api.post("/v1/sources/chunks")
    def adjacent_chunks(
        request_body: dict[str, Any],
        _authorized: None = Depends(_auth_dependency(api)),
    ) -> dict[str, Any]:
        _reject_forbidden(_without_context(request_body))
        app = _require_memory_app(api)
        request = parse_adjacent_request(request_body, max_results=settings.max_results)
        started = time.perf_counter()
        results = app.store.get_adjacent_source_chunks(
            source_id=request.source_id,
            chunk_id=request.chunk_id,
            direction=request.direction,
            limit=request.limit,
        )
        normalized = [
            item
            for item in (
                normalize_result(result, max_summary_chars=settings.max_summary_chars)
                for result in results
            )
            if item is not None
        ]
        reasons = [] if normalized else ["adjacent_chunks_unavailable"]
        return {
            "results": normalized,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "semantic_fallback": False,
            "degraded_reasons": reasons,
        }

    @api.post("/v1/candidates")
    def candidates(
        request_body: dict[str, Any],
        _authorized: None = Depends(_auth_dependency(api)),
    ) -> dict[str, Any]:
        forbidden = forbidden_field_path(request_body)
        if forbidden:
            return {
                "accepted": False,
                "candidate_id": str(request_body.get("candidate_id") or ""),
                "memory_id": "",
                "status": "rejected",
                "reason": "forbidden_field",
            }
        app = _require_memory_app(api)
        request = parse_candidate_request(request_body)
        source_text = request.source_text or request.content
        event_id = app.store.add_raw_event(
            source_text,
            source=request.source,
            role="user",
            client="reachy",
            conversation_id=request.session_id or None,
            source_ref=request.turn_id or request.candidate_id or None,
            metadata={
                "client": "reachy",
                "session_id": request.session_id,
                "source": request.source,
                "tags": ["reachy_candidate"],
            },
        )
        candidate_id = app.store.create_extraction_candidate(
            source_event_ids=[event_id],
            memory_type=request.kind or "semantic",
            scope="user",
            title=_candidate_title(request.content),
            summary=request.content,
            canonical_text=request.content,
            entities=_speaker_entities(request.speaker),
            tags=[request.source],
            confidence=request.confidence,
            reason_to_save=f"Reachy candidate {request.candidate_id}".strip(),
        )
        return {
            "accepted": True,
            "candidate_id": candidate_id,
            "memory_id": "",
            "status": "pending_review",
            "reason": "",
        }

    return api


def main() -> None:
    settings = settings_from_env()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


def _auth_dependency(api: FastAPI):
    def _require_auth(authorization: str = Header(default="")) -> None:
        settings: AdapterSettings = api.state.settings
        if not settings.api_key:
            return
        expected = f"Bearer {settings.api_key}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="invalid_api_key")

    return _require_auth


def _memory_app_or_none(api: FastAPI) -> MemoryApp | None:
    return api.state.memory_app


def _require_memory_app(api: FastAPI) -> MemoryApp:
    app = _memory_app_or_none(api)
    if app is None:
        raise HTTPException(status_code=503, detail=_safe_reason(api.state.startup_error or "memory_app_unavailable"))
    return app


def _reject_forbidden(payload: dict[str, Any]) -> None:
    forbidden = forbidden_field_path(payload)
    if forbidden:
        raise HTTPException(status_code=400, detail=f"forbidden_field:{forbidden}")


def _without_context(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "context"}


def _candidate_title(content: str) -> str:
    words = content.strip().split()
    return " ".join(words[:10])[:120] if words else "Reachy candidate"


def _speaker_entities(speaker: dict[str, Any]) -> list[str]:
    display_name = str(speaker.get("display_name") or "").strip()
    trusted = speaker.get("trusted") is True
    return [display_name] if trusted and display_name else []


def _safe_reason(value: str) -> str:
    if isinstance(value, ConfigError):
        value = str(value)
    text = str(value or "unknown").replace("\\", "/")
    if "/" in text or "HERMES_MEMORY_HOME" in text or "--data-dir" in text:
        return "configuration_error"
    return text[:160]


def _version() -> str:
    try:
        from importlib.metadata import version

        return version("hermes-memory-os")
    except Exception:
        return "0.1.0"


def _env_int(value: str | None, default: int, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value) if value not in (None, "") else default
    except ValueError:
        parsed = default
    return max(minimum, min(maximum, parsed))


app = create_app()


if __name__ == "__main__":
    main()
