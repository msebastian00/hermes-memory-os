import json

from hermes_memory_os.db.store import BLOCKED_RUNTIME_METADATA, MemoryStore


def test_sync_turn_sanitizes_reachy_runtime_metadata(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    store.init()

    user_id, assistant_id = store.sync_turn(
        "hello",
        "hi",
        {
            "client": "reachy",
            "conversation_id": "conv-1",
            "speaker_confidence": 0.91,
            "wake_state": "listening",
            "latency_budget_ms": 300,
            "tags": ["voice"],
        },
    )

    with store.connection() as conn:
        rows = conn.execute(
            "SELECT id, client, conversation_id, metadata_json FROM raw_events ORDER BY created_at"
        ).fetchall()

    assert {rows[0]["id"], rows[1]["id"]} == {user_id, assistant_id}
    assert rows[0]["client"] == "reachy"
    assert rows[0]["conversation_id"] == "conv-1"
    metadata = json.loads(rows[0]["metadata_json"])
    assert metadata["client"] == "reachy"
    assert metadata["tags"] == ["voice"]
    for key in BLOCKED_RUNTIME_METADATA:
        assert key not in metadata


def test_add_archive_memory_keeps_record(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    store.init()
    memory_id = store.add_memory(
        memory_type="fact",
        scope="system",
        title="Hermes Memory OS",
        summary="Hermes Memory OS owns durable local memory.",
        canonical_text="Hermes Memory OS owns durable local memory.",
    )

    store.archive_memory(memory_id, "stale test")

    with store.connection() as conn:
        row = conn.execute("SELECT status FROM memories WHERE id=?", (memory_id,)).fetchone()

    assert row["status"] == "archived"


def test_extraction_candidate_lifecycle(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    store.init()
    event_id = store.add_raw_event("Hermes should remember reviewed candidates.")

    candidate_id = store.create_extraction_candidate(
        source_event_ids=[event_id],
        memory_type="fact",
        scope="system",
        title="Reviewed extraction",
        summary="Hermes can stage candidate memories for review.",
        canonical_text="Hermes can stage candidate memories for review before saving them.",
        entities=["Hermes"],
        tags=["review"],
        confidence=0.82,
        reason_to_save="Useful durable product behavior.",
    )

    pending = store.list_extraction_candidates(status="pending_review")

    assert len(pending) == 1
    assert pending[0]["id"] == candidate_id
    assert pending[0]["source_event_ids"] == [event_id]
    assert pending[0]["entities"] == ["Hermes"]
    assert pending[0]["tags"] == ["review"]
    assert pending[0]["status"] == "pending_review"

    store.update_extraction_candidate(candidate_id, status="approved", confidence=0.9)

    assert store.list_extraction_candidates(status="pending_review") == []
    approved = store.list_extraction_candidates(status="approved")
    assert approved[0]["id"] == candidate_id
    assert approved[0]["confidence"] == 0.9
    assert approved[0]["reviewed_at"] is not None


def test_qdrant_point_ids_are_persisted(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    store.init()
    memory_id = store.add_memory(
        memory_type="fact",
        scope="system",
        title="Semantic memory",
        summary="Semantic memories retain Qdrant point IDs.",
        canonical_text="Semantic memories retain Qdrant point IDs.",
    )
    source_id, indexed = store.upsert_source_file(
        source_path="/wiki/semantic.md",
        source_type="markdown",
        title="Semantic",
        content="# Semantic\n\nChunks retain Qdrant point IDs.",
        chunks=[{"heading": "Semantic", "text": "Chunks retain Qdrant point IDs."}],
    )
    assert indexed is True

    with store.connection() as conn:
        chunk = conn.execute(
            "SELECT id FROM source_chunks WHERE source_id=?",
            (source_id,),
        ).fetchone()

    store.save_memory_qdrant_point(
        memory_id,
        collection="hermes_memories",
        point_id="mem-point-1",
    )
    store.save_source_chunk_qdrant_point(chunk["id"], "chunk-point-1")

    with store.connection() as conn:
        memory = conn.execute(
            "SELECT qdrant_collection, qdrant_point_id FROM memories WHERE id=?",
            (memory_id,),
        ).fetchone()
        chunk = conn.execute(
            "SELECT qdrant_point_id FROM source_chunks WHERE id=?",
            (chunk["id"],),
        ).fetchone()

    assert memory["qdrant_collection"] == "hermes_memories"
    assert memory["qdrant_point_id"] == "mem-point-1"
    assert chunk["qdrant_point_id"] == "chunk-point-1"
