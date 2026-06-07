import json

from hermes_memory_os.db.store import MemoryStore
from hermes_memory_os.retrieval.retriever import Retriever
from hermes_memory_os.semantic import SemanticSearchBackend


class StaticSemanticBackend:
    def __init__(self, results):
        self.results = results

    def search(self, query: str, *, limit: int, source_types: list[str] | None = None):
        return self.results[:limit]


class FailingSemanticBackend:
    def search(self, query: str, *, limit: int, source_types: list[str] | None = None):
        raise RuntimeError("qdrant unavailable")


class FakeEmbedder:
    def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class SearchOnlyQdrant:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def search(self, collection, vector, limit=8, *, query_filter=None):
        self.calls.append(
            {
                "collection": collection,
                "vector": vector,
                "limit": limit,
                "query_filter": query_filter,
            }
        )
        return [{"score": 0.77, "payload": self.payload}]


def _config(min_score: float = 0.1) -> dict:
    return {
        "max_injected": 8,
        "min_final_score": min_score,
        "weights": {
            "semantic": 0.5,
            "keyword": 0.5,
            "entity": 0.0,
            "scope": 0.0,
            "recency": 0.0,
            "trust": 0.0,
        },
    }


def test_hybrid_retrieval_merges_semantic_and_keyword_duplicates(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    store.init()
    memory_id = store.add_memory(
        memory_type="fact",
        scope="system",
        title="Durable Recall",
        summary="Hermes durable recall merges duplicate results.",
        canonical_text="Hermes durable recall merges duplicate results.",
    )
    semantic = store.get_memory_result(memory_id)
    semantic["semantic_score"] = 0.9

    retriever = Retriever(store, _config(), semantic_backend=StaticSemanticBackend([semantic]))
    results = retriever.search("durable recall")

    assert len([item for item in results if item["id"] == memory_id]) == 1
    result = results[0]
    assert result["semantic_score"] == 0.9
    assert result["keyword_score"] > 0
    assert result["retrieval_sources"] == ["keyword", "semantic"]


def test_semantic_only_source_chunk_result_is_ranked(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    store.init()
    source_id, _ = store.upsert_source_file(
        source_path="/books/memory.txt",
        source_type="book",
        title="Memory Book",
        content="Chapter 1\n\nSemantic-only source chunk.",
        chunks=[{"chapter": "Chapter 1", "text": "Semantic-only source chunk."}],
    )
    with store.connection() as conn:
        chunk_id = conn.execute(
            "SELECT id FROM source_chunks WHERE source_id=?",
            (source_id,),
        ).fetchone()["id"]
    semantic = store.get_source_chunk_result(chunk_id)
    semantic["semantic_score"] = 0.85

    retriever = Retriever(store, _config(), semantic_backend=StaticSemanticBackend([semantic]))
    results = retriever.search("conceptual query", source_types=["book"])

    assert results
    assert results[0]["id"] == chunk_id
    assert results[0]["keyword_score"] == 0.0
    assert results[0]["semantic_score"] == 0.85
    assert results[0]["source_type"] == "book"
    assert "Memory Book" in results[0]["citation"]


def test_semantic_failure_falls_back_to_fts_and_logs_context(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    store.init()
    memory_id = store.add_memory(
        memory_type="fact",
        scope="system",
        title="Fallback Recall",
        summary="Hermes returns FTS results when semantic search fails.",
        canonical_text="Hermes returns FTS results when semantic search fails.",
    )

    retriever = Retriever(store, _config(), semantic_backend=FailingSemanticBackend())
    results = retriever.search("fallback recall")

    assert results
    assert results[0]["id"] == memory_id
    with store.connection() as conn:
        row = conn.execute(
            "SELECT query_context_json FROM retrieval_log ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    context = json.loads(row["query_context_json"])
    assert context["semantic_fallback"] is True
    assert context["semantic_error"] == "RuntimeError"


def test_semantic_backend_hydrates_source_chunks_and_applies_source_type_filter(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    store.init()
    source_id, _ = store.upsert_source_file(
        source_path="/transcripts/demo.srt",
        source_type="subtitle",
        title="Demo Transcript",
        content="00:00:01.000 --> 00:00:02.000\nHermes semantic search.",
        chunks=[
            {
                "timestamp_start": "00:00:01.000",
                "timestamp_end": "00:00:02.000",
                "text": "Hermes semantic search.",
            }
        ],
    )
    with store.connection() as conn:
        chunk_id = conn.execute(
            "SELECT id FROM source_chunks WHERE source_id=?",
            (source_id,),
        ).fetchone()["id"]
    qdrant = SearchOnlyQdrant({"kind": "source_chunk", "chunk_id": chunk_id})
    backend = SemanticSearchBackend(
        store=store,
        embedder=FakeEmbedder(),
        qdrant=qdrant,
        collections={"sources": "hermes_sources", "memories": "hermes_memories"},
    )

    results = backend.search("semantic wording", limit=4, source_types=["subtitle"])

    assert results[0]["id"] == chunk_id
    assert results[0]["semantic_score"] == 0.77
    assert qdrant.calls == [
        {
            "collection": "hermes_sources",
            "vector": [0.1, 0.2, 0.3],
            "limit": 4,
            "query_filter": {
                "must": [{"key": "source_type", "match": {"value": "subtitle"}}]
            },
        }
    ]
