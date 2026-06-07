from hermes_memory_os.db.store import MemoryStore
from hermes_memory_os.ingest.markdown import ingest_paths
from hermes_memory_os.retrieval.retriever import Retriever


def test_markdown_ingest_is_idempotent_and_searchable(tmp_path):
    wiki = tmp_path / "wiki-brain"
    wiki.mkdir()
    note = wiki / "reachy-memory.md"
    note.write_text(
        "# Reachy Memory Bridge\n\nReachy should call Hermes Memory OS for durable recall.",
        encoding="utf-8",
    )
    store = MemoryStore(tmp_path / "memory.sqlite")
    store.init()

    first = ingest_paths(store, [wiki])
    second = ingest_paths(store, [wiki])

    assert first == {"files_seen": 1, "indexed": 1, "skipped": 0}
    assert second == {"files_seen": 1, "indexed": 0, "skipped": 1}

    retriever = Retriever(
        store,
        {
            "max_injected": 8,
            "min_final_score": 0.1,
            "weights": {
                "semantic": 0.0,
                "keyword": 1.0,
                "entity": 0.0,
                "scope": 0.0,
                "recency": 0.0,
                "trust": 0.0,
            },
        },
    )

    results = retriever.search("Reachy durable recall")
    assert results
    assert results[0]["kind"] == "source_chunk"
    assert "Reachy" in results[0]["text"]
