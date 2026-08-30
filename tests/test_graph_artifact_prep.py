import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from hermes_memory_os.app import MemoryApp
from hermes_memory_os.db.store import MemoryStore
from hermes_memory_os.graph.artifact_prep import embedding_input_limit, prepare_book_artifacts
from hermes_memory_os.graph.builder import discover_book
from hermes_memory_os.graph.config import GraphConfig
from hermes_memory_os.graph.crosswalk import CrosswalkError, index_book_crosswalk, write_crosswalk


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _book_vault(tmp_path: Path, raw_text: str, chunks: list[dict], bodies: list[dict]) -> GraphConfig:
    vault = tmp_path / "vault"
    digest = __import__("hashlib").sha256(raw_text.encode("utf-8")).hexdigest()
    _write(
        vault / "03_RESOURCES/books/raw/book-one/manifest.md",
        f"---\nsource_id: book-one\ntitle: Book One\nauthors:\n  - Author One\ncontent_hash: {digest}\nsource_path: 03_RESOURCES/books/raw/book-one.md\n---\n",
    )
    _write(vault / "03_RESOURCES/books/raw/book-one.md", raw_text)
    _write(
        vault / "02_WIKI/sources/books/book-one.md",
        "---\nsource_id: book-one\ntitle: Book One\nauthors:\n  - Author One\n---\n## Claims, Evidence, and Limitations\n\n### Claims\n1. A reviewed claim.\n",
    )
    _write(vault / "05_QUEUE/book-ingestion/incoming/book-one.md", "---\nsource_id: book-one\n---\n")
    fence = chr(96) * 3
    _write(
        vault / "06_GENERATED/source-analysis/book-one/retrieval-chunks.md",
        fence + "json\n" + json.dumps(chunks) + "\n" + fence + "\n",
    )
    _write(
        vault / "06_GENERATED/source-analysis/book-one/chunk-bodies.json",
        json.dumps({"source_id": "book-one", "raw_content_hash": digest, "chunks": bodies}, indent=2),
    )
    config_path = tmp_path / "graph.yml"
    _write(config_path, "paths:\n  vault_root: vault\ngraph:\n  default_write_mode: dry_run\n  review_report_path: reports\n")
    return GraphConfig.load(config_path)


def _two_chunk_book(tmp_path: Path, limit_text: str) -> tuple[GraphConfig, str]:
    small = "small exact span\n\n"
    raw = small + limit_text
    chunks = [
        {"chunk_id": "keep-small", "chunk_index": 0, "section": "intro", "source_id": "book-one", "title": "Book One"},
        {"chunk_id": "oversized-parent", "chunk_index": 1, "section": "body", "source_id": "book-one", "title": "Book One"},
    ]
    bodies = [
        {"chunk_id": "keep-small", "text": small, "span_start": 0, "span_end": len(small)},
        {"chunk_id": "oversized-parent", "text": limit_text, "span_start": len(small), "span_end": len(raw)},
    ]
    return _book_vault(tmp_path, raw, chunks, bodies), raw


def test_prepared_chunks_are_at_or_under_configured_limit(tmp_path):
    oversized = ("paragraph one. " * 250) + "\n\n" + ("paragraph two. " * 250)
    assert len(oversized) > 6000
    config, raw = _two_chunk_book(tmp_path, oversized)

    planned = prepare_book_artifacts(config, "book-one", write_mode="dry_run", max_chunk_chars=6000)
    prepared = prepare_book_artifacts(config, "book-one", write_mode="upsert", max_chunk_chars=6000)
    again = prepare_book_artifacts(config, "book-one", write_mode="upsert", max_chunk_chars=6000)
    bodies = json.loads((config.vault_root / "06_GENERATED/source-analysis/book-one/chunk-bodies.json").read_text(encoding="utf-8"))
    artifact = discover_book(config.vault_root, "book-one")

    assert planned["status"] == "planned"
    assert prepared["max_input_chars"] == 6000
    assert all(len(row["text"]) <= 6000 for row in bodies["chunks"])
    assert all(raw[row["span_start"]:row["span_end"]] == row["text"] for row in bodies["chunks"])
    ids = [row["chunk_id"] for row in bodies["chunks"]]
    assert "keep-small" in ids
    assert "oversized-parent" not in ids
    assert any(item.startswith("oversized-parent__p") for item in ids)
    assert again["chunk_count"] == prepared["chunk_count"] == len(artifact.chunks)
    assert [chunk["chunk_id"] for chunk in artifact.chunks] == ids


def test_vector_text_must_equal_declared_exact_span(tmp_path):
    config, _raw = _two_chunk_book(tmp_path, "short enough")
    bodies_path = config.vault_root / "06_GENERATED/source-analysis/book-one/chunk-bodies.json"
    payload = json.loads(bodies_path.read_text(encoding="utf-8"))
    payload["chunks"][0]["text"] = "tampered"
    bodies_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CrosswalkError, match="does not exactly match"):
        index_book_crosswalk(SimpleNamespace(config=SimpleNamespace(embeddings={"max_input_chars": 6000})), config, "book-one", bodies_path, write_mode="dry_run")


def test_write_crosswalk_refuses_missing_point(tmp_path):
    out = tmp_path / "crosswalk.json"
    with pytest.raises(CrosswalkError, match="incomplete"):
        write_crosswalk({"qdrant_point_ids": {"a": "point-a", "b": None}}, out)
    assert not out.exists()


