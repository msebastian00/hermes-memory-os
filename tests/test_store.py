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
