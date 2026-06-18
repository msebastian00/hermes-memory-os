from hermes_memory_os.safety import forbidden_field_path, normalize_result, safe_payload


def test_forbidden_field_path_finds_nested_values():
    payload = {"outer": [{"safe": "x"}, {"speaker": {"voiceprint": [1, 2, 3]}}]}

    assert forbidden_field_path(payload) == "outer[1].speaker.voiceprint"


def test_safe_payload_removes_forbidden_fields_and_bounds_text():
    payload = {
        "ok": "x" * 20,
        "api_key": "secret",
        "nested": {"db_path": "/tmp/memory.sqlite", "summary": "hello"},
    }

    cleaned = safe_payload(payload, max_text_chars=5)

    assert cleaned["ok"].endswith("…")
    assert "api_key" not in cleaned
    assert "db_path" not in cleaned["nested"]
    assert cleaned["nested"]["summary"] == "hello"


def test_normalize_result_removes_internal_fields():
    raw = {
        "id": "chk_1",
        "kind": "source_chunk",
        "source_id": "src_1",
        "title": "Passage",
        "text": "Memory OS should not leak paths.",
        "source_type": "book",
        "source": "/secret/book.txt",
        "final_score": 0.77,
        "embedding": [1, 2, 3],
        "db_path": "/tmp/memory.sqlite",
    }

    result = normalize_result(raw)

    assert result["id"] == "chk_1"
    assert result["kind"] == "source_chunk"
    assert result["summary"] == "Memory OS should not leak paths."
    assert result["citation"] == "local source"
    assert result["score"] == 0.77
    assert result["location"] == {"source_id": "src_1", "chunk_id": "chk_1"}
    assert "embedding" not in result
    assert "db_path" not in result


def test_normalize_result_suppresses_pending_or_archived():
    assert normalize_result({"id": "mem_1", "status": "pending_review"}) is None
    assert normalize_result({"id": "mem_1", "status": "archived"}) is None
