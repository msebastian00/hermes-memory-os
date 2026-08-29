"""Feature flags for the optional Hermes knowledge-graph tools."""

from __future__ import annotations

import os


GRAPH_ENABLED_ENV = "HERMES_GRAPH_ENABLED"
GRAPH_CONFIG_ENV = "HERMES_GRAPH_CONFIG"

_TRUTHY = {"1", "true", "yes", "on"}


def graph_enabled(environ: dict[str, str] | None = None) -> bool:
    """Graph expansion and writes are off unless HERMES_GRAPH_ENABLED is truthy."""

    env = os.environ if environ is None else environ
    value = str(env.get(GRAPH_ENABLED_ENV, "false")).strip().lower()
    return value in _TRUTHY


def truthy(value: object) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in _TRUTHY
    return False
