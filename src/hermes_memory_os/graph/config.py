"""Configuration for the optional graph layer."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class GraphConfigError(ValueError):
    """Raised for invalid graph configuration."""


@dataclass(frozen=True)
class GraphConfig:
    config_path: Path
    vault_root: Path
    reports_root: Path
    neo4j_uri: str | None
    neo4j_user: str | None
    neo4j_password: str | None
    default_write_mode: str
    min_edge_confidence: float
    max_context_tokens: int

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
        return cls(
            config_path=path,
            vault_root=vault_root,
            reports_root=reports_root,
            neo4j_uri=_env_value(neo4j.get("uri_env", "NEO4J_URI")),
            neo4j_user=_env_value(neo4j.get("user_env", "NEO4J_USER")),
            neo4j_password=_env_value(neo4j.get("password_env", "NEO4J_PASSWORD")),
            default_write_mode=str(graph.get("default_write_mode", "dry_run")),
            min_edge_confidence=float(graph.get("min_edge_confidence", 0.75)),
            max_context_tokens=int(graph.get("max_context_tokens", 4000)),
        )

    def require_neo4j(self) -> tuple[str, str, str]:
        if not self.neo4j_uri or not self.neo4j_user or not self.neo4j_password:
            raise GraphConfigError(
                "NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD are required for Neo4j operations."
            )
        if not self.neo4j_uri.startswith(("http://", "https://")):
            raise GraphConfigError("NEO4J_URI must be an HTTP URL for the built-in client.")
        return self.neo4j_uri, self.neo4j_user, self.neo4j_password


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
