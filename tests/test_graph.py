import hashlib
import json
from pathlib import Path

from hermes_memory_os.graph.builder import GraphBookBuilder, discover_book
from hermes_memory_os.graph.artifact_prep import prepare_book_artifacts
from hermes_memory_os.graph.config import GraphConfig
from hermes_memory_os.graph.source_integrity import validate_book_source
from hermes_memory_os.graph.maintenance import collect_maintenance, write_maintenance_report
from hermes_memory_os.graph.overlap import collect_overlap_review, concept_candidates, write_overlap_review_report
from hermes_memory_os.graph.retrieval import GraphRetrievalAdapter
from hermes_memory_os.graph.schema import SCHEMA_STATEMENTS, initialize_schema


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _book_config(tmp_path: Path) -> GraphConfig:
    vault = tmp_path / "vault"
    _write(
        vault / "03_RESOURCES/books/raw/book-one/manifest.md",
        """---
source_id: book-one
title: Book One
authors:
  - Author One
content_hash: abc123
source_path: 03_RESOURCES/books/raw/book-one.md
---
""",
    )
    raw_text = "\n".join(f"# {section}\nSection {section}" for section in range(1, 11)) + "\n"
    raw_path = vault / "03_RESOURCES/books/raw/book-one.md"
    _write(raw_path, raw_text)
    manifest_path = vault / "03_RESOURCES/books/raw/book-one/manifest.md"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(
            "abc123", hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        ),
        encoding="utf-8",
    )
    _write(
        vault / "02_WIKI/sources/books/book-one.md",
        """---
source_id: book-one
title: Book One
authors:
  - Author One
key_concepts:
  - Finite game
  - Infinite game
---
## Claims, Evidence, and Limitations

### Claims
1. There are two kinds of games: finite and infinite.
2. Infinite games continue play.
""",
    )
    chunks = [
        {
            "chunk_id": "chunk-one",
            "source_id": "book-one",
            "source_type": "book",
            "title": "Book One",
            "section": "1-10",
            "chunk_index": 0,
            "page_start": 1,
            "page_end": 10,
        }
    ]
    fence = chr(96) * 3
    _write(
        vault / "06_GENERATED/source-analysis/book-one/retrieval-chunks.md",
        fence + "json\n" + json.dumps(chunks) + "\n" + fence + "\n",
    )
    config_path = tmp_path / "graph.yml"
    _write(
        config_path,
        """paths:
  vault_root: vault
graph:
  default_write_mode: dry_run
  review_report_path: reports
""",
    )
    return GraphConfig.load(config_path)


class _FakeNeo4j:
    def __init__(self):
        self.statements = []
        self.nodes = {}
        self.relationships = {}

    def execute(self, statement, parameters=None):
        self.statements.append((statement, parameters))
        return []

    def upsert(self, nodes, relationships):
        self.nodes.update({node["id"]: node for node in nodes})
        self.relationships.update({relation["id"]: relation for relation in relationships})
        return {"nodes": len(nodes), "relationships": len(relationships)}


def test_schema_initialization_is_idempotent():
    client = _FakeNeo4j()

    assert initialize_schema(client) == len(SCHEMA_STATEMENTS)
    assert initialize_schema(client) == len(SCHEMA_STATEMENTS)
    assert len(client.statements) == len(SCHEMA_STATEMENTS) * 2


def test_book_discovery_and_dry_run_are_evidence_backed(tmp_path):
    config = _book_config(tmp_path)
    artifact = discover_book(config.vault_root, "book-one")
    report = GraphBookBuilder(config).build("book-one", write_mode="dry_run")

    assert artifact.title == "Book One"
    assert len(artifact.chunks) == 1
    assert report["status"] == "planned"
    assert report["source_integrity"]["status"] == "ready_for_span_review"
    assert report["stats"]["warnings"] == 1

    labels = {node["label"] for node in report["plan"]["nodes"]}
    assert {"Source", "Document", "Chunk", "Entity", "Claim", "Evidence"} <= labels
    assert all(relation["properties"]["evidence_id"] for relation in report["plan"]["relationships"])
    assert any(node["properties"]["qdrant_point_id"] is None for node in report["plan"]["nodes"] if node["label"] == "Chunk")

