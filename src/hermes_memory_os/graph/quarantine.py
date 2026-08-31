"""Reversibly retire graph material when its source-integrity gate fails."""

from __future__ import annotations

from typing import Any

from hermes_memory_os.utils import now_iso


def quarantine_book_source(
    memory_app: Any,
    graph_client: Any,
    source_id: str,
    *,
    reason: str,
    write_mode: str = "dry_run",
) -> dict[str, Any]:
    """Exclude active crosswalk and graph records from retrieval without deleting audit data."""

    if write_mode not in {"dry_run", "upsert"}:
        raise ValueError("write_mode must be dry_run or upsert")
    prefix = f"graph-crosswalk://{source_id}/"
    active_sources = memory_app.store.list_sources_by_path_prefix(prefix, status="active")
    result = {
        "source_id": source_id,
        "write_mode": write_mode,
        "reason": reason,
        "memory_source_ids": [str(item["id"]) for item in active_sources],
        "memory_sources_quarantined": 0,
        "graph_source_quarantined": False,
        "quarantined_at": now_iso(),
    }
    if write_mode == "dry_run":
        return result

    for source in active_sources:
        if memory_app.store.quarantine_source(str(source["id"]), reason=reason):
            result["memory_sources_quarantined"] += 1
    result["graph_source_quarantined"] = bool(
        graph_client.quarantine_source(source_id, reason=reason)
    )
    return result
