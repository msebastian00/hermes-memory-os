from hermes_memory_os.provider import HermesMemoryOSProvider
from hermes_memory_os.provider import adapter as provider_adapter


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


def test_provider_prefetch_adds_evidence_backed_graph_context_when_enabled(tmp_path, monkeypatch):
    provider = HermesMemoryOSProvider()
    provider.initialize({"data_dir": str(tmp_path)})
    monkeypatch.setenv("HERMES_GRAPH_ENABLED", "true")
    monkeypatch.setattr(
        provider_adapter,
        "handle_graph_retrieve",
        lambda *_args, **_kwargs: {
            "provenance": [
                {
                    "claim_text": "Life design is iterative.",
                    "quote": "Prototype experiences create useful feedback.",
                    "source_id": "book-designing-your-life-undated",
                    "source_chunk_id": "chunk_49_prototype-experiences",
                    "confidence": 0.78,
                }
            ]
        },
    )

    injected = provider.prefetch("life design")

    assert "Evidence-Backed Graph Context" in injected
    assert "Source claim: Life design is iterative." in injected
    assert "book-designing-your-life-undated/chunk_49_prototype-experiences" in injected
    assert "confidence 0.78" in injected


def test_provider_prefetch_does_not_add_graph_context_when_disabled(tmp_path, monkeypatch):
    provider = HermesMemoryOSProvider()
    provider.initialize({"data_dir": str(tmp_path)})
    monkeypatch.delenv("HERMES_GRAPH_ENABLED", raising=False)
    monkeypatch.setattr(
        provider_adapter,
        "handle_graph_retrieve",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("graph must remain disabled")),
    )

    assert provider.prefetch("no local result") == ""
