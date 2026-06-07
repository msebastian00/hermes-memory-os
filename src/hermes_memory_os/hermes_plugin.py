"""Hermes plugin entrypoint.

Hermes deployments can import this module and call `create_provider()` to obtain
the MemoryProvider-compatible adapter without depending on repository layout.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .provider import HermesMemoryOSProvider, create_provider

__all__ = ["HermesMemoryOSProvider", "create_provider", "provider_class"]

provider_class = HermesMemoryOSProvider


def load(config: dict[str, Any] | str | Path | None = None, hermes_home: str | Path | None = None) -> HermesMemoryOSProvider:
    """Compatibility loader for plugin systems that expect a load function."""

    return create_provider(config=config, hermes_home=hermes_home)