def test_supersede_source_only_after_complete_replacement(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite")
    store.init()
    old_id, _ = store.upsert_source_file(
        source_path="graph-crosswalk://book-one/oldhash",
        source_type="book",
        title="old",
        content="old-content",
        chunks=[{"text": "old-chunk", "metadata": {"graph_source_chunk_id": "keep-small"}}],
        source_metadata={"graph_source_id": "book-one"},
        chunking_version="graph-crosswalk-v1",
    )
    new_id, _ = store.upsert_source_file(
        source_path="graph-crosswalk://book-one/newhash/digest",
        source_type="book",
        title="new",
        content="new-content",
        chunks=[{"text": "new-chunk", "metadata": {"graph_source_chunk_id": "keep-small"}}],
        source_metadata={"graph_source_id": "book-one"},
        chunking_version="graph-crosswalk-v1",
    )
    assert store.get_source(old_id)["status"] == "active"
    assert store.supersede_source(old_id, replaced_by=old_id, reason="noop") is False
    assert store.get_source(old_id)["status"] == "active"
    assert store.supersede_source(old_id, replaced_by=new_id, reason="replaced by complete graph-crosswalk") is True
    old = store.get_source(old_id)
    assert old["status"] == "superseded"
    assert old["metadata"]["superseded_by"] == new_id
    assert store.list_sources_by_path_prefix("graph-crosswalk://book-one/", status="active") == [
        store.get_source(new_id)
    ]


class _FakeEmbedder:
    def __init__(self):
        self.calls = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return [0.1, 0.2, 0.3]

    def health(self) -> bool:
        return True


class _FakeQdrant:
    def __init__(self, url: str, timeout: int = 10, api_key: str | None = None):
        self.points = {}

    def health(self) -> bool:
        return True

    def collection_exists(self, name: str) -> bool:
        return True

    def ensure_collection(self, name: str, vector_size: int, distance: str = "Cosine") -> None:
        return None

    def upsert_point(self, collection: str, point_id: str, vector: list[float], payload: dict) -> None:
        self.points[point_id] = payload["text_excerpt"]


def _semantic_app(tmp_path: Path, monkeypatch) -> MemoryApp:
    data_dir = tmp_path / "data"
    config_path = tmp_path / "mem.yml"
    config_path.write_text(
        f"""
paths:
  base_dir: {data_dir}
  vault_dir: {data_dir / "vault"}
  sqlite_path: {data_dir / "db" / "memory.sqlite"}
  logs_dir: {data_dir / "logs"}
qdrant:
  enabled: true
  url: http://localhost:6333
  vector_size: 3
  collections:
    sources: hermes_sources
embeddings:
  provider: ollama
  model: test-embed
  dimension: 3
  max_input_chars: 6000
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("hermes_memory_os.app.QdrantClient", _FakeQdrant)
    monkeypatch.setattr("hermes_memory_os.app.build_embedder", lambda config: _FakeEmbedder())
    app = MemoryApp.from_config(config_path=config_path)
    app.init_storage()
    return app


def test_complete_replacement_supersedes_prior_partial_source(tmp_path, monkeypatch):
    config, raw = _two_chunk_book(tmp_path, "fits-limit")
    app = _semantic_app(tmp_path, monkeypatch)
    old_id, _ = app.store.upsert_source_file(
        source_path="graph-crosswalk://book-one/oldpartial",
        source_type="book",
        title="partial",
        content=raw,
        chunks=[{"text": "fits-limit", "metadata": {"graph_source_chunk_id": "keep-small"}}],
        source_metadata={"graph_source_id": "book-one"},
        chunking_version="graph-crosswalk-v1",
    )
    bodies = config.vault_root / "06_GENERATED/source-analysis/book-one/chunk-bodies.json"
    result = index_book_crosswalk(app, config, "book-one", bodies, write_mode="upsert")
    assert result["status"] == "indexed"
    assert result["qdrant_point_ids"]
    assert all(result["qdrant_point_ids"].values())
    assert old_id in result["superseded_source_ids"]
    assert app.store.get_source(old_id)["status"] == "superseded"
    assert app.store.get_source(result["memory_os_source_id"])["status"] == "active"
    for text in app.semantic_indexer.embedder.calls:
        assert text in raw
        assert len(text) <= 6000


def test_partial_index_does_not_supersede_prior_source(tmp_path, monkeypatch):
    config, raw = _two_chunk_book(tmp_path, "fits-limit")
    app = _semantic_app(tmp_path, monkeypatch)
    old_id, _ = app.store.upsert_source_file(
        source_path="graph-crosswalk://book-one/oldpartial",
        source_type="book",
        title="partial",
        content=raw,
        chunks=[{"text": "fits-limit", "metadata": {"graph_source_chunk_id": "keep-small"}}],
        source_metadata={"graph_source_id": "book-one"},
        chunking_version="graph-crosswalk-v1",
    )

    def fail_index(chunks):
        return {"semantic_indexed": 0, "semantic_failed": len(chunks)}

    app.semantic_indexer.index_source_chunks = fail_index
    bodies = config.vault_root / "06_GENERATED/source-analysis/book-one/chunk-bodies.json"
    result = index_book_crosswalk(app, config, "book-one", bodies, write_mode="upsert")
    assert result["status"] == "partially_indexed"
    assert result["superseded_source_ids"] == []
    assert app.store.get_source(old_id)["status"] == "active"
    with pytest.raises(CrosswalkError, match="incomplete"):
        write_crosswalk(result, tmp_path / "out.json")


def test_embedding_input_default_is_conservative_for_nomic_context(monkeypatch):
    monkeypatch.delenv("HERMES_EMBEDDING_MAX_INPUT_CHARS", raising=False)
    assert embedding_input_limit() == 4000
