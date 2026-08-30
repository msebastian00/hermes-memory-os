from pathlib import Path

import pytest

from hermes_memory_os.graph.builder import GraphBookBuilder
from hermes_memory_os.graph.overlap import (
    candidate_digest,
    collect_overlap_review,
    concept_candidates,
    validate_approved_overlap_review,
    write_overlap_review_report,
)

from test_graph import _FakeNeo4j, _book_config


class _SemanticBackend:
    def __init__(self):
        self.calls = []

    def search(self, query, *, limit, source_types=None):
        self.calls.append((query, limit, source_types))
        return [
            {
                "id": "source-chunk-1",
                "kind": "source_chunk",
                "source_id": "book-existing",
                "citation": "Existing source, section 2",
                "qdrant_point_id": "point-1",
                "semantic_score": 0.91,
            }
        ]


class _App:
    class Retriever:
        def __init__(self):
            self.semantic_backend = _SemanticBackend()

    def __init__(self):
        self.retriever = self.Retriever()


class _Graph:
    def __init__(self):
        self.calls = []

    def execute(self, query, parameters=None):
        self.calls.append((query, parameters))
        return [
            {
                "id": "entity:concept:state-management",
                "canonical_name": "State Management",
                "entity_type": "concept",
                "aliases": ["emotional state management"],
                "home_vault_path": "02_WIKI/concepts/state-management.md",
                "confidence": 0.95,
            }
        ]


def test_overlap_review_is_qdrant_first_and_never_mutates(tmp_path):
    app = _App()
    graph = _Graph()
    vault_root = tmp_path / "vault"
    concept_path = vault_root / "02_WIKI" / "concepts" / "state-management.md"
    concept_path.parent.mkdir(parents=True)
    concept_path.write_text("---\ntype: concept\ntitle: State Management\naliases:\n  - emotional state management\n---\n", encoding="utf-8")
    candidates = concept_candidates("book-tony", ["Emotional State Management"])

    review = collect_overlap_review(candidates, graph_client=graph, memory_app=app, vault_root=vault_root)

    item = review["candidates"][0]
    assert app.retriever.semantic_backend.calls == [("Emotional State Management", 5, None)]
    assert graph.calls
    assert item["status"] == "review_required"
    assert item["graph_matches"][0]["match_kind"] == "exact"
    assert item["vault_matches"][0]["match_kind"] == "exact"
    assert review["review_complete"] is True
    assert item["semantic_hits"][0]["qdrant_point_id"] == "point-1"
    assert review["auto_merged"] is False
    assert review["memory_os_written"] is False
    assert review["qdrant_written"] is False
    assert review["neo4j_written"] is False


def test_overlap_report_requires_explicit_matching_human_approval(tmp_path):
    candidates = concept_candidates("book-one", ["Finite Game"])
    review = collect_overlap_review(candidates, graph_client=None, memory_app=None)
    output = write_overlap_review_report(review, tmp_path / "review.md")

    with pytest.raises(ValueError, match="incomplete"):
        validate_approved_overlap_review(output, source_id="book-one", candidates=candidates)

    text = output.read_text(encoding="utf-8")
    text = text.replace("status: incomplete", "status: approved").replace("status: pending_human_review", "status: approved")
    text = text.replace("review_complete: false", "review_complete: true")
    text = text.replace("approved_by: null", "approved_by: Mike")
    text = text.replace("approved_at: null", "approved_at: 2026-08-30T00:00:00Z")
    output.write_text(text, encoding="utf-8")
    validate_approved_overlap_review(output, source_id="book-one", candidates=candidates)

    other = concept_candidates("book-one", ["Infinite Game"])
    assert candidate_digest(candidates) != candidate_digest(other)
    with pytest.raises(ValueError, match="does not match"):
        validate_approved_overlap_review(output, source_id="book-one", candidates=other)


def test_book_upsert_requires_approved_overlap_review(tmp_path):
    config = _book_config(tmp_path)
    builder = GraphBookBuilder(config)

    with pytest.raises(ValueError, match="overlap-review"):
        builder.build("book-one", write_mode="upsert", client=_FakeNeo4j())

    candidates = concept_candidates("book-one", ["Finite game", "Infinite game"])
    review = collect_overlap_review(candidates, graph_client=None, memory_app=None)
    review_path = write_overlap_review_report(review, config.reports_root / "book-one-overlap-review.md")
    text = review_path.read_text(encoding="utf-8")
    text = text.replace("status: incomplete", "status: approved").replace("status: pending_human_review", "status: approved")
    text = text.replace("review_complete: false", "review_complete: true")
    text = text.replace("approved_by: null", "approved_by: Mike")
    text = text.replace("approved_at: null", "approved_at: 2026-08-30T00:00:00Z")
    review_path.write_text(text, encoding="utf-8")

    result = builder.build(
        "book-one",
        write_mode="upsert",
        overlap_review_path=review_path,
        client=_FakeNeo4j(),
    )
    assert result["status"] == "upserted"