def test_book_discovery_accepts_legacy_manifest_identity_and_source_path(tmp_path):
    config = _book_config(tmp_path)
    vault = config.vault_root
    manifest = vault / "03_RESOURCES/books/raw/book-one/manifest.md"
    raw_text = (vault / "03_RESOURCES/books/raw/book-one.md").read_text(encoding="utf-8")
    manifest.write_text(
        "\n".join(
            [
                "id: book-one",
                "title: Book One",
                "author: Author One",
                f"content_hash: {hashlib.sha256(raw_text.encode('utf-8')).hexdigest()}",
                "original_path: 03_RESOURCES/books/raw/book-one.md",
                "",
                "# Legacy manifest",
            ]
        ),
        encoding="utf-8",
    )

    artifact = discover_book(vault, "book-one")
    assert artifact.raw_relative_path == "03_RESOURCES/books/raw/book-one.md"
    assert artifact.authors == ("Author One",)




def test_book_discovery_accepts_structured_claim_table(tmp_path):
    config = _book_config(tmp_path)
    source = config.vault_root / "02_WIKI/sources/books/book-one.md"
    source.write_text(
        """---
source_id: book-one
title: Book One
---
## Claims, evidence, and limitations

| Claim | Claim basis | Evidence supplied |
|---|---|---|
| A source claim with evidence | author claim | chapter 1 |
""",
        encoding="utf-8",
    )

    artifact = discover_book(config.vault_root, "book-one")

    assert artifact.claims == ("A source claim with evidence",)


def test_artifact_preparation_writes_exact_spans_idempotently(tmp_path):
    config = _book_config(tmp_path)
    _write(config.vault_root / "05_QUEUE/book-ingestion/incoming/book-one.md", "---\nsource_id: book-one\n---\n")
    chunks_path = config.vault_root / "06_GENERATED/source-analysis/book-one/retrieval-chunks.md"
    chunks_path.unlink()

    planned = prepare_book_artifacts(config, "book-one", write_mode="dry_run", max_chunk_chars=1000)
    assert planned["status"] == "planned"
    assert not chunks_path.exists()

    prepared = prepare_book_artifacts(config, "book-one", write_mode="upsert", max_chunk_chars=1000)
    again = prepare_book_artifacts(config, "book-one", write_mode="upsert", max_chunk_chars=1000)
    artifact = discover_book(config.vault_root, "book-one")
    raw = (config.vault_root / "03_RESOURCES/books/raw/book-one.md").read_text(encoding="utf-8")
    bodies = json.loads((chunks_path.parent / "chunk-bodies.json").read_text(encoding="utf-8"))

    assert prepared["chunk_count"] == again["chunk_count"] == len(artifact.chunks)
    assert all(raw[row["span_start"]:row["span_end"]] == row["text"] for row in bodies["chunks"])
    assert all(len(row["text"]) <= 1000 for row in bodies["chunks"])


def test_book_upsert_uses_stable_ids_without_duplicates(tmp_path):
    config = _book_config(tmp_path)
    client = _FakeNeo4j()
    builder = GraphBookBuilder(config)

    first = builder.build("book-one", write_mode="upsert", client=client)
    first_node_ids = set(client.nodes)
    first_relationship_ids = set(client.relationships)
    second = builder.build("book-one", write_mode="upsert", client=client)

    assert first["status"] == second["status"] == "upserted"
    assert set(client.nodes) == first_node_ids
    assert set(client.relationships) == first_relationship_ids


