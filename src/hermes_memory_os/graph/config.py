"""Configuration for the optional graph layer."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

class GraphConfigError(ValueError):
    """Raised for invalid graph configuration."""

DEFAULT_ALLOWED_BOOK_SOURCE_IDS = ("book-finite-infinite-games-undated",)

@dataclass(frozen=True)
class GraphConfig:
    config_path: Path
    vault_root: Path
    reports_root: Path
    neo4j_uri: str | None
    neo4j_user: str | None
    neo4j_password: str | None
    neo4j_timeout_seconds: int
    neo4j_write_batch_size: int
    default_write_mode: str
    min_edge_confidence: float
    max_context_tokens: int
    allowed_book_source_ids: tuple[str, ...]

    @classmethod
    def load(cls, path: Path) -> "GraphConfig":
        path = path.resolve()
        if not path.is_file():
            raise GraphConfigError(f"Graph config does not exist: {path}")
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise GraphConfigError("Graph config must be a YAML mapping.")
        paths = raw.get("paths") or {}
        graph = raw.get("graph") or {}
        neo4j = raw.get("neo4j") or {}
        vault_root = _resolve_path(path, paths.get("vault_root"))
        reports_root = _resolve_path(path, graph.get("review_report_path", "graph/reports"))
        if vault_root is None:
            raise GraphConfigError("paths.vault_root is required.")
        allowed_book_source_ids = _allowed_book_source_ids(graph.get("allowed_book_source_ids"))
        return cls(
            config_path=path,
            vault_root=vault_root,
            reports_root=reports_root,
            neo4j_uri=_env_value(neo4j.get("uri_env", "NEO4J_URI")),
            neo4j_user=_env_value(neo4j.get("user_env", "NEO4J_USER")),
            neo4j_password=_env_value(neo4j.get("password_env", "NEO4J_PASSWORD")),
            neo4j_timeout_seconds=_positive_int(neo4j.get("timeout_seconds", 60), "neo4j.timeout_seconds"),
            neo4j_write_batch_size=_positive_int(neo4j.get("write_batch_size", 200), "neo4j.write_batch_size"),
            default_write_mode=str(graph.get("default_write_mode", "dry_run")),
            min_edge_confidence=float(graph.get("min_edge_confidence", 0.75)),
            max_context_tokens=int(graph.get("max_context_tokens", 4000)),
            allowed_book_source_ids=allowed_book_source_ids,
        )

    def require_neo4j(self) -> tuple[str, str, str]:
        if not self.neo4j_uri or not self.neo4j_user or not self.neo4j_password:
            raise GraphConfigError(
                "NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD are required for Neo4j operations."
            )
        if not self.neo4j_uri.startswith(("http://", "https://")):
            raise GraphConfigError("NEO4J_URI must be an HTTP URL for the built-in client.")
        return self.neo4j_uri, self.neo4j_user, self.neo4j_password

def _allowed_book_source_ids(value: Any) -> tuple[str, ...]:
    if value is None:
        return DEFAULT_ALLOWED_BOOK_SOURCE_IDS
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise GraphConfigError("graph.allowed_book_source_ids must be a list of source IDs.")
    values = tuple(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))
    if not values:
        raise GraphConfigError("graph.allowed_book_source_ids must not be empty.")
    return values

def _resolve_path(config_path: Path, value: Any) -> Path | None:
    if value is None:
        return None
    candidate = Path(str(value))
    if not candidate.is_absolute():
        candidate = config_path.parent / candidate
    return candidate.resolve()

def _env_value(name: str) -> str | None:
    value = os.environ.get(name)
    return value if value else None


def _positive_int(value: Any, name: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise GraphConfigError(f"{name} must be a positive integer.") from exc
    if result < 1:
        raise GraphConfigError(f"{name} must be a positive integer.")
    return result
