"""Command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .app import MemoryApp
from .chief import daily_brief, process_inbox, self_review, weekly_connections
from .config import ConfigError
from .provider import create_provider


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hermes-memory")
    parser.add_argument("--config", help="Path to YAML config.")
    parser.add_argument("--data-dir", help="Override HERMES_MEMORY_HOME.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Initialize local storage.")
    doctor = sub.add_parser("doctor", help="Validate local storage and config.")
    doctor.add_argument("--strict", action="store_true", help="Exit non-zero unless semantic production readiness checks pass.")

    ingest = sub.add_parser("ingest", help="Ingest local source content.")
    ingest.add_argument("--path", action="append", help="Source file or directory. May be repeated.")
    ingest.add_argument("--source-type", help="Override inferred source type for all ingested files.")
    ingest.add_argument("--reindex", action="store_true", help="Mark unchanged matching sources for re-indexing.")

    search = sub.add_parser("search", help="Search memory.")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=8)
    search.add_argument("--source-type", action="append", help="Filter source chunks by source type. May be repeated.")

    add = sub.add_parser("add", help="Add a durable memory.")
    add.add_argument("--type", required=True, dest="memory_type")
    add.add_argument("--scope", required=True)
    add.add_argument("--title")
    add.add_argument("--summary", required=True)
    add.add_argument("--text", required=True)
    add.add_argument("--tag", action="append", default=[])
    add.add_argument("--entity", action="append", default=[])

    archive = sub.add_parser("archive", help="Archive a memory.")
    archive.add_argument("memory_id")
    archive.add_argument("--reason")

    candidates = sub.add_parser("candidates", help="Review extraction candidates.")
    candidate_sub = candidates.add_subparsers(dest="candidate_command", required=True)
    candidate_list = candidate_sub.add_parser("list", help="List extraction candidates.")
    candidate_list.add_argument("--status", default="pending_review")
    candidate_list.add_argument("--limit", type=int, default=50)

    candidate_create = candidate_sub.add_parser("create", help="Create an extraction candidate.")
    candidate_create.add_argument("--source-event-id", action="append", default=[], required=True)
    candidate_create.add_argument("--type", required=True, dest="memory_type")
    candidate_create.add_argument("--scope", required=True)
    candidate_create.add_argument("--title")
    candidate_create.add_argument("--summary", required=True)
    candidate_create.add_argument("--text", required=True)
    candidate_create.add_argument("--entity", action="append", default=[])
    candidate_create.add_argument("--tag", action="append", default=[])
    candidate_create.add_argument("--confidence", type=float, default=0.5)
    candidate_create.add_argument("--reason")

    candidate_update = candidate_sub.add_parser("update", help="Update an extraction candidate review state.")
    candidate_update.add_argument("candidate_id")
    candidate_update.add_argument("--status", choices=["pending_review", "approved", "rejected", "archived"])
    candidate_update.add_argument("--title")
    candidate_update.add_argument("--summary")
    candidate_update.add_argument("--text", dest="canonical_text")
    candidate_update.add_argument("--confidence", type=float)
    candidate_update.add_argument("--reason")

    chief = sub.add_parser("chief", help="Generate Chief of Staff workflow drafts.")
    chief_sub = chief.add_subparsers(dest="chief_command", required=True)

    process = chief_sub.add_parser("process-inbox", help="Generate an inbox processing draft.")
    process.add_argument("--path", action="append", required=True, help="Inbox file or directory. May be repeated.")
    process.add_argument("--output-dir")
    process.add_argument("--limit", type=int, default=8)

    daily = chief_sub.add_parser("daily-brief", help="Generate a daily brief draft.")
    daily.add_argument("--output-dir")
    daily.add_argument("--limit", type=int, default=8)

    weekly = chief_sub.add_parser("weekly-connections", help="Generate a weekly connections draft.")
    weekly.add_argument("--output-dir")
    weekly.add_argument("--limit", type=int, default=12)

    review = chief_sub.add_parser("self-review", help="Generate a self-review draft.")
    review.add_argument("--output-dir")
    review.add_argument("--limit", type=int, default=20)

    reindex_memories = sub.add_parser("reindex-memories", help="Reindex all active durable memories into Qdrant.")
    reindex_memories.add_argument("--batch-size", type=int, default=200)

    smoke = sub.add_parser("provider-smoke", help="Verify the Hermes provider entrypoint works.")
    smoke.add_argument("--query", default="Hermes Memory OS provider smoke")

    args = parser.parse_args(argv)
    try:
        app = MemoryApp.from_config(config_path=args.config, data_dir=args.data_dir)
        if args.command == "init":
            app.init_storage()
            print_json({"initialized": True, "base_dir": str(app.config.base_dir)})
            return 0

        if args.command == "doctor":
            app.store.init()
            status = app.doctor()
            if args.strict:
                failures = doctor_strict_failures(status)
                status["strict_ready"] = not failures
                status["strict_failures"] = failures
                print_json(status)
                return 0 if not failures else 1
            print_json(status)
            return 0

        app.init_storage()

        if args.command == "ingest":
            paths = [Path(item) for item in (args.path or [])] or app.config.wiki_paths
            if not paths:
                raise ConfigError("Provide --path or configure wiki_brain.paths.")
            print_json(app.ingest_sources(paths, source_type=args.source_type, reindex=args.reindex))
            return 0

        if args.command == "search":
            print_json(
                {
                    "results": app.retriever.search(
                        args.query,
                        limit=args.limit,
                        source_types=args.source_type,
                    )
                }
            )
            return 0

        if args.command == "reindex-memories":
            print_json(app.reindex_memories(batch_size=args.batch_size))
            return 0

        if args.command == "add":
            result = app.add_memory(
                memory_type=args.memory_type,
                scope=args.scope,
                title=args.title,
                summary=args.summary,
                canonical_text=args.text,
                tags=args.tag,
                entities=args.entity,
            )
            print_json(result)
            return 0

        if args.command == "archive":
            app.store.archive_memory(args.memory_id, args.reason)
            print_json({"archived": True, "memory_id": args.memory_id})
            return 0

        if args.command == "candidates":
            if args.candidate_command == "list":
                print_json(
                    {
                        "candidates": app.store.list_extraction_candidates(
                            status=args.status,
                            limit=args.limit,
                        )
                    }
                )
                return 0
            if args.candidate_command == "create":
                candidate_id = app.store.create_extraction_candidate(
                    source_event_ids=args.source_event_id,
                    memory_type=args.memory_type,
                    scope=args.scope,
                    title=args.title,
                    summary=args.summary,
                    canonical_text=args.text,
                    entities=args.entity,
                    tags=args.tag,
                    confidence=args.confidence,
                    reason_to_save=args.reason,
                )
                print_json({"candidate_id": candidate_id})
                return 0
            if args.candidate_command == "update":
                app.store.update_extraction_candidate(
                    args.candidate_id,
                    status=args.status,
                    title=args.title,
                    summary=args.summary,
                    canonical_text=args.canonical_text,
                    confidence=args.confidence,
                    reason_to_save=args.reason,
                )
                print_json({"updated": True, "candidate_id": args.candidate_id})
                return 0

        if args.command == "chief":
            output_dir = Path(args.output_dir) if args.output_dir else None
            if args.chief_command == "process-inbox":
                output = process_inbox(
                    app,
                    paths=[Path(path) for path in args.path],
                    output_dir=output_dir,
                    limit=args.limit,
                )
            elif args.chief_command == "daily-brief":
                output = daily_brief(app, output_dir=output_dir, limit=args.limit)
            elif args.chief_command == "weekly-connections":
                output = weekly_connections(app, output_dir=output_dir, limit=args.limit)
            elif args.chief_command == "self-review":
                output = self_review(app, output_dir=output_dir, limit=args.limit)
            else:
                raise ConfigError(f"Unknown chief command: {args.chief_command}")
            print_json({"output_path": str(output)})
            return 0

        if args.command == "provider-smoke":
            provider = create_provider({"config_path": args.config, "data_dir": args.data_dir})
            added = provider.handle_tool_call(
                "hermes_memory_add",
                {
                    "memory_type": "fact",
                    "scope": "system",
                    "title": "Hermes Memory OS provider smoke",
                    "summary": "Hermes can import and call the Hermes Memory OS provider.",
                    "canonical_text": "Hermes can import and call the Hermes Memory OS provider.",
                    "tags": ["hermes-dev"],
                    "entities": ["Hermes"],
                },
            )
            injected = provider.prefetch(args.query, {"client": "hermes-dev"})
            synced = provider.sync_turn(
                "provider smoke user turn",
                "provider smoke assistant turn",
                {"client": "hermes-dev", "conversation_id": "provider-smoke"},
            )
            print_json(
                {
                    "provider_imported": True,
                    "memory_id": added["memory_id"],
                    "prefetch_nonempty": bool(injected),
                    "raw_event_ids": synced["raw_event_ids"],
                }
            )
            return 0

    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 1


def print_json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def doctor_strict_failures(status: dict[str, object]) -> list[str]:
    failures = []
    required_true = {
        "base_dir_exists": "base_dir_missing",
        "vault_dir_exists": "vault_dir_missing",
        "sqlite_exists": "sqlite_missing",
        "logs_dir_exists": "logs_dir_missing",
        "semantic_enabled": "semantic_disabled",
        "embedding_reachable": "embedding_unreachable",
        "qdrant_enabled": "qdrant_disabled",
        "qdrant_reachable": "qdrant_unreachable",
    }
    for key, failure in required_true.items():
        if status.get(key) is not True:
            failures.append(failure)

    collections = status.get("qdrant_collections")
    if isinstance(collections, dict):
        missing = [
            role
            for role, collection in collections.items()
            if not isinstance(collection, dict) or collection.get("exists") is not True
        ]
        if missing:
            failures.append(f"qdrant_collections_missing:{','.join(sorted(missing))}")
    else:
        failures.append("qdrant_collections_unavailable")

    if status.get("embedding_provider") == "none":
        failures.append("embedding_provider_none")
    if status.get("cloud_allowed") is True:
        failures.append("cloud_allowed_enabled")
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
