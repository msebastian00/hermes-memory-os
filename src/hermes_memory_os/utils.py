"""Shared utility functions."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True, sort_keys=True)


def loads(data: str | None, default: Any = None) -> Any:
    if not data:
        return default
    return json.loads(data)
