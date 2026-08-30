"""Command line interface for the optional Hermes knowledge graph."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hermes_memory_os.app import MemoryApp
from .builder import GraphBookBuilder, discover_book
from .config import GraphConfig, GraphConfigError
from .crosswalk import index_book_crosswalk, write_crosswalk
from .policy import GraphPolicyBuilder
from .overlap import concept_candidates, collect_overlap_review, write_overlap_review_report
from .maintenance import collect_maintenance, write_maintenance_report
from .source_integrity import validate_book_source, write_source_integrity_report
from .neo4j import Neo4jClient
from .schema import initialize_schema


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hermes-graph")
    parser.add_argument("--config", required=True, help="Path to hermes-graph YAML configuration.")
    sub = parser.add_subparsers(dest="command", required=True)

    discover = sub.add_parser("discover", help="Inspect an already-ingested vault book.")
    discover.add_argument("--source-id", required=True)


    integrity = sub.add_parser("validate-book-source", help="Validate raw-source structure before graph promotion.")
    integrity.add_argument("--source-id", required=True)
    integrity.add_argument("--report-out", type=Path)
    sub.add_parser("init", help="Initialize Neo4j constraints and indexes.")
    sub.add_parser("check", help="Check Neo4j transactional API connectivity.")

    build = sub.add_parser("build-book", help="Build one book graph slice.")
    build.add_argument("--source-id", required=True)
    build.add_argument("--write-mode", choices=("dry_run", "upsert"))
    build.add_argument("--qdrant-crosswalk", type=Path)
    build.add_argument("--overlap-review", type=Path, help="Approved graph-overlap-review report required for upsert.")
    build.add_argument("--report-out", type=Path)


    crosswalk = sub.add_parser("crosswalk-book", help="Plan or create a verified Qdrant crosswalk.")
    crosswalk.add_argument("--source-id", required=True)
    crosswalk.add_argument("--memory-config", required=True, type=Path)
    crosswalk.add_argument("--data-dir", type=Path)
    crosswalk.add_argument("--chunk-bodies", required=True, type=Path)
    crosswalk.add_argument("--write-mode", choices=("dry_run", "upsert"), default="dry_run")
    crosswalk.add_argument("--crosswalk-out", type=Path)
    maintenance = sub.add_parser("maintenance", help="Generate graph maintenance findings.")

    policies = sub.add_parser("ingest-policies", help="Plan or upsert authoritative policy sources.")
    policies.add_argument("--policy-path", action="append", type=Path)
    policies.add_argument("--write-mode", choices=("dry_run", "upsert"), default="dry_run")
    policies.add_argument("--report-out", type=Path)

    review = sub.add_parser("review-book-overlap", help="Create a read-only concept-overlap review report.")
    review.add_argument("--source-id", required=True)
    review.add_argument("--memory-config", type=Path, help="Memory OS config used for Qdrant semantic review.")
    review.add_argument("--data-dir", type=Path)
    review.add_argument("--output", type=Path)

    maintenance.add_argument("--output", type=Path)
    maintenance.add_argument("--min-confidence", type=float, default=0.75)

    args = parser.parse_args(argv)
    try:
        config = GraphConfig.load(Path(args.config))
        if args.command == "discover":
            artifact = discover_book(config.vault_root, args.source_id)
            _print(
                {
                    "source_id": artifact.source_id,
                    "title": artifact.title,
                    "chunks": len(artifact.chunks),
                    "claims": len(artifact.claims),
                    "source_page": str(artifact.synthesis_path),
                    "raw_source": str(artifact.raw_path),
                    "retrieval_chunks": str(artifact.retrieval_chunks_path),
                }
            )
            return 0
        if args.command == "validate-book-source":
            result = validate_book_source(config, args.source_id)
            if args.report_out:
                args.report_out.parent.mkdir(parents=True, exist_ok=True)
                write_source_integrity_report(result, args.report_out)
            _print(result)
            return 0
        if args.command == "check":
            _print({"neo4j_reachable": Neo4jClient.from_config(config).health()})
            return 0
        if args.command == "init":
            _print({"schema_statements": initialize_schema(Neo4jClient.from_config(config))})
            return 0
        if args.command == "build-book":
            write_mode = args.write_mode or config.default_write_mode
            crosswalk = _load_crosswalk(args.qdrant_crosswalk)
            overlap_review_path = args.overlap_review
            client = Neo4jClient.from_config(config) if write_mode == "upsert" else None
            result = GraphBookBuilder(config).build(
                args.source_id,
                write_mode=write_mode,
                qdrant_crosswalk=crosswalk,
                overlap_review_path=overlap_review_path,
                client=client,
            )
            if args.report_out:
                args.report_out.parent.mkdir(parents=True, exist_ok=True)
                args.report_out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            _print({key: value for key, value in result.items() if key != "plan"})
            return 0
        if args.command == "review-book-overlap":
            artifact = discover_book(config.vault_root, args.source_id)
            app = (
                MemoryApp.from_config(config_path=args.memory_config, data_dir=args.data_dir)
                if args.memory_config
                else None
            )
            review = collect_overlap_review(
                concept_candidates(artifact.source_id, artifact.concepts),
                graph_client=Neo4jClient.from_config(config),
                memory_app=app,
                vault_root=config.vault_root,
            )
            output = args.output or config.reports_root / f"{args.source_id}-overlap-review.md"
            output = output.resolve()
            reports_root = config.reports_root.resolve()
            if output != reports_root and reports_root not in output.parents:
                raise ValueError("review output must stay under the graph reports directory")
            write_overlap_review_report(review, output)
            _print({
                "status": review["status"],
                "output_path": str(output),
                "candidate_digest": review["candidate_digest"],
                "counts": review["counts"],
                "review_warnings": review["review_warnings"],
                "auto_merged": False,
            })
            return 0
        if args.command == "maintenance":
            findings = collect_maintenance(Neo4jClient.from_config(config), min_confidence=args.min_confidence)
            output = args.output or config.reports_root / "graph-maintenance.md"
            _print({"output_path": str(write_maintenance_report(findings, output)), "counts": {key: len(value) for key, value in findings.items()}})
            return 0
        if args.command == "crosswalk-book":
            app = MemoryApp.from_config(config_path=args.memory_config, data_dir=args.data_dir)
            if args.write_mode == "upsert":
                app.init_storage()
            result = index_book_crosswalk(
                app, config, args.source_id, args.chunk_bodies, write_mode=args.write_mode
            )
            if args.write_mode == "upsert":
                output = args.crosswalk_out or config.reports_root / "crosswalks" / f"{args.source_id}.json"
                result["crosswalk_path"] = str(write_crosswalk(result, output))
            _print(result)
            return 0
        if args.command == "ingest-policies":
            client = Neo4jClient.from_config(config) if args.write_mode == "upsert" else None
            result = GraphPolicyBuilder(config).build(
                policy_paths=args.policy_path, write_mode=args.write_mode, client=client
            )
            if args.report_out:
                args.report_out.parent.mkdir(parents=True, exist_ok=True)
                args.report_out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            _print({key: value for key, value in result.items() if key != "plan"})
            return 0
    except (GraphConfigError, ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    return 2


def _load_crosswalk(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in raw.items()):
        raise ValueError("Qdrant crosswalk must be a JSON object mapping source chunk IDs to point IDs.")
    return raw


def _print(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    raise SystemExit(main())
