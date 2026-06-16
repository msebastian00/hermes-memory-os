from pathlib import Path
import json

from hermes_memory_os.app import MemoryApp
from hermes_memory_os.cli import main


class FakeEmbedder:
    def __init__(self):
        self.calls = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return [0.1, 0.2, 0.3]

    def health(self) -> bool:
        return True


class FakeQdrant:
    upserts = []
    ensured = []

    def __init__(self, url: str):
        self.url = url

    def health(self) -> bool:
        return True

    def collection_exists(self, name: str) -> bool:
        return name in self.ensured

    def ensure_collection(self, name: str, vector_size: int, distance: str = "Cosine") -> None:
        self.ensured.append(name)

    def upsert_point(self, collection: str, point_id: str, vector: list[float], payload: dict) -> None:
        self.upserts.append(
            {
                "collection": collection,
                "point_id": point_id,
                "vector": vector,
                "payload": payload,
            }
        )


def _write_storage_config(path: Path, data_dir: Path) -> None:
    path.write_text(
        f"""
paths:
  base_dir: {data_dir}
  vault_dir: {data_dir / "vault"}
  sqlite_path: {data_dir / "db" / "memory.sqlite"}
  logs_dir: {data_dir / "logs"}
qdrant:
  enabled: false
embeddings:
  provider: none
""",
        encoding="utf-8",
    )


def _write_semantic_config(path: Path, data_dir: Path) -> None:
    path.write_text(
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
  distance: Cosine
  collections:
    memories: hermes_memories
    wiki: hermes_wiki
    captures: hermes_captures
    sources: hermes_sources
embeddings:
  provider: ollama
  base_url: http://localhost:11434
  model: test-embed
  dimension: 3
""",
        encoding="utf-8",
    )


def test_app_ingest_semantically_indexes_source_chunks(tmp_path, monkeypatch):
    FakeQdrant.upserts = []
    FakeQdrant.ensured = []
    monkeypatch.setattr("hermes_memory_os.app.QdrantClient", FakeQdrant)
    monkeypatch.setattr("hermes_memory_os.app.build_embedder", lambda config: FakeEmbedder())
    config_path = tmp_path / "config.yml"
    data_dir = tmp_path / "data"
    _write_semantic_config(config_path, data_dir)
    transcript = tmp_path / "meeting.srt"
    transcript.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nMike: Hermes should index transcript chunks.\n",
        encoding="utf-8",
    )

    app = MemoryApp.from_config(config_path=config_path)
    app.init_storage()
    result = app.ingest_sources([transcript])

    assert result["indexed"] == 1
    assert result["semantic_indexed"] == 1
    assert result["semantic_failed"] == 0
    assert FakeQdrant.upserts[0]["collection"] == "hermes_sources"
    assert FakeQdrant.upserts[0]["vector"] == [0.1, 0.2, 0.3]
    payload = FakeQdrant.upserts[0]["payload"]
    assert payload["kind"] == "source_chunk"
    assert payload["source_type"] == "subtitle"
    assert payload["timestamp_start"] == "00:00:01.000"
    assert payload["speaker"] == "Mike"
    assert payload["embedding_provider"] == "ollama"
    assert payload["embedding_model"] == "test-embed"
    assert "meeting" in payload["citation"]

    with app.store.connection() as conn:
        row = conn.execute(
            "SELECT qdrant_point_id, embedding_provider, embedding_model, indexing_state FROM source_chunks"
        ).fetchone()
    assert row["qdrant_point_id"] == FakeQdrant.upserts[0]["point_id"]
    assert row["embedding_provider"] == "ollama"
    assert row["embedding_model"] == "test-embed"
    assert row["indexing_state"] == "indexed"


def test_app_add_semantically_indexes_durable_memory(tmp_path, monkeypatch):
    FakeQdrant.upserts = []
    FakeQdrant.ensured = []
    monkeypatch.setattr("hermes_memory_os.app.QdrantClient", FakeQdrant)
    monkeypatch.setattr("hermes_memory_os.app.build_embedder", lambda config: FakeEmbedder())
    config_path = tmp_path / "config.yml"
    data_dir = tmp_path / "data"
    _write_semantic_config(config_path, data_dir)

    app = MemoryApp.from_config(config_path=config_path)
    app.init_storage()
    result = app.add_memory(
        memory_type="fact",
        scope="system",
        title="Semantic add",
        summary="Hermes indexes durable memories.",
        canonical_text="Hermes indexes durable memories into Qdrant.",
        tags=["semantic"],
        entities=["Hermes"],
    )

    assert result["memory_id"].startswith("mem_")
    assert result["semantic_indexed"] == 1
    assert result["semantic_failed"] == 0
    assert FakeQdrant.upserts[0]["collection"] == "hermes_memories"
    payload = FakeQdrant.upserts[0]["payload"]
    assert payload["kind"] == "memory"
    assert payload["memory_id"] == result["memory_id"]
    assert payload["tags"] == ["semantic"]
    assert payload["entities"] == ["Hermes"]

    with app.store.connection() as conn:
        row = conn.execute(
            "SELECT qdrant_collection, qdrant_point_id FROM memories WHERE id=?",
            (result["memory_id"],),
        ).fetchone()
    assert row["qdrant_collection"] == "hermes_memories"
    assert row["qdrant_point_id"] == FakeQdrant.upserts[0]["point_id"]


def test_reindex_memories_backfills_existing_durable_memories(tmp_path, monkeypatch, capsys):
    FakeQdrant.upserts = []
    FakeQdrant.ensured = []
    monkeypatch.setattr("hermes_memory_os.app.QdrantClient", FakeQdrant)
    monkeypatch.setattr("hermes_memory_os.app.build_embedder", lambda config: FakeEmbedder())
    storage_config = tmp_path / "storage.yml"
    semantic_config = tmp_path / "semantic.yml"
    data_dir = tmp_path / "data"
    _write_storage_config(storage_config, data_dir)
    _write_semantic_config(semantic_config, data_dir)

    storage_app = MemoryApp.from_config(config_path=storage_config)
    storage_app.init_storage()
    storage_app.add_memory(
        memory_type="fact",
        scope="system",
        title="Backfill one",
        summary="First memory to backfill.",
        canonical_text="First memory to backfill.",
    )
    storage_app.add_memory(
        memory_type="fact",
        scope="system",
        title="Backfill two",
        summary="Second memory to backfill.",
        canonical_text="Second memory to backfill.",
    )

    assert main(["--config", str(semantic_config), "reindex-memories"]) == 0
    result = capsys.readouterr()
    status = json.loads(result.out)

    assert status["semantic_enabled"] is True
    assert status["memories_reindexed"] == 2
    assert status["semantic_indexed"] == 2
    assert status["semantic_failed"] == 0
    assert len(FakeQdrant.upserts) == 2
    assert {item["collection"] for item in FakeQdrant.upserts} == {"hermes_memories"}
