"""Command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .app import MemoryApp
from .config import ConfigError
from .ingest.markdown import ingest_paths
from .provider import create_provider


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hermes-memory")
    parser.add_argument("--config", help="Path to YAML config.")
    parser.add_argument("--data-dir", help="Override HERMES_MEMORY_HOME.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Initialize local storage.")
    sub.add_parser("doctor", help="Validate local storage and config.")

    ingest = sub.add_parser("ingest", help="Ingest Markdown/wiki-brain content.")
    ingest.add_argument("--path", action="append", help="Markdown file or directory. May be repeated.")

    search = sub.add_parser("search", help="Search memory.")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=8)

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
            print_json(app.doctor())
            return 0

        app.init_storage()

        if args.command == "ingest":
            paths = [Path(item) for item in (args.path or [])] or app.config.wiki_paths
            if not paths:
                raise ConfigError("Provide --path or configure wiki_brain.paths.")
            print_json(ingest_paths(app.store, paths))
            return 0

        if args.command == "search":
            print_json({"results": app.retriever.search(args.query, limit=args.limit)})
            return 0

        if args.command == "add":
            memory_id = app.store.add_memory(
                memory_type=args.memory_type,
                scope=args.scope,
                title=args.title,
                summary=args.summary,
                canonical_text=args.text,
                tags=args.tag,
                entities=args.entity,
            )
            print_json({"memory_id": memory_id})
            return 0

        if args.command == "archive":
            app.store.archive_memory(args.memory_id, args.reason)
            print_json({"archived": True, "memory_id": args.memory_id})
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


if __name__ == "__main__":
    raise SystemExit(main())
