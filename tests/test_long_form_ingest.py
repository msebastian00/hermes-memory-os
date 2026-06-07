import builtins
import json
import zipfile

import pytest

from hermes_memory_os.db.store import MemoryStore
from hermes_memory_os.errors import ConfigError
from hermes_memory_os.ingest.sources import ingest_paths, load_source_document
from hermes_memory_os.retrieval.retriever import Retriever


def _retriever(store: MemoryStore) -> Retriever:
    return Retriever(
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


def test_txt_book_ingest_preserves_chapter_and_citation(tmp_path):
    book = tmp_path / "memory-book.txt"
    book.write_text(
        "Chapter 1 Memory Systems\n\nHermes uses durable recall for organizational memory.",
        encoding="utf-8",
    )
    store = MemoryStore(tmp_path / "memory.sqlite")
    store.init()

    assert ingest_paths(store, [book]) == {"files_seen": 1, "indexed": 1, "skipped": 0}

    results = _retriever(store).search("organizational memory", source_types=["book"])

    assert results
    assert results[0]["source_type"] == "book"
    assert results[0]["chapter"] == "Chapter 1 Memory Systems"
    assert "memory-book" in results[0]["citation"]
    assert "Chapter 1 Memory Systems" in results[0]["citation"]


def test_source_type_filter_excludes_other_long_form_sources(tmp_path):
    book = tmp_path / "strategy-book.txt"
    transcript = tmp_path / "strategy-transcript.srt"
    book.write_text("Chapter 1\n\nHermes strategy belongs in a book source.", encoding="utf-8")
    transcript.write_text(
        "1\n00:00:01,000 --> 00:00:02,000\nSpeaker 1: Hermes strategy belongs in a transcript.\n",
        encoding="utf-8",
    )
    store = MemoryStore(tmp_path / "memory.sqlite")
    store.init()
    ingest_paths(store, [book, transcript])

    book_results = _retriever(store).search("Hermes strategy", source_types=["book"])
    subtitle_results = _retriever(store).search("Hermes strategy", source_types=["subtitle"])

    assert {item["source_type"] for item in book_results} == {"book"}
    assert {item["source_type"] for item in subtitle_results} == {"subtitle"}


def test_srt_and_vtt_ingest_preserve_timestamps_and_speakers(tmp_path):
    srt = tmp_path / "meeting.srt"
    vtt = tmp_path / "talk.vtt"
    srt.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nMike: Hermes should cite transcript moments.\n",
        encoding="utf-8",
    )
    vtt.write_text(
        "WEBVTT\n\n00:00:04.000 --> 00:00:06.000\nDana: Hermes should keep speaker metadata.\n",
        encoding="utf-8",
    )
    store = MemoryStore(tmp_path / "memory.sqlite")
    store.init()
    ingest_paths(store, [srt, vtt])

    with store.connection() as conn:
        rows = conn.execute(
            """
            SELECT sc.timestamp_start, sc.timestamp_end, sc.speaker, s.source_type
            FROM source_chunks sc
            JOIN sources s ON s.id = sc.source_id
            ORDER BY sc.timestamp_start
            """
        ).fetchall()

    assert rows[0]["timestamp_start"] == "00:00:01.000"
    assert rows[0]["timestamp_end"] == "00:00:03.000"
    assert rows[0]["speaker"] == "Mike"
    assert rows[0]["source_type"] == "subtitle"
    assert rows[1]["speaker"] == "Dana"


def test_json_transcript_ingest_preserves_speaker_metadata(tmp_path):
    transcript = tmp_path / "call.json"
    transcript.write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "speaker": "Mike",
                        "start": "00:01:00",
                        "end": "00:01:10",
                        "text": "Hermes needs JSON transcript ingestion.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    store = MemoryStore(tmp_path / "memory.sqlite")
    store.init()
    ingest_paths(store, [transcript])

    results = _retriever(store).search("JSON transcript", source_types=["transcript"])

    assert results
    assert results[0]["speaker"] == "Mike"
    assert "00:01:00" in results[0]["citation"]


def test_epub_ingest_uses_local_zip_html_extraction(tmp_path):
    epub = tmp_path / "memory.epub"
    with zipfile.ZipFile(epub, "w") as archive:
        archive.writestr(
            "chapter1.xhtml",
            "<html><body><h1>Chapter 1</h1><p>Hermes can ingest EPUB memory books.</p></body></html>",
        )
    store = MemoryStore(tmp_path / "memory.sqlite")
    store.init()
    ingest_paths(store, [epub])

    results = _retriever(store).search("EPUB memory", source_types=["book"])

    assert results
    assert results[0]["source_type"] == "book"
    assert "EPUB memory books" in results[0]["text"]


def test_reindex_helpers_detect_chunking_and_embedding_changes(tmp_path):
    book = tmp_path / "reindex-book.txt"
    book.write_text("Chapter 1\n\nHermes reindexes long-form chunks.", encoding="utf-8")
    store = MemoryStore(tmp_path / "memory.sqlite")
    store.init()
    ingest_paths(store, [book])

    pending = store.list_chunks_needing_index(
        embedding_provider="ollama",
        embedding_model="nomic-embed-text",
        chunking_version="v1",
    )
    assert len(pending) == 1

    store.mark_source_chunk_indexed(
        pending[0]["id"],
        qdrant_point_id="point-1",
        embedding_provider="ollama",
        embedding_model="nomic-embed-text",
        chunking_version="v1",
    )

    assert (
        store.list_chunks_needing_index(
            embedding_provider="ollama",
            embedding_model="nomic-embed-text",
            chunking_version="v1",
        )
        == []
    )
    assert store.list_chunks_needing_index(
        embedding_provider="ollama",
        embedding_model="other-model",
        chunking_version="v1",
    )
    assert store.list_chunks_needing_index(
        embedding_provider="ollama",
        embedding_model="nomic-embed-text",
        chunking_version="v2",
    )

    assert store.mark_source_chunks_for_reindex(source_type="book") == 1
    pending_again = store.list_chunks_needing_index(
        embedding_provider="ollama",
        embedding_model="nomic-embed-text",
        chunking_version="v1",
    )
    assert pending_again[0]["qdrant_point_id"] is None
    assert pending_again[0]["indexing_state"] == "pending"


def test_pdf_ingest_reports_missing_local_parser(tmp_path, monkeypatch):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    def blocked_import(name, *args, **kwargs):
        if name == "pypdf":
            raise ImportError("blocked")
        return original_import(name, *args, **kwargs)

    original_import = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", blocked_import)

    with pytest.raises(ConfigError, match="pypdf"):
        load_source_document(pdf)
