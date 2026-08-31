import json

import pytest
from pathlib import Path

from hermes_memory_os.graph.builder import BookDiscoveryError, GraphBookBuilder
from hermes_memory_os.graph.config import GraphConfig
from hermes_memory_os.graph.crosswalk import CrosswalkError, build_crosswalk_plan
from hermes_memory_os.graph.source_integrity import validate_book_source


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _config(tmp_path: Path, raw: str) -> GraphConfig:
    vault = tmp_path / "vault"
    _write(vault / "03_RESOURCES/books/raw/book-one.md", raw)
    _write(
        vault / "03_RESOURCES/books/raw/book-one/manifest.md",
        f"---\nsource_id: book-one\ntitle: Book One\nsource_path: 03_RESOURCES/books/raw/book-one.md\ncontent_hash: {'x' * 64}\n---\n",
    )
    _write(
        vault / "02_WIKI/sources/books/book-one.md",
        "---\nsource_id: book-one\ntitle: Book One\n---\n## Claims, Evidence, and Limitations\n\n### Claims\n1. A reviewed claim.\n",
    )
    chunks = [
        {"chunk_id": "one", "chunk_index": 0, "section": "1-2"},
        {"chunk_id": "two", "chunk_index": 1, "section": "3-4"},
    ]
    fence = chr(96) * 3
    _write(
        vault / "06_GENERATED/source-analysis/book-one/retrieval-chunks.md",
        fence + "json\n" + json.dumps(chunks) + "\n" + fence + "\n",
    )
    config = tmp_path / "graph.yml"
    _write(config, "paths:\n  vault_root: vault\ngraph:\n  default_write_mode: dry_run\n")
    return GraphConfig.load(config)


def test_source_integrity_blocks_missing_required_section_markers(tmp_path):
    config = _config(tmp_path, "# 1\nfirst\n\n# 3\nthird\n\n# 4\nfourth\n")

    result = validate_book_source(config, "book-one")

    assert result["status"] == "blocked"
    assert result["safe_for_qdrant_crosswalk"] is False
    report = GraphBookBuilder(config).build("book-one", write_mode="dry_run")
    assert "source_integrity_blocked:raw_source_hash_mismatch,section_markers_incomplete" in report["warnings"]
    assert result["missing_sections"] == [2]
    assert "raw_source_hash_mismatch" in result["problems"]


def test_source_integrity_allows_review_when_structural_markers_are_present(tmp_path):
    config = _config(tmp_path, "# 1\nfirst\n\n# 2\nsecond\n\n# 3\nthird\n\n# 4\nfourth\n")
    raw_path = tmp_path / "vault/03_RESOURCES/books/raw/book-one.md"
    manifest = tmp_path / "vault/03_RESOURCES/books/raw/book-one/manifest.md"
    digest = __import__("hashlib").sha256(raw_path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    manifest.write_text(manifest.read_text(encoding="utf-8").replace("x" * 64, digest), encoding="utf-8")

    result = validate_book_source(config, "book-one")

    assert result["status"] == "ready_for_span_review"
    assert result["safe_for_qdrant_crosswalk"] is True
    assert result["missing_sections"] == []


def test_source_integrity_blocks_graph_upsert_and_crosswalk(tmp_path):
    config = _config(tmp_path, "# 1\nfirst\n\n# 3\nthird\n\n# 4\nfourth\n")

    with pytest.raises(BookDiscoveryError, match="source-integrity"):
        GraphBookBuilder(config).build("book-one", write_mode="upsert", client=object())
    with pytest.raises(CrosswalkError, match="source-integrity"):
        build_crosswalk_plan(config, "book-one", tmp_path / "not-read-when-invalid.json")


def test_unreliable_markers_do_not_override_missing_sections(tmp_path):
    config = _config(tmp_path, "# 1\nfirst\n\n# 3\nthird\n\n# 4\nfourth\n")
    raw_path = tmp_path / "vault/03_RESOURCES/books/raw/book-one.md"
    manifest = tmp_path / "vault/03_RESOURCES/books/raw/book-one/manifest.md"
    digest = __import__("hashlib").sha256(raw_path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("x" * 64, digest)
        + "section_marker_reliability: unreliable\n",
        encoding="utf-8",
    )
    chunks_path = tmp_path / "vault/06_GENERATED/source-analysis/book-one/retrieval-chunks.md"
    chunks_path.write_text(
        chr(96) * 3 + "json\n"
        + json.dumps(
            [
                {"chunk_id": "one", "chunk_index": 0, "section": "1-2", "span_start": 0, "span_end": len(raw_path.read_text(encoding="utf-8"))},
                {"chunk_id": "two", "chunk_index": 1, "section": "3-4", "span_start": len(raw_path.read_text(encoding="utf-8")), "span_end": len(raw_path.read_text(encoding="utf-8"))},
            ]
        )
        + "\n" + chr(96) * 3 + "\n",
        encoding="utf-8",
    )

    result = validate_book_source(config, "book-one")

    assert result["span_coverage_complete"] is True
    assert result["section_markers_unreliable"] is True
    assert result["status"] == "blocked"
    assert result["safe_for_qdrant_crosswalk"] is False
    assert result["problems"] == ["section_markers_incomplete"]
    assert "section_marker_reliability_does_not_override_completeness" in result["warnings"]


def test_deferred_manifest_status_blocks_even_when_markers_are_complete(tmp_path):
    config = _config(tmp_path, "# 1\nfirst\n\n# 2\nsecond\n\n# 3\nthird\n\n# 4\nfourth\n")
    raw_path = tmp_path / "vault/03_RESOURCES/books/raw/book-one.md"
    manifest = tmp_path / "vault/03_RESOURCES/books/raw/book-one/manifest.md"
    digest = __import__("hashlib").sha256(raw_path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "content_hash: " + "x" * 64,
            "content_hash: " + digest + "\nstatus: deferred",
        ),
        encoding="utf-8",
    )

    result = validate_book_source(config, "book-one")

    assert result["status"] == "blocked"
    assert result["manifest_status"] == "deferred"
    assert result["problems"] == ["manifest_source_not_ready"]
