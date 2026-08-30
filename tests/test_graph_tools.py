import json
from pathlib import Path

from hermes_memory_os.graph.flags import graph_enabled
from hermes_memory_os.graph.retrieval import GraphRetrievalAdapter
from hermes_memory_os.graph.tools import (
    ALLOWED_BOOK_SOURCE_ID,
    dispatch_graph_tool,
    handle_graph_build_book,
    handle_graph_retrieve,
    openai_graph_tool_schemas,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _allowed_book_config(tmp_path: Path):
    from hermes_memory_os.graph.config import GraphConfig

    vault = tmp_path / "vault"
    source_id = ALLOWED_BOOK_SOURCE_ID
    _write(
        vault / "03_RESOURCES/books/raw/book-finite-infinite-games-undated/manifest.md",
        f"""---
source_id: {source_id}
title: Finite and Infinite Games
authors:
  - James P. Carse
content_hash: abc123
source_path: 03_RESOURCES/books/raw/book-finite-infinite-games-undated.md
---
""",
    )
    _write(vault / "03_RESOURCES/books/raw/book-finite-infinite-games-undated.md", "Original source text.")
    _write(
        vault / "05_QUEUE/book-ingestion/incoming/book-finite-infinite-games-undated.md",
        f"---\nsource_id: {source_id}\ntype: book-ingestion-queue\n---\n",
    )
    _write(
        vault / "02_WIKI/sources/books/finite-infinite-games.md",
        f"""---
source_id: {source_id}
title: Finite and Infinite Games
authors:
  - James P. Carse
key_concepts:
  - Finite game
  - Infinite game
---
## Claims, Evidence, and Limitations

### Claims
1. There are two kinds of games: finite and infinite.
2. Infinite games continue play.
""",
    )
    chunks = [
        {
            "chunk_id": "chunk-one",
            "source_id": source_id,
            "source_type": "book",
            "title": "Finite and Infinite Games",
            "section": "1-10",
            "chunk_index": 0,
            "page_start": 1,
            "page_end": 10,
        }
    ]
    fence = chr(96) * 3
    _write(
        vault / f"06_GENERATED/source-analysis/{source_id}/retrieval-chunks.md",
        fence + "json\n" + json.dumps(chunks) + "\n" + fence + "\n",
    )
    config_path = tmp_path / "graph.yml"
    _write(
        config_path,
        """paths:
  vault_root: vault
graph:
  default_write_mode: dry_run
  review_report_path: reports
""",
    )
    return GraphConfig.load(config_path), config_path


class _Store:
    def get_source_chunk(self, _):
        return {"id": "memory-chunk", "qdrant_point_id": "point-1"}


class _Semantic:
    def __init__(self, hits=None):
        self.calls = 0
        self.hits = hits or [
            {"id": "memory-chunk", "kind": "source_chunk", "semantic_score": 0.9, "text": "supported claim"}
        ]

    def search(self, query, *, limit):
        self.calls += 1
        return list(self.hits)[:limit]


class _Retriever:
    def __init__(self, hits=None):
        self.semantic_backend = _Semantic(hits)
        self.fallback_called = False
        self.fallback_hits = [{"id": "fallback", "kind": "memory", "text": "memory only"}]

    def search(self, *args, **kwargs):
        self.fallback_called = True
        return list(self.fallback_hits)


class _App:
    def __init__(self, hits=None):
        self.store = _Store()
        self.retriever = _Retriever(hits)


class _Graph:
    def __init__(self, rows=None, error=None):
        self.calls = []
        self.rows = rows or []
        self.error = error

    def expand_context(self, chunk_ids, point_ids):
        self.calls.append((list(chunk_ids), list(point_ids)))
        if self.error:
            raise self.error
        return list(self.rows)

    def health(self):
        return True


class _RecordingBuilder:
    def __init__(self, config):
        self.config = config
        self.calls = []

    def build(self, source_id, *, write_mode="dry_run", qdrant_crosswalk=None, client=None):
        self.calls.append(
            {
                "source_id": source_id,
                "write_mode": write_mode,
                "client": client,
                "qdrant_crosswalk": qdrant_crosswalk,
            }
        )
        if write_mode == "upsert":
            assert client is not None
            client.upsert([], [])
        return {
            "source_id": source_id,
            "write_mode": write_mode,
            "status": "planned" if write_mode == "dry_run" else "upserted",
            "warnings": ["embedding_missing:chunk-one"],
            "stats": {"nodes": 1, "relationships": 1, "warnings": 1},
            "plan": {"nodes": [], "relationships": []},
        }


class _UpsertClient:
    def __init__(self):
        self.upserts = 0

    def upsert(self, nodes, relationships):
        self.upserts += 1
        return {"nodes": len(nodes), "relationships": len(relationships)}

    def health(self):
        return True


SUPPORTED_ROW = {
    "chunk_id": "memory-chunk",
    "qdrant_point_id": "point-1",
    "source_id": ALLOWED_BOOK_SOURCE_ID,
    "source_chunk_id": "chunk-one",
    "claim_id": "claim-1",
    "claim_text": "A supported claim.",
    "claim_confidence": 0.8,
    "claim_status": "active",
    "claim_basis": "author-framework",
    "verification_status": "unverified",
    "evidence_id": "evidence-1",
    "evidence_quote": "A short quote.",
    "entity_name": "Finite and Infinite Games",
}


def test_graph_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("HERMES_GRAPH_ENABLED", raising=False)
    assert graph_enabled() is False
    assert graph_enabled({"HERMES_GRAPH_ENABLED": "false"}) is False
    assert graph_enabled({"HERMES_GRAPH_ENABLED": "true"}) is True


def test_feature_off_skips_graph_and_returns_memory_hits():
    app = _App()
    graph = _Graph(rows=[SUPPORTED_ROW])
    packet = handle_graph_retrieve(
        app,
        {"query": "supported claim"},
        graph_client=graph,
        environ={"HERMES_GRAPH_ENABLED": "false"},
    )
    assert graph.calls == []
    assert packet["graph_enabled"] is False
    assert packet["semantic_hits"]
    assert packet["graph_hits"] == []
    assert packet["claims"] == []
    assert "graph_disabled" in packet["review_warnings"]
    assert packet["write_mode"] == "read"


def test_neo4j_unavailable_falls_back_to_memory_os():
    app = _App()

    def boom(_config):
        raise ConnectionError("neo4j down")

    packet = handle_graph_retrieve(
        app,
        {"query": "supported claim"},
        environ={"HERMES_GRAPH_ENABLED": "true"},
        neo4j_client_factory=boom,
        config_path="unused.yml",
    )
    assert packet["graph_hits"] == []
    assert packet["semantic_hits"]
    assert any(item.startswith("graph_unavailable:") for item in packet["review_warnings"])
    assert packet["graph_enabled"] is True


def test_graph_client_exception_does_not_fail_request():
    app = _App()
    packet = GraphRetrievalAdapter(app, _Graph(error=RuntimeError("down"))).retrieve("supported claim")
    assert packet["semantic_hits"]
    assert packet["claims"] == []
    assert any(item.startswith("graph_unavailable:") for item in packet["review_warnings"])


def test_dry_run_is_default_and_does_not_upsert(tmp_path):
    _config, config_path = _allowed_book_config(tmp_path)
    built = []

    def factory(config):
        builder = _RecordingBuilder(config)
        built.append(builder)
        return builder

    result = handle_graph_build_book(
        {"source_id": ALLOWED_BOOK_SOURCE_ID},
        config_path=config_path,
        environ={"HERMES_GRAPH_ENABLED": "false"},
        builder_factory=factory,
        neo4j_client_factory=lambda _c: (_ for _ in ()).throw(AssertionError("no neo4j on dry_run")),
    )
    assert result["write_mode"] == "dry_run"
    assert result["status"] == "planned"
    assert built[0].calls[0]["write_mode"] == "dry_run"
    assert built[0].calls[0]["client"] is None
    assert result["report_path"]
    assert Path(result["report_path"]).is_file()
    assert "plan" not in json.loads(Path(result["report_path"]).read_text())


def test_queue_authorized_upsert_uses_injected_client(tmp_path):
    _config, config_path = _allowed_book_config(tmp_path)
    client = _UpsertClient()
    built = []

    def factory(config):
        builder = _RecordingBuilder(config)
        built.append(builder)
        return builder

    result = handle_graph_build_book(
        {
            "source_id": ALLOWED_BOOK_SOURCE_ID,
            "write_mode": "upsert",
        },
        config_path=config_path,
        environ={"HERMES_GRAPH_ENABLED": "true"},
        builder_factory=factory,
        neo4j_client_factory=lambda _c: client,
    )
    assert result["status"] == "upserted"
    assert result["write_mode"] == "upsert"
    assert built[0].calls[0]["client"] is client
    assert client.upserts == 1


def test_upsert_blocked_when_graph_disabled(tmp_path):
    _config, config_path = _allowed_book_config(tmp_path)
    result = handle_graph_build_book(
        {
            "source_id": ALLOWED_BOOK_SOURCE_ID,
            "write_mode": "upsert",
        },
        config_path=config_path,
        environ={"HERMES_GRAPH_ENABLED": "false"},
        builder_factory=lambda config: (_ for _ in ()).throw(AssertionError("must not build")),
    )
    assert result["status"] == "graph_disabled"
    assert result["write_mode"] == "dry_run"


def test_queue_authorized_source_id_is_accepted(tmp_path):
    _config, config_path = _allowed_book_config(tmp_path)
    _write(tmp_path / "vault" / "05_QUEUE" / "book-ingestion" / "incoming" / "book-other.md", "---\nsource_id: book-other\n---\n")
    result = handle_graph_build_book(
        {"source_id": "book-other"},
        config_path=config_path,
        environ={"HERMES_GRAPH_ENABLED": "false"},
        builder_factory=_RecordingBuilder,
    )

    assert result["status"] == "planned"
    assert result["source_id"] == "book-other"


def test_unsupported_source_id_is_rejected(tmp_path):
    _config, config_path = _allowed_book_config(tmp_path)
    result = handle_graph_build_book(
        {"source_id": "book-other"},
        config_path=config_path,
        builder_factory=lambda config: (_ for _ in ()).throw(AssertionError("must not build")),
    )
    assert result["status"] == "error"
    assert "not present in the book-ingestion queue" in result["error"]


def test_report_path_cannot_escape_reports_dir(tmp_path):
    _config, config_path = _allowed_book_config(tmp_path)
    result = handle_graph_build_book(
        {
            "source_id": ALLOWED_BOOK_SOURCE_ID,
            "report_out": str(tmp_path / "outside.json"),
        },
        config_path=config_path,
        builder_factory=_RecordingBuilder,
    )
    assert result["status"] == "error"
    assert "graph reports directory" in result["error"]


def test_provenance_includes_quote_chunk_point_and_confidence():
    app = _App()
    packet = handle_graph_retrieve(
        app,
        {"query": "supported claim"},
        graph_client=_Graph(rows=[SUPPORTED_ROW]),
        environ={"HERMES_GRAPH_ENABLED": "true"},
    )
    assert packet["claims"][0]["id"] == "claim-1"
    assert packet["claims"][0]["claim_basis"] == "author-framework"
    assert packet["claims"][0]["verification_status"] == "unverified"
    prov = packet["provenance"][0]
    assert prov["quote"] == "A short quote."
    assert prov["chunk_id"] == "memory-chunk"
    assert prov["qdrant_point_id"] == "point-1"
    assert prov["confidence"] == 0.8
    assert prov["source_id"] == ALLOWED_BOOK_SOURCE_ID


def test_low_confidence_and_unsupported_rows_are_excluded():
    app = _App()
    rows = [
        {**SUPPORTED_ROW, "claim_id": "low", "claim_confidence": 0.2},
        {**SUPPORTED_ROW, "claim_id": "no-evidence", "evidence_id": None, "evidence_quote": None},
        {**SUPPORTED_ROW, "claim_id": "bad-status", "claim_status": "unsupported"},
        SUPPORTED_ROW,
    ]
    packet = GraphRetrievalAdapter(app, _Graph(rows=rows)).retrieve("supported claim")
    assert [claim["id"] for claim in packet["claims"]] == ["claim-1"]
    assert packet["result_counts"]["excluded"] == 3


def test_maintenance_is_read_only_and_degrades_without_neo4j(tmp_path):
    _config, config_path = _allowed_book_config(tmp_path)
    result = dispatch_graph_tool(
        "graph_maintenance",
        {},
        config_path=config_path,
        environ={"HERMES_GRAPH_ENABLED": "true"},
        neo4j_client_factory=lambda _c: (_ for _ in ()).throw(ConnectionError("down")),
    )
    assert result["status"] == "degraded"
    assert result["write_mode"] == "read"
    assert result["output_path"] is None
    assert result["counts"]["duplicate_entities"] == 0


def test_maintenance_writes_report_without_merging(tmp_path):
    _config, config_path = _allowed_book_config(tmp_path)

    class Client:
        def health(self):
            return True

        def execute(self, query, parameters=None):
            if "duplicate" in query.lower() or "canonical_name" in query:
                return [{"summary": "Duplicate"}]
            return []

    result = dispatch_graph_tool(
        "graph_maintenance",
        {},
        config_path=config_path,
        environ={"HERMES_GRAPH_ENABLED": "true"},
        neo4j_client_factory=lambda _c: Client(),
    )
    assert result["status"] == "reported"
    assert result["auto_merged"] is False
    assert result["notes_rewritten"] is False
    text = Path(result["output_path"]).read_text(encoding="utf-8")
    assert "Duplicate Entities" in text
    assert result["counts"]["duplicate_entities"] == 1


def test_policy_ingest_remains_staged_and_review_is_exposed():
    ingest = dispatch_graph_tool("graph_policy_ingest", {"path": "04_SYSTEM/policies"})
    assert ingest["status"] == "not_activated"
    names = {schema["name"] for schema in openai_graph_tool_schemas()}
    assert names == {"graph_retrieve", "graph_build_book", "graph_promote_book", "graph_maintenance", "graph_review"}


def test_provider_exposes_graph_tools_and_retrieve_degrades(tmp_path, monkeypatch):
    from hermes_memory_os.provider import HermesMemoryOSProvider

    monkeypatch.delenv("HERMES_GRAPH_ENABLED", raising=False)
    provider = HermesMemoryOSProvider()
    provider.initialize({"data_dir": str(tmp_path)})
    names = {schema["name"] for schema in provider.get_tool_schemas()}
    assert {"graph_retrieve", "graph_build_book", "graph_promote_book", "graph_maintenance", "graph_review"} <= names
    packet = provider.handle_tool_call("graph_retrieve", {"query": "anything"})
    assert packet["graph_enabled"] is False
    assert "graph_disabled" in packet["review_warnings"]
    assert packet["graph_hits"] == []