def test_retrieval_uses_qdrant_hits_before_graph_expansion():
    class Store:
        def get_source_chunk(self, _):
            return {"id": "memory-chunk", "qdrant_point_id": "point-1"}

    class Semantic:
        def __init__(self):
            self.calls = 0

        def search(self, query, *, limit):
            self.calls += 1
            return [{"id": "memory-chunk", "kind": "source_chunk", "semantic_score": 0.9, "text": query}]

    class Retriever:
        def __init__(self):
            self.semantic_backend = Semantic()
            self.fallback_called = False

        def search(self, *args, **kwargs):
            self.fallback_called = True
            return []

    class App:
        def __init__(self):
            self.store = Store()
            self.retriever = Retriever()

    class Graph:
        def expand_context(self, chunk_ids, point_ids):
            assert chunk_ids == ["memory-chunk"]
            assert point_ids == ["point-1"]
            return [
                {
                    "chunk_id": "memory-chunk",
                    "qdrant_point_id": "point-1",
                    "claim_id": "claim-1",
                    "claim_text": "A supported claim.",
                    "claim_confidence": 0.8,
                    "claim_status": "active",
                    "evidence_id": "evidence-1",
                    "evidence_quote": "A short quote.",
                    "entity_name": "Book One",
                }
            ]

    app = App()
    packet = GraphRetrievalAdapter(app, Graph()).retrieve("supported claim")

    assert app.retriever.semantic_backend.calls == 1
    assert app.retriever.fallback_called is False
    assert packet["claims"][0]["id"] == "claim-1"
    assert packet["provenance"][0]["qdrant_point_id"] == "point-1"
    assert packet["provenance"][0]["quote"] == "A short quote."
    assert packet["provenance"][0]["confidence"] == 0.8
    assert packet["claims"][0]["claim_basis"] == "author-framework"


def test_retrieval_excludes_low_confidence_and_unsupported_graph_facts():
    class Store:
        def get_source_chunk(self, _):
            return {"id": "memory-chunk", "qdrant_point_id": "point-1"}

    class Semantic:
        def search(self, query, *, limit):
            return [{"id": "memory-chunk", "kind": "source_chunk", "semantic_score": 0.9, "text": query}]

    class Retriever:
        def __init__(self):
            self.semantic_backend = Semantic()

        def search(self, *args, **kwargs):
            return []

    class App:
        def __init__(self):
            self.store = Store()
            self.retriever = Retriever()

    class Graph:
        def expand_context(self, chunk_ids, point_ids):
            return [
                {
                    "chunk_id": "memory-chunk",
                    "qdrant_point_id": "point-1",
                    "claim_id": "low",
                    "claim_text": "Weak.",
                    "claim_confidence": 0.1,
                    "claim_status": "active",
                    "evidence_id": "e-low",
                    "evidence_quote": "weak",
                },
                {
                    "chunk_id": "memory-chunk",
                    "qdrant_point_id": "point-1",
                    "claim_id": "orphan",
                    "claim_text": "No evidence.",
                    "claim_confidence": 0.9,
                    "claim_status": "active",
                    "evidence_id": None,
                    "evidence_quote": None,
                },
            ]

    packet = GraphRetrievalAdapter(App(), Graph()).retrieve("weak claim")
    assert packet["claims"] == []
    assert packet["graph_hits"] == []
    assert any("excluded_unsupported_or_low_confidence" in item for item in packet["review_warnings"])



def test_retrieval_ranks_document_expansion_claims_by_query_relevance():
    class Store:
        def get_source_chunk(self, _):
            return {"id": "memory-chunk", "qdrant_point_id": "point-1"}

    class Semantic:
        def search(self, query, *, limit):
            return [{"id": "memory-chunk", "kind": "source_chunk", "semantic_score": 0.9, "text": query}]

    class Retriever:
        semantic_backend = Semantic()

        def search(self, *args, **kwargs):
            return []

    class App:
        store = Store()
        retriever = Retriever()

    class Graph:
        def expand_context(self, *_args):
            return [
                {"claim_id": "generic", "claim_text": "A generic source claim.", "claim_confidence": 0.78, "claim_status": "active", "evidence_id": "e1", "evidence_quote": "generic"},
                {"claim_id": "life", "claim_text": "Life design is an iterative practice.", "claim_confidence": 0.78, "claim_status": "active", "evidence_id": "e2", "evidence_quote": "life"},
            ]

    packet = GraphRetrievalAdapter(App(), Graph()).retrieve("life design")
    assert [claim["id"] for claim in packet["claims"]] == ["life", "generic"]


