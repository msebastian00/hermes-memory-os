from hermes_memory_os.provider import HermesMemoryOSProvider


def test_provider_prefetch_and_sync_turn(tmp_path):
    provider = HermesMemoryOSProvider()
    provider.initialize({"data_dir": str(tmp_path)})
    provider.handle_tool_call(
        "hermes_memory_add",
        {
            "memory_type": "fact",
            "scope": "system",
            "title": "Wiki Brain",
            "summary": "The existing wiki-brain is indexed as an external knowledge layer.",
            "canonical_text": "The existing wiki-brain is indexed as an external knowledge layer.",
            "tags": ["wiki-brain"],
            "entities": ["Hermes"],
        },
    )

    injected = provider.prefetch("wiki brain knowledge layer")

    assert "Relevant Local Memory" in injected
    assert "wiki-brain" in injected or "Wiki Brain" in injected

    synced = provider.sync_turn(
        "remember this",
        "stored",
        {"client": "reachy", "speaker_confidence": 0.4, "conversation_id": "c1"},
    )
    assert len(synced["raw_event_ids"]) == 2


def test_self_learning_is_logged_not_applied(tmp_path):
    provider = HermesMemoryOSProvider()
    provider.initialize({"data_dir": str(tmp_path)})

    result = provider.on_session_end([{"role": "user", "content": "missed recall"}])

    assert result["review_event_id"].startswith("learn_")
    with provider.app.store.connection() as conn:
        row = conn.execute("SELECT status FROM agent_learning_events").fetchone()
    assert row["status"] == "pending_review"
