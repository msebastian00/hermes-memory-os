from __future__ import annotations

import hashlib
from pathlib import Path

from hermes_memory_os.graph import multimodal


class _Response:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            "choices": [{
                "message": {
                    "content": '{"modality":"equation","description":"x equals y","confidence":0.9}'
                }
            }]
        }


def test_visual_request_uses_verified_spark_model_and_non_thinking_mode(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "page-0001.png"
    image.write_bytes(b"test-image")
    monkeypatch.setenv("HERMES_GRAPH_VLM_BASE_URL", "http://192.168.100.11:8002/v1")
    monkeypatch.delenv("HERMES_GRAPH_VLM_MODEL", raising=False)
    captured: dict[str, object] = {}

    def fake_post(url: str, *, json: dict[str, object], timeout: int) -> _Response:
        captured.update({"url": url, "payload": json, "timeout": timeout})
        return _Response()

    monkeypatch.setattr(multimodal.requests, "post", fake_post)
    result = multimodal.analyze_image(image, prompt="extract")

    assert captured["url"] == "http://192.168.100.11:8002/v1/chat/completions"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "qwen36"
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert result["attachment_sha256"] == hashlib.sha256(b"test-image").hexdigest()
    assert result["extractor"] == "spark1:qwen36"


def test_visual_plan_uses_immutable_attachment_identity_not_vlm_wording(tmp_path: Path, monkeypatch) -> None:
    raw = tmp_path / "source.txt"
    raw.write_text("important source text", encoding="utf-8")
    attachment = tmp_path / "page-0010.png"
    attachment.write_bytes(b"visual")
    chunk = {
        "chunk_index": 0,
        "page_start": 10,
        "page_end": 10,
        "span_start": 0,
        "span_end": len(raw.read_text(encoding="utf-8")),
    }

    class _Book:
        source_id = "book-test"
        raw_relative_path = "03_RESOURCES/books/raw/source.txt"
        raw_path = raw
        title = "Test Book"
        authors = ("Test Author",)
        chunks = (chunk,)

    monkeypatch.setattr("hermes_memory_os.graph.builder.discover_book", lambda *_args: _Book())
    config = type("Config", (), {"vault_root": tmp_path})()
    digest = hashlib.sha256(attachment.read_bytes()).hexdigest()
    common = {
        "attachment_path": str(attachment),
        "attachment_sha256": digest,
        "extractor": "spark1:qwen36",
        "confidence": 0.9,
        "page_number": 10,
        "modality": "diagram",
    }
    first = multimodal.visual_evidence_plan(
        config, "book-test", [{**common, "description": "first wording", "claim_text": "first claim"}]
    )
    second = multimodal.visual_evidence_plan(
        config, "book-test", [{**common, "description": "second wording", "claim_text": "second claim"}]
    )

    assert first["nodes"][0]["id"] == second["nodes"][0]["id"]
    assert first["nodes"][1]["id"] == second["nodes"][1]["id"]
    assert first["visual_records"] == second["visual_records"]


def test_searchable_text_removes_line_break_hyphenation_with_offsets() -> None:
    text, offsets = multimodal._searchable_text("impor-\n  tant", with_offsets=True)

    assert text == "important"
    assert offsets[-1] == len("impor-\n  tan")
