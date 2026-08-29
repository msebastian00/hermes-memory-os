"""Constrained Hermes graph tools. Qdrant/Memory OS first; Neo4j is optional."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable

from .builder import GraphBookBuilder
from .config import GraphConfig, GraphConfigError
from .flags import GRAPH_CONFIG_ENV, graph_enabled, truthy
from .maintenance import collect_maintenance, write_maintenance_report
from .neo4j import Neo4jClient
from .retrieval import DEFAULT_MIN_CONFIDENCE, GraphRetrievalAdapter

logger = logging.getLogger("hermes_memory_os.graph.tools")

ALLOWED_BOOK_SOURCE_ID = "book-finite-infinite-games-undated"
POLICY_INGEST_STATUS = "not_activated"
REVIEW_STATUS = "not_activated"

_PACKAGE_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG = _PACKAGE_ROOT / "config" / "hermes-graph.example.yml"


def openai_graph_tool_schemas() -> list[dict[str, Any]]:
    """OpenAI function-calling schemas for the Hermes plugin boundary."""

    return [
        {
            "name": "graph_retrieve",
            "description": (
                "Read-only graph-aware retrieval. Always queries Memory OS/Qdrant first, "
                "then expands Neo4j only from returned source-chunk IDs or verified "
                "Qdrant point IDs when HERMES_GRAPH_ENABLED=true. Falls back to Memory OS "
                "if the graph is disabled or Neo4j is unavailable. Source claims stay "
                "attributed to their author and are not verified universal facts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Retrieval query"},
                    "profile": {
                        "type": "string",
                        "enum": ["minimal", "project", "research", "maintenance"],
                        "description": "Expansion profile (default minimal)",
                    },
                    "max_context_tokens": {
                        "type": "integer",
                        "description": "Context budget (default 4000)",
                        "default": 4000,
                    },
                    "include_low_confidence": {
                        "type": "boolean",
                        "description": "Include low-confidence graph facts (default false)",
                        "default": False,
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "graph_build_book",
            "description": (
                "Build an explicitly configured book graph slice via hermes-graph. Defaults to "
                "dry_run. Upsert requires human_approved=true. Never writes Qdrant, "
                "SQLite, vault notes, or policy files. source_id must be listed in "
                "graph.allowed_book_source_ids."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "source_id": {
                        "type": "string",
                        "description": "Must be listed in graph.allowed_book_source_ids",
                    },
                    "write_mode": {
                        "type": "string",
                        "enum": ["dry_run", "upsert"],
                        "description": "Default dry_run",
                    },
                    "human_approved": {
                        "type": "boolean",
                        "description": "Required true for upsert. Default false.",
                        "default": False,
                    },
                    "qdrant_crosswalk_path": {
                        "type": "string",
                        "description": "Optional JSON map of source chunk IDs to existing Qdrant point IDs",
                    },
                    "report_out": {
                        "type": "string",
                        "description": "Optional report path; must stay under the graph reports directory",
                    },
                },
                "required": ["source_id"],
            },
        },
        {
            "name": "graph_maintenance",
            "description": (
                "Read-only graph hygiene report: duplicate entities, claims without "
                "evidence, low-confidence edges, policy conflicts, missing Qdrant "
                "crosswalks. Does not merge entities, resolve conflicts, or rewrite notes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "min_confidence": {
                        "type": "number",
                        "description": "Low-confidence relationship threshold (default 0.75)",
                        "default": 0.75,
                    },
                    "output": {
                        "type": "string",
                        "description": "Optional report path under the graph reports directory",
                    },
                },
            },
        },
    ]


def provider_graph_tool_schemas() -> list[dict[str, Any]]:
    """Provider-adapter schemas using input_schema (Memory OS inner provider)."""

    converted = []
    for schema in openai_graph_tool_schemas():
        converted.append(
            {
                "name": schema["name"],
                "description": schema["description"],
                "input_schema": schema["parameters"],
            }
        )
    return converted


def dispatch_graph_tool(
    name: str,
    arguments: dict[str, Any] | None,
    *,
    memory_app: Any = None,
    graph_client: Any = None,
    builder_factory: Callable[[GraphConfig], Any] | None = None,
    neo4j_client_factory: Callable[[GraphConfig], Any] | None = None,
    config_path: str | Path | None = None,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    arguments = dict(arguments or {})
    if name == "graph_retrieve":
        return handle_graph_retrieve(
            memory_app,
            arguments,
            graph_client=graph_client,
            config_path=config_path,
            environ=environ,
            neo4j_client_factory=neo4j_client_factory,
        )
    if name == "graph_build_book":
        return handle_graph_build_book(
            arguments,
            config_path=config_path,
            environ=environ,
            builder_factory=builder_factory,
            neo4j_client_factory=neo4j_client_factory,
        )
    if name == "graph_maintenance":
        return handle_graph_maintenance(
            arguments,
            config_path=config_path,
            environ=environ,
            neo4j_client_factory=neo4j_client_factory,
        )
    if name == "graph_policy_ingest":
        return handle_graph_policy_ingest(arguments, environ=environ)
    if name == "graph_review":
        return handle_graph_review(arguments, environ=environ)
    raise ValueError(f"Unknown graph tool: {name}")


def handle_graph_retrieve(
    memory_app: Any,
    arguments: dict[str, Any],
    *,
    graph_client: Any = None,
    config_path: str | Path | None = None,
    environ: dict[str, str] | None = None,
    neo4j_client_factory: Callable[[GraphConfig], Any] | None = None,
) -> dict[str, Any]:
    query = str(arguments.get("query") or "").strip()
    if not query:
        return _error("query is required", action="graph_retrieve")
    if memory_app is None:
        return _error("Memory OS provider is not initialized", action="graph_retrieve")

    enabled = graph_enabled(environ)
    warnings: list[str] = []
    client = graph_client
    write_mode = "read"
    if not enabled:
        client = None
        warnings.append("graph_disabled")
    elif client is None:
        client, connect_warnings = _try_graph_client(
            config_path, environ, neo4j_client_factory
        )
        warnings.extend(connect_warnings)

    try:
        adapter = GraphRetrievalAdapter(memory_app, client)
        packet = adapter.retrieve(
            query,
            profile=str(arguments.get("profile") or "minimal"),
            max_context_tokens=int(arguments.get("max_context_tokens") or 4000),
            include_low_confidence=truthy(arguments.get("include_low_confidence", False)),
        )
    except Exception as exc:
        logger.warning("graph_retrieve memory fallback after error: %s", exc.__class__.__name__)
        packet = _memory_only_packet(memory_app, query, arguments, f"graph_unavailable:{exc.__class__.__name__}")

    packet["review_warnings"] = warnings + list(packet.get("review_warnings") or [])
    packet["graph_enabled"] = enabled
    packet["write_mode"] = write_mode
    _log_action(
        action="graph_retrieve",
        source_ids=_source_ids_from_packet(packet),
        write_mode=write_mode,
        warnings=packet["review_warnings"],
        counts=packet.get("result_counts") or {},
    )
    return packet


def handle_graph_build_book(
    arguments: dict[str, Any],
    *,
    config_path: str | Path | None = None,
    environ: dict[str, str] | None = None,
    builder_factory: Callable[[GraphConfig], Any] | None = None,
    neo4j_client_factory: Callable[[GraphConfig], Any] | None = None,
) -> dict[str, Any]:
    source_id = str(arguments.get("source_id") or "").strip()
    write_mode = str(arguments.get("write_mode") or "dry_run").strip() or "dry_run"
    human_approved = truthy(arguments.get("human_approved", False))
    enabled = graph_enabled(environ)

    if not source_id:
        return _error("source_id is required", action="graph_build_book", write_mode=write_mode)
    if write_mode not in {"dry_run", "upsert"}:
        return _error("write_mode must be dry_run or upsert", action="graph_build_book", source_ids=[source_id])
    if write_mode == "upsert" and not human_approved:
        return {
            "status": "approval_required",
            "error": "upsert requires explicit human_approved=true",
            "write_mode": "dry_run",
            "source_id": source_id,
            "review_warnings": ["upsert_blocked_without_human_approved"],
        }
    if write_mode == "upsert" and not enabled:
        return {
            "status": "graph_disabled",
            "error": "HERMES_GRAPH_ENABLED is false; refusing upsert",
            "write_mode": "dry_run",
            "source_id": source_id,
            "review_warnings": ["graph_disabled"],
        }

    try:
        config = load_graph_config(config_path, environ)
    except (GraphConfigError, OSError) as exc:
        return _error(str(exc), action="graph_build_book", source_ids=[source_id], write_mode=write_mode)

    if source_id not in config.allowed_book_source_ids:
        result = _error(
            f"Unsupported source_id {source_id!r}. Allowed: {list(config.allowed_book_source_ids)}",
            action="graph_build_book",
            source_ids=[source_id],
            write_mode=write_mode,
        )
        result["allowed_source_ids"] = list(config.allowed_book_source_ids)
        return result

    requested_out = arguments.get("report_out")
    report_path = None
    if requested_out or write_mode == "dry_run":
        try:
            report_path = _safe_report_path(config, requested_out, f"{source_id}-{write_mode}.json")
        except ValueError as exc:
            return _error(str(exc), action="graph_build_book", source_ids=[source_id], write_mode=write_mode)

    client = None
    if write_mode == "upsert":
        try:
            factory = neo4j_client_factory or Neo4jClient.from_config
            client = factory(config)
        except Exception as exc:
            return _error(
                f"Neo4j client unavailable for upsert: {exc.__class__.__name__}",
                action="graph_build_book",
                source_ids=[source_id],
                write_mode=write_mode,
            )

    try:
        crosswalk = _load_crosswalk(arguments.get("qdrant_crosswalk_path"))
        builder = (builder_factory or GraphBookBuilder)(config)
        result = builder.build(
            source_id,
            write_mode=write_mode,
            qdrant_crosswalk=crosswalk,
            client=client,
        )
    except Exception as exc:
        return _error(
            f"graph_build_book failed: {exc.__class__.__name__}: {exc}",
            action="graph_build_book",
            source_ids=[source_id],
            write_mode=write_mode,
        )
    if report_path is not None:
        _write_json_report(report_path, {key: value for key, value in result.items() if key != "plan"})

    compact = {key: value for key, value in result.items() if key != "plan"}
    compact["report_path"] = str(report_path) if report_path else None
    compact["plan_omitted"] = True
    compact["review_warnings"] = list(result.get("warnings") or [])
    _log_action(
        action="graph_build_book",
        source_ids=[source_id],
        write_mode=write_mode,
        warnings=compact["review_warnings"],
        counts=result.get("stats") or {},
    )
    return compact


def handle_graph_maintenance(
    arguments: dict[str, Any],
    *,
    config_path: str | Path | None = None,
    environ: dict[str, str] | None = None,
    neo4j_client_factory: Callable[[GraphConfig], Any] | None = None,
) -> dict[str, Any]:
    min_confidence = float(arguments.get("min_confidence") or DEFAULT_MIN_CONFIDENCE)
    try:
        config = load_graph_config(config_path, environ)
    except (GraphConfigError, OSError) as exc:
        return _error(str(exc), action="graph_maintenance", write_mode="read")

    client, warnings = _try_graph_client(config_path, environ, neo4j_client_factory, config=config)
    empty = {
        "duplicate_entities": [],
        "claims_without_evidence": [],
        "low_confidence_relationships": [],
        "policy_conflicts": [],
        "missing_qdrant_crosswalk": [],
    }
    if client is None:
        result = {
            "status": "degraded",
            "write_mode": "read",
            "output_path": None,
            "counts": {key: 0 for key in empty},
            "review_warnings": warnings or ["graph_unavailable"],
            "findings": empty,
        }
        _log_action("graph_maintenance", [], "read", result["review_warnings"], result["counts"])
        return result

    try:
        findings = collect_maintenance(client, min_confidence=min_confidence)
    except Exception as exc:
        warnings.append(f"graph_unavailable:{exc.__class__.__name__}")
        result = {
            "status": "degraded",
            "write_mode": "read",
            "output_path": None,
            "counts": {key: 0 for key in empty},
            "review_warnings": warnings,
            "findings": empty,
        }
        _log_action("graph_maintenance", [], "read", warnings, result["counts"])
        return result

    try:
        output = _safe_report_path(config, arguments.get("output"), "graph-maintenance.md")
        write_maintenance_report(findings, output)
    except ValueError as exc:
        return _error(str(exc), action="graph_maintenance", write_mode="read")

    counts = {key: len(value) for key, value in findings.items()}
    result = {
        "status": "reported",
        "write_mode": "read",
        "output_path": str(output),
        "counts": counts,
        "review_warnings": warnings,
        "auto_merged": False,
        "notes_rewritten": False,
    }
    _log_action("graph_maintenance", [], "read", warnings, counts)
    return result


def handle_graph_policy_ingest(arguments: dict[str, Any], *, environ: dict[str, str] | None = None) -> dict[str, Any]:
    _log_action("graph_policy_ingest", [], "none", [POLICY_INGEST_STATUS], {})
    return {
        "status": POLICY_INGEST_STATUS,
        "error": (
            "graph_policy_ingest is staged only. Policy adapter and tests are not "
            "activated. See docs/graph-policy-ingest-spec.md."
        ),
        "write_mode": "none",
        "review_warnings": ["policy_ingest_not_activated"],
    }


def handle_graph_review(arguments: dict[str, Any], *, environ: dict[str, str] | None = None) -> dict[str, Any]:
    _log_action("graph_review", [], "none", [REVIEW_STATUS], {})
    return {
        "status": REVIEW_STATUS,
        "error": (
            "graph_review is staged only until the policy adapter design is reviewed. "
            "See docs/graph-review-spec.md. Never merge entities or promote graph "
            "material into vault canon or Memory OS."
        ),
        "write_mode": "none",
        "review_warnings": ["graph_review_not_activated"],
        "auto_merged": False,
        "promoted_to_vault": False,
        "promoted_to_memory_os": False,
    }


def load_graph_config(config_path: str | Path | None = None, environ: dict[str, str] | None = None) -> GraphConfig:
    env = os.environ if environ is None else environ
    raw = config_path or env.get(GRAPH_CONFIG_ENV) or _DEFAULT_CONFIG
    return GraphConfig.load(Path(raw))


def _try_graph_client(
    config_path: str | Path | None,
    environ: dict[str, str] | None,
    neo4j_client_factory: Callable[[GraphConfig], Any] | None,
    config: GraphConfig | None = None,
) -> tuple[Any, list[str]]:
    warnings: list[str] = []
    try:
        config = config or load_graph_config(config_path, environ)
        factory = neo4j_client_factory or Neo4jClient.from_config
        client = factory(config)
        health = getattr(client, "health", None)
        if callable(health) and not health():
            return None, ["graph_unavailable:health_check_failed"]
        return client, warnings
    except Exception as exc:
        return None, [f"graph_unavailable:{exc.__class__.__name__}"]


def _memory_only_packet(memory_app: Any, query: str, arguments: dict[str, Any], warning: str) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    try:
        hits = memory_app.retriever.search(query, limit=5)
    except Exception as exc:
        warning = f"{warning};memory_search_failed:{exc.__class__.__name__}"
    return {
        "query": query,
        "profile": str(arguments.get("profile") or "minimal"),
        "context_budget_tokens": int(arguments.get("max_context_tokens") or 4000),
        "semantic_hits": hits,
        "graph_hits": [],
        "claims": [],
        "policies": [],
        "open_questions": [],
        "review_warnings": [warning],
        "provenance": [],
        "result_counts": {"semantic_hits": len(hits), "graph_hits": 0, "claims": 0, "provenance": 0, "excluded": 0},
    }


def _safe_report_path(config: GraphConfig, requested: str | None, default_name: str) -> Path:
    reports_root = config.reports_root.resolve()
    path = Path(requested) if requested else reports_root / default_name
    if not path.is_absolute():
        path = reports_root / path
    path = path.resolve()
    if path != reports_root and reports_root not in path.parents:
        raise ValueError("report path must stay under the graph reports directory")
    return path


def _write_json_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _load_crosswalk(path_value: object) -> dict[str, str]:
    if not path_value:
        return {}
    path = Path(str(path_value))
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in raw.items()):
        raise ValueError("Qdrant crosswalk must be a JSON object mapping source chunk IDs to point IDs.")
    return raw


def _source_ids_from_packet(packet: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for row in packet.get("provenance") or []:
        source_id = row.get("source_id")
        if source_id and source_id not in ids:
            ids.append(str(source_id))
    return ids


def _log_action(
    action: str,
    source_ids: list[str],
    write_mode: str,
    warnings: list[str],
    counts: dict[str, Any],
) -> None:
    logger.info(
        "graph_tool action=%s source_ids=%s write_mode=%s warnings=%s counts=%s",
        action,
        source_ids,
        write_mode,
        warnings,
        counts,
    )


def _error(
    message: str,
    *,
    action: str,
    source_ids: list[str] | None = None,
    write_mode: str = "none",
) -> dict[str, Any]:
    warnings = [message]
    _log_action(action, source_ids or [], write_mode, warnings, {})
    return {
        "status": "error",
        "error": message,
        "write_mode": write_mode,
        "review_warnings": warnings,
    }
