from pathlib import Path

from hermes_memory_os.graph.builder import GraphBookBuilder
from hermes_memory_os.graph.overlap import (
    candidate_digest,
    collect_overlap_review,
    concept_candidates,
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
    assert item["status"] == "exact_identity_reused"
    assert item["graph_matches"][0]["match_kind"] == "exact"
    assert item["vault_matches"][0]["match_kind"] == "exact"
    assert review["review_complete"] is True
    assert item["semantic_hits"][0]["qdrant_point_id"] == "point-1"
    assert review["auto_merged"] is False
    assert review["memory_os_written"] is False
    assert review["qdrant_written"] is False
    assert review["neo4j_written"] is False


def test_overlap_report_is_evidence_only_and_has_stable_candidate_digest(tmp_path):
    candidates = concept_candidates("book-one", ["Finite Game"])
    review = collect_overlap_review(candidates, graph_client=None, memory_app=None)
    output = write_overlap_review_report(review, tmp_path / "review.md")

    text = output.read_text(encoding="utf-8")
    assert "automatic-report-only" in text
    assert "approved_by" not in text
    assert review["status"] == "incomplete"

    other = concept_candidates("book-one", ["Infinite Game"])
    assert candidate_digest(candidates) != candidate_digest(other)


def test_book_upsert_does_not_require_overlap_approval(tmp_path):
    config = _book_config(tmp_path)
    builder = GraphBookBuilder(config)
    result = builder.build("book-one", write_mode="upsert", client=_FakeNeo4j())
    assert result["status"] == "upserted"
