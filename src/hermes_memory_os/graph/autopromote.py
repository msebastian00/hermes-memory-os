"""Autonomous, evidence-gated promotion of intentionally queued books."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from hermes_memory_os.utils import now_iso

from .builder import GraphBookBuilder, discover_book
from .config import GraphConfig
from .crosswalk import index_book_crosswalk, write_crosswalk
from .maintenance import collect_maintenance, write_maintenance_report
from .overlap import collect_overlap_review, concept_candidates, write_overlap_review_report
from .source_integrity import validate_book_artifacts
from .artifact_prep import embedding_input_limit, prepare_book_artifacts
from .multimodal import discover_book_pdf, extract_pdf_visual_evidence, visual_evidence_plan, visual_processing_enabled


class AutoPromotionError(ValueError):
    """Raised when a queued source does not meet a machine-enforced write gate."""


def queued_book_source_ids(vault_root: Path) -> list[str]:
    """Return source IDs intentionally queued for book ingestion, excluding blocked/review."""

    queue_root = vault_root / "05_QUEUE" / "book-ingestion"
    source_ids: set[str] = set()
    for state in ("incoming", "processing", "completed"):
        for path in sorted((queue_root / state).glob("*.md")):
            metadata = _frontmatter(path)
            if not _actionable_queue_card(metadata):
                continue
            source_id = str(metadata.get("source_id") or "").strip()
            if source_id:
                source_ids.add(source_id)
    return sorted(source_ids)


def is_queued_book_source(vault_root: Path, source_id: str) -> bool:
    return source_id in queued_book_source_ids(vault_root)


def default_chunk_bodies_path(config: GraphConfig, source_id: str) -> Path:
    return config.vault_root / "06_GENERATED" / "source-analysis" / source_id / "chunk-bodies.json"


def promote_queued_book(
    memory_app: Any,
    config: GraphConfig,
    source_id: str,
    *,
    client: Any,
    chunk_bodies_path: Path | None = None,
    write_mode: str = "upsert",
) -> dict[str, Any]:
    """Run dry validation, crosswalk, graph upsert, and maintenance without human input."""

    if write_mode not in {"dry_run", "upsert"}:
        raise AutoPromotionError("write_mode must be dry_run or upsert")

    if not is_queued_book_source(config.vault_root, source_id):
        raise AutoPromotionError(f"source_id is not present in the book-ingestion queue: {source_id}")
    if write_mode == "upsert" and (client is None or (callable(getattr(client, "health", None)) and not client.health())):
        raise AutoPromotionError("Neo4j must be reachable before autonomous promotion")
    if write_mode == "upsert" and getattr(memory_app, "semantic_indexer", None) is None:
        raise AutoPromotionError("Memory OS semantic indexing must be enabled before autonomous promotion")

    limit = embedding_input_limit(memory_app)
    prepared = prepare_book_artifacts(
        config,
        source_id,
        write_mode=write_mode,
        max_chunk_chars=limit,
        memory_app=memory_app,
    )
    bodies_path = (chunk_bodies_path or default_chunk_bodies_path(config, source_id)).resolve()
    if write_mode == "upsert":
        bodies_path = Path(prepared["chunk_bodies_path"]).resolve()

    book = discover_book(config.vault_root, source_id)
    integrity = validate_book_artifacts(book)
    if not integrity["safe_for_qdrant_crosswalk"]:
        raise AutoPromotionError("source-integrity validation blocked promotion: " + ", ".join(integrity["problems"]))
    if not bodies_path.is_file():
        raise AutoPromotionError(f"missing exact chunk-body manifest: {bodies_path}")

    # Validate every write input first. These two dry plans mutate no source system.
    crosswalk_dry_run = index_book_crosswalk(
        memory_app, config, source_id, bodies_path, write_mode="dry_run"
    )
    graph_dry_run = GraphBookBuilder(config).build(source_id, write_mode="dry_run")

    overlap = collect_overlap_review(
        concept_candidates(source_id, book.concepts),
        graph_client=client,
        memory_app=memory_app,
        vault_root=config.vault_root,
    )
    overlap_path = config.reports_root / f"{source_id}-overlap-review.md"
    write_overlap_review_report(overlap, overlap_path)

    visual_dry_run = _promote_visual_evidence(config, book, client=client, write_mode="dry_run")

    if write_mode == "dry_run":
        return {
            "status": "planned",
            "source_id": source_id,
            "write_mode": "dry_run",
            "authorization": "book-ingestion-queue",
            "source_integrity": integrity,
            "crosswalk_dry_run": crosswalk_dry_run,
            "graph_dry_run": {key: value for key, value in graph_dry_run.items() if key != "plan"},
            "visual_dry_run": visual_dry_run,
            "overlap_review": {
                "path": str(overlap_path),
                "status": overlap["status"],
                "counts": overlap["counts"],
                "warnings": overlap["review_warnings"],
                "auto_merged": False,
            },
        }

    crosswalk = index_book_crosswalk(
        memory_app, config, source_id, bodies_path, write_mode="upsert"
    )
    crosswalk_path = config.reports_root / "crosswalks" / f"{source_id}.json"
    write_crosswalk(crosswalk, crosswalk_path)

    graph_upsert = GraphBookBuilder(config).build(
        source_id,
        write_mode="upsert",
        qdrant_crosswalk=dict(crosswalk["qdrant_point_ids"]),
        client=client,
    )
    visual_upsert = _promote_visual_evidence(config, book, client=client, write_mode="upsert")
    maintenance = collect_maintenance(client, min_confidence=config.min_edge_confidence)
    maintenance_path = config.reports_root / "graph-maintenance.md"
    write_maintenance_report(maintenance, maintenance_path)

    result = {
        "status": "promoted",
        "source_id": source_id,
        "generated_at": now_iso(),
        "authorization": "book-ingestion-queue",
        "source_integrity": integrity,
        "crosswalk_dry_run": crosswalk_dry_run,
        "graph_dry_run": {key: value for key, value in graph_dry_run.items() if key != "plan"},
        "overlap_review": {
            "path": str(overlap_path),
            "status": overlap["status"],
            "counts": overlap["counts"],
            "warnings": overlap["review_warnings"],
            "auto_merged": False,
        },
        "crosswalk_path": str(crosswalk_path),
        "graph_upsert": {key: value for key, value in graph_upsert.items() if key != "plan"},
        "visual_dry_run": visual_dry_run,
        "visual_upsert": visual_upsert,
        "maintenance_path": str(maintenance_path),
        "maintenance_counts": {key: len(value) for key, value in maintenance.items()},
    }
    report_path = config.reports_root / "promotions" / f"{source_id}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    result["report_path"] = str(report_path)
    return result


def promote_queued_books(
    memory_app: Any,
    config: GraphConfig,
    *,
    client: Any,
    write_mode: str = "upsert",
) -> dict[str, Any]:
    """Promote every queue-authorized source that is fully machine-ready."""

    promoted: list[dict[str, Any]] = []
    deferred: list[dict[str, str]] = []
    for source_id in queued_book_source_ids(config.vault_root):
        try:
            promoted.append(promote_queued_book(memory_app, config, source_id, client=client, write_mode=write_mode))
        except Exception as exc:
            deferred.append({"source_id": source_id, "reason": str(exc)})
    result = {
        "status": "swept",
        "write_mode": write_mode,
        "generated_at": now_iso(),
        "promoted": promoted,
        "deferred": deferred,
        "counts": {"promoted": len(promoted), "deferred": len(deferred)},
    }
    report_path = config.reports_root / "promotions" / "queued-sweep.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    result["report_path"] = str(report_path)
    return result


def _frontmatter(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not text.startswith("---\n"):
        return {}
    head, separator, _body = text[4:].partition("\n---\n")
    if not separator:
        return {}
    parsed = yaml.safe_load(head) or {}
    return parsed if isinstance(parsed, dict) else {}


def _actionable_queue_card(metadata: dict[str, Any]) -> bool:
    """Exclude explicitly superseded and cleanup-only cards from autonomous promotion."""

    if str(metadata.get("superseded_by") or "").strip():
        return False
    if str(metadata.get("cleanup_note") or "").strip():
        return False
    source_path = str(metadata.get("source_path") or "")
    return "/processed/" not in source_path


def _promote_visual_evidence(
    config: GraphConfig,
    book: Any,
    *,
    client: Any,
    write_mode: str,
) -> dict[str, Any]:
    """Run visual extraction as an additive, evidence-gated promotion step."""
    if not visual_processing_enabled():
        return {"status": "disabled", "reason": "HERMES_GRAPH_VISUAL_ENABLED or VLM endpoint is not configured"}
    pdf_path = discover_book_pdf(book, config.vault_root)
    if pdf_path is None:
        return {"status": "not_applicable", "reason": "no manifest-declared immutable PDF"}
    output = config.reports_root / "multimodal" / book.source_id
    extraction = extract_pdf_visual_evidence(pdf_path, output)
    plan = visual_evidence_plan(
        config,
        book.source_id,
        extraction["records"],
        min_confidence=config.min_edge_confidence,
    )
    result = {
        "status": "planned",
        "pdf_path": str(pdf_path),
        "pages_rendered": extraction["pages_rendered"],
        "evidence_records": len(extraction["records"]),
        "nodes": len(plan["nodes"]),
        "relationships": len(plan["relationships"]),
        "warnings": extraction["warnings"] + plan["warnings"],
        "output_path": str(output),
    }
    if write_mode == "upsert" and plan["nodes"]:
        result["write_result"] = client.upsert(plan["nodes"], plan["relationships"])
        result["superseded_variants"] = client.supersede_visual_variants(plan["visual_records"])
        result["status"] = "upserted"
    return result