def test_retrieval_skips_graph_when_client_is_missing():
    class Retriever:
        semantic_backend = None

        def search(self, query, *, limit):
            return [{"id": "mem-1", "kind": "memory", "text": query}]

    class App:
        store = None
        retriever = Retriever()

    packet = GraphRetrievalAdapter(App(), None).retrieve("memory only")
    assert packet["graph_hits"] == []
    assert packet["semantic_hits"][0]["id"] == "mem-1"


def test_maintenance_crosswalk_query_is_limited_to_book_sources():
    class Client:
        def __init__(self):
            self.queries = []

        def execute(self, query, parameters=None):
            self.queries.append(query)
            return []

    client = Client()
    collect_maintenance(client)

    crosswalk_query = next(query for query in client.queries if "qdrant_point_id" in query)
    assert "source.source_type = \"book\"" in crosswalk_query


def test_maintenance_report_includes_all_review_categories(tmp_path):
    output = write_maintenance_report(
        {
            "duplicate_entities": [{"summary": "Duplicate"}],
            "claims_without_evidence": [],
            "low_confidence_relationships": [],
            "policy_conflicts": [],
            "missing_qdrant_crosswalk": [{"source_chunk_id": "chunk-one"}],
        },
        tmp_path / "report.md",
    )

    text = output.read_text(encoding="utf-8")
    assert "Duplicate Entities" in text
    assert "Claims Without Evidence" in text
    assert "Missing Qdrant Crosswalk" in text


def test_graph_builder_handles_nested_raw_book_paths(tmp_path):
    config = _book_config(tmp_path)
    vault = config.vault_root
    original = vault / "03_RESOURCES/books/raw/book-one.md"
    nested = vault / "03_RESOURCES/books/raw/book-one/content/book-one.md"
    raw_text = original.read_text(encoding="utf-8")
    _write(nested, raw_text)
    original.unlink()
    manifest = vault / "03_RESOURCES/books/raw/book-one/manifest.md"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "03_RESOURCES/books/raw/book-one.md",
            "03_RESOURCES/books/raw/book-one/content/book-one.md",
        ),
        encoding="utf-8",
    )

    report = GraphBookBuilder(config).build("book-one", write_mode="dry_run")

    evidence = [node["properties"] for node in report["plan"]["nodes"] if node["label"] == "Evidence"]
    assert evidence
    assert all(not item["source_locator"].startswith("..") for item in evidence)
    assert any(item["source_locator"].startswith("06_GENERATED/") for item in evidence)


def test_source_integrity_uses_immutable_manifest_section_requirement(tmp_path):
    config = _book_config(tmp_path)
    vault = config.vault_root
    raw_path = vault / "03_RESOURCES/books/raw/book-one.md"
    complete = raw_path.read_text(encoding="utf-8")
    incomplete = complete.replace("# 4\nSection 4\n", "")
    raw_path.write_text(incomplete, encoding="utf-8")
    manifest = vault / "03_RESOURCES/books/raw/book-one/manifest.md"
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        .replace(hashlib.sha256(complete.encode("utf-8")).hexdigest(), hashlib.sha256(incomplete.encode("utf-8")).hexdigest())
        + "\n## Completeness\nSource text contains all 10 numbered sections.\n",
        encoding="utf-8",
    )
    _write(vault / "05_QUEUE/book-ingestion/incoming/book-one.md", "---\nsource_id: book-one\n---\n")

    prepare_book_artifacts(config, "book-one", write_mode="upsert", max_chunk_chars=1000)
    integrity = validate_book_source(config, "book-one")

    assert integrity["status"] == "blocked"
    assert integrity["missing_sections"] == [4]


def test_book_discovery_accepts_evidence_backed_claim_bullets(tmp_path):
    config = _book_config(tmp_path)
    source = config.vault_root / "02_WIKI/sources/books/book-one.md"
    source.write_text(
        """---
source_id: book-one
title: Book One
---
### Evidence-Backed Claims
- A supported source claim with a cited basis.
""",
        encoding="utf-8",
    )

    artifact = discover_book(config.vault_root, "book-one")

    assert artifact.claims == ("A supported source claim with a cited basis.",)
