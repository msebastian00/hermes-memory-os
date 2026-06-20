"""Configuration loading for Hermes Memory OS."""

from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import ConfigError


DEFAULT_CONFIG: dict[str, Any] = {
    "paths": {
        "base_dir": "${HERMES_MEMORY_HOME}",
        "vault_dir": "${HERMES_MEMORY_HOME}/vault",
        "sqlite_path": "${HERMES_MEMORY_HOME}/db/memory.sqlite",
        "logs_dir": "${HERMES_MEMORY_HOME}/logs",
    },
    "wiki_brain": {"enabled": True, "paths": []},
    "qdrant": {
        "enabled": False,
        "url": "http://localhost:6333",
        "vector_size": 768,
        "distance": "Cosine",
        "collections": {
            "memories": "hermes_memories",
            "wiki": "hermes_wiki",
            "captures": "hermes_captures",
            "sources": "hermes_sources",
            "agent_learning": "hermes_agent_learning",
        },
    },
    "embeddings": {
        "provider": "none",
        "base_url": "http://localhost:11434",
        "model": "nomic-embed-text",
        "dimension": 768,
    },
    "retrieval": {
        "max_injected": 8,
        "min_final_score": 0.35,
        "min_final_score_by_kind": {
            "memory": 0.35,
            "source_chunk": 0.20,
        },
        "weights": {
            "semantic": 0.45,
            "keyword": 0.20,
            "entity": 0.15,
            "scope": 0.10,
            "recency": 0.05,
            "trust": 0.05,
        },
    },
    "privacy": {
        "cloud_allowed": False,
        "never_send_raw_events_to_cloud": True,
    },
    "self_learning": {"enabled": True, "mode": "log_and_review"},
}


@dataclass(frozen=True)
class MemoryConfig:
    """Resolved runtime configuration."""

    raw: dict[str, Any]
    base_dir: Path
    vault_dir: Path
    sqlite_path: Path
    logs_dir: Path
    wiki_paths: list[Path] = field(default_factory=list)

    @property
    def retrieval(self) -> dict[str, Any]:
        return self.raw["retrieval"]

    @property
    def qdrant(self) -> dict[str, Any]:
        return self.raw["qdrant"]

    @property
    def embeddings(self) -> dict[str, Any]:
        return self.raw["embeddings"]


def load_config(
    config_path: str | Path | None = None,
    data_dir: str | Path | None = None,
) -> MemoryConfig:
    """Load config from defaults plus optional YAML overrides."""

    merged = _deep_merge(DEFAULT_CONFIG, _read_yaml(config_path))
    if data_dir is not None:
        merged["paths"]["base_dir"] = str(data_dir)
        merged["paths"]["vault_dir"] = str(Path(data_dir) / "vault")
        merged["paths"]["sqlite_path"] = str(Path(data_dir) / "db" / "memory.sqlite")
        merged["paths"]["logs_dir"] = str(Path(data_dir) / "logs")

    expanded = _expand_env(merged)
    base_dir_raw = expanded["paths"]["base_dir"]
    if not base_dir_raw or "${HERMES_MEMORY_HOME}" in str(base_dir_raw):
        raise ConfigError("Set HERMES_MEMORY_HOME, pass --data-dir, or provide paths.base_dir.")

    base_dir = Path(expanded["paths"]["base_dir"]).expanduser()
    vault_dir = Path(expanded["paths"]["vault_dir"]).expanduser()
    sqlite_path = Path(expanded["paths"]["sqlite_path"]).expanduser()
    logs_dir = Path(expanded["paths"]["logs_dir"]).expanduser()
    wiki_paths = [
        Path(path).expanduser()
        for path in expanded.get("wiki_brain", {}).get("paths", [])
        if path
    ]

    _validate_privacy(expanded)
    return MemoryConfig(
        raw=expanded,
        base_dir=base_dir,
        vault_dir=vault_dir,
        sqlite_path=sqlite_path,
        logs_dir=logs_dir,
        wiki_paths=wiki_paths,
    )


def _read_yaml(config_path: str | Path | None) -> dict[str, Any]:
    if config_path is None:
        return {}
    path = Path(config_path)
    if not path.exists():
        raise ConfigError(f"Config file does not exist: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ConfigError("Config root must be a mapping.")
    return data


def _expand_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, str):
        return os.path.expandvars(value)
    return value


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _validate_privacy(config: dict[str, Any]) -> None:
    privacy = config.get("privacy", {})
    if privacy.get("cloud_allowed") is not True:
        provider = config.get("embeddings", {}).get("provider", "none")
        base_url = config.get("embeddings", {}).get("base_url", "")
        if provider in {"openai", "hosted"} or "api.openai.com" in base_url:
            raise ConfigError("Hosted embedding endpoints require privacy.cloud_allowed=true.")
