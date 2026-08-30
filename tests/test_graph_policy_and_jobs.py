import json
import os
from pathlib import Path

import pytest

from hermes_memory_os.graph.span_manifest import (
    inventory_span_manifest_candidates,
    proposed_span_manifest,
    write_proposed_span_manifest,
)

VAULT = Path("/wiki/vault")
POLICY = VAULT / "04_SYSTEM/policies/HERMES_KNOWLEDGE_GRAPH_POLICY.md"
ROUTER = VAULT / "04_SYSTEM/policies/POLICY_ROUTER.md"
BOOK_POLICY = VAULT / "04_SYSTEM/policies/book-and-longform-knowledge-ingestion-policy.md"
SOURCE_INTEGRITY_POLICY = VAULT / "04_SYSTEM/policies/HERMES_SOURCE_INTEGRITY_POLICY.md"
ENTITY_RESOLUTION_POLICY = VAULT / "04_SYSTEM/policies/entity-resolution-policy.md"
ROOT = Path(__file__).resolve().parents[1]
JOB = ROOT / "cron/graph-maintenance.job.json"
SCRIPT = ROOT / "scripts/graph_maintenance_cron.sh"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.skipif(not POLICY.is_file(), reason="vault policy not mounted")
def test_graph_policy_requires_evidence_and_dry_run_review():
    text = POLICY.read_text(encoding="utf-8")
    for required in (
        "Evidence",
        "Provenance",
        "Confidence",
        "Source attribution",
        "reviewed retrieval chunks",
        "span manifest",
        "raw-source SHA-256",
        "Dry-run review MUST precede",
        "MUST NEVER rewrite policy files",
        "ready_for_span_review",
        "review artifacts, never autonomous corrections",
    ):
        assert required in text


@pytest.mark.skipif(not ROUTER.is_file(), reason="vault router not mounted")
def test_policy_router_routes_graph_triggers():
    text = ROUTER.read_text(encoding="utf-8")
    assert "HERMES_KNOWLEDGE_GRAPH_POLICY.md" in text
    assert "Graph claim, relationship, book promotion, or span manifest" in text
    assert "Graph maintenance report" in text
    assert "Source completeness, extraction quality, span verification, or source repair" in text
    assert "HERMES_SOURCE_INTEGRITY_POLICY.md" in text
    assert "|| Graph claim" not in text


@pytest.mark.skipif(not BOOK_POLICY.is_file(), reason="vault book policy not mounted")
def test_book_policy_cross_references_graph_policy():
    text = BOOK_POLICY.read_text(encoding="utf-8")
    assert "HERMES_KNOWLEDGE_GRAPH_POLICY.md" in text
    assert "does not replace this Vault graph" in text
    assert "HERMES_SOURCE_INTEGRITY_POLICY.md" in text
    assert "source-integrity preflight" in text




@pytest.mark.skipif(not SOURCE_INTEGRITY_POLICY.is_file(), reason="vault policy not mounted")
def test_source_integrity_policy_blocks_unverified_source_writes():
    text = SOURCE_INTEGRITY_POLICY.read_text(encoding="utf-8")
    for required in (
        "SHA-256",
        "ready_for_span_review",
        "blocked",
        "MUST NOT receive new Qdrant points",
        "Never overwrite or silently edit",
        "Book-ingestion jobs MUST invoke the preflight",
    ):
        assert required in text


@pytest.mark.skipif(not ENTITY_RESOLUTION_POLICY.is_file(), reason="vault policy not mounted")
def test_entity_resolution_policy_requires_read_only_overlap_review():
    text = ENTITY_RESOLUTION_POLICY.read_text(encoding="utf-8")
    for required in (
        "Qdrant",
        "same_concept",
        "broader_or_narrower",
        "related_but_distinct",
        "uncertain",
        "MUST NOT automatically merge",
        "matching overlap-review report",
    ):
        assert required in text
    assert "entity-resolution-policy.md" in ROUTER.read_text(encoding="utf-8")


def test_maintenance_job_template_is_read_only_after_evening_cos():
    job = json.loads(JOB.read_text(encoding="utf-8"))
    assert job["enabled"] is False
    assert job["schedule"] == "30 21 * * *"
    assert job["no_agent"] is True
    assert job["deliver"] == "local"
    assert job["script"] == "graph_maintenance_cron.sh"
    assert job["placement"]["after_schedule"] == "30 20 * * *"
    command = job["command"]
    assert "maintenance" in command
    assert "build-book" not in command
    assert "upsert" not in command
    assert str(job["constraints"]["forbidden"]).count("build-book") == 1
    assert job["constraints"]["log_secrets"] is False
    script = SCRIPT.read_text(encoding="utf-8")
    assert "build-book" in script or "Never builds books" in script
    assert "Never print env dumps" in script or "Never log" in script or "password" in script
    assert "upsert" in script
    assert "maintenance" in script


def test_maintenance_script_dry_run_prints_command_only(tmp_path, monkeypatch):
    monkeypatch.setenv("GRAPH_MAINTENANCE_DRY_RUN", "1")
    monkeypatch.setenv("GRAPH_MAINTENANCE_OUTPUT", str(ROOT / "graph/reports/graph-maintenance.md"))
    import subprocess

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "GRAPH_MAINTENANCE_DRY_RUN": "1"},
    )
    assert result.returncode == 0
    assert "dry_run hermes-graph" in result.stdout
    assert "maintenance" in result.stdout
    assert "build-book" not in result.stdout
    assert "PASSWORD" not in result.stdout
    assert "PASSWORD" not in result.stderr


def test_span_inventory_skips_raw_only_and_emits_unverified_chunks(tmp_path):
    vault = tmp_path / "vault"
    _write(
        vault / "03_RESOURCES/books/raw/raw-only/manifest.md",
        """---
source_id: book-raw-only
source_path: 03_RESOURCES/books/raw/raw-only.md
content_hash: deadbeef
---
""",
    )
    _write(vault / "03_RESOURCES/books/raw/raw-only.md", "raw only")
    source_id = "book-finite-infinite-games-undated"
    _write(
        vault / "03_RESOURCES/books/raw/fig/manifest.md",
        f"""---
source_id: {source_id}
source_path: 03_RESOURCES/books/raw/fig.md
content_hash: abc123
---
""",
    )
    _write(vault / "03_RESOURCES/books/raw/fig.md", "fig")
    _write(
        vault / "02_WIKI/sources/books/fig.md",
        f"""---
source_id: {source_id}
title: Finite and Infinite Games
---
""",
    )
    fence = chr(96) * 3
    chunks = [
        {
            "chunk_id": "chunk-one",
            "chunk_index": 0,
            "section": "1-25",
            "page_start": 1,
            "page_end": 26,
        }
    ]
    _write(
        vault / f"06_GENERATED/source-analysis/{source_id}/retrieval-chunks.md",
        fence + "json\n" + json.dumps(chunks) + "\n" + fence + "\n",
    )

    found = inventory_span_manifest_candidates(vault)
    assert [item["source_id"] for item in found] == [source_id]
    payload = proposed_span_manifest(found[0])
    assert payload["status"] == "proposed_review"
    assert payload["write_mode"] == "dry_run"
    assert payload["raw_source_sha256"] == "abc123"
    assert payload["chunks"][0]["chunk_id"] == "chunk-one"
    assert payload["chunks"][0]["span"]["start"] == "section:1"
    assert payload["indexes_qdrant"] is False
    assert payload["upserts_neo4j"] is False
    out = write_proposed_span_manifest(payload, tmp_path / "reports" / "proposed.json")
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["qdrant_crosswalk"] == "missing"
