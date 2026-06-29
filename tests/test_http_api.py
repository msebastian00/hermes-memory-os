from fastapi.testclient import TestClient

from hermes_memory_os import http_api
from hermes_memory_os.http_api import create_app
from hermes_memory_os.http_models import AdapterSettings


def _client(tmp_path, *, api_key: str = "") -> TestClient:
    settings = AdapterSettings(data_dir=str(tmp_path / "memory"), api_key=api_key)
    return TestClient(create_app(settings))


def _auth(api_key: str = "secret") -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def test_health_reports_safe_ready_state(tmp_path):
    client = _client(tmp_path)

    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["storage_ready"] is True
    assert data["retrieval_ready"] is True
    assert data["candidate_ready"] is True
    assert "sqlite" not in str(data).lower()
    assert str(tmp_path) not in str(data)


def test_health_reports_missing_configuration_without_paths(monkeypatch):
    monkeypatch.delenv("HERMES_MEMORY_HOME", raising=False)
    client = TestClient(create_app(AdapterSettings()))

    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert data["degraded"] is True
    assert data["degraded_reasons"]
    assert "HERMES_MEMORY_HOME" not in str(data)


def test_health_retries_failed_startup_and_recovers(tmp_path, monkeypatch):
    real_memory_app = http_api.MemoryApp
    attempts = {"count": 0}

    class FlakyMemoryApp:
        @classmethod
        def from_config(cls, *args, **kwargs):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("qdrant_unavailable")
            return real_memory_app.from_config(*args, **kwargs)

    monkeypatch.setattr(http_api, "MemoryApp", FlakyMemoryApp)
    settings = AdapterSettings(data_dir=str(tmp_path / "memory"), retry_interval_seconds=0)
    app = create_app(settings)
    assert app.state.memory_app is None

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["storage_ready"] is True
    assert attempts["count"] == 2


def test_auth_required_for_v1_routes(tmp_path):
    client = _client(tmp_path, api_key="secret")

    unauthenticated = client.post("/v1/search", json={"query": "x"})
    authenticated = client.post("/v1/search", headers=_auth(), json={"query": "x"})

    assert unauthenticated.status_code == 401
    assert authenticated.status_code == 200


def test_search_returns_durable_memory_results(tmp_path):
    client = _client(tmp_path, api_key="secret")
    app = client.app.state.memory_app
    app.add_memory(
        memory_type="fact",
        scope="system",
        title="Reachy Memory OS",
        summary="Reachy should call Memory OS directly for fast recall.",
        canonical_text="Reachy should call Memory OS directly for fast recall.",
        tags=["reachy"],
        entities=["Reachy"],
    )

    response = client.post(
        "/v1/search",
        headers=_auth(),
        json={
            "query": "Reachy direct recall",
            "source_types": ["memory"],
            "limit": 5,
            "mode": "recall",
            "context": {"client": "reachy", "db_path": "/tmp/hidden.sqlite"},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["results"]
    result = data["results"][0]
    assert result["kind"] == "durable_memory"
    assert result["source_type"] == "memory"
    assert "fast recall" in result["summary"]
    assert "db_path" not in str(data)
    assert data["latency_ms"] >= 0


def test_search_rejects_bad_requests_and_forbidden_fields(tmp_path):
    client = _client(tmp_path)

    assert client.post("/v1/search", json={"query": ""}).status_code == 400
    assert client.post("/v1/search", json={"query": "x", "mode": "bad"}).status_code == 400
    assert client.post("/v1/search", json={"query": "x", "voiceprint": [1]}).status_code == 400


def test_search_source_type_filter_returns_source_chunks(tmp_path):
    client = _client(tmp_path)
    app = client.app.state.memory_app
    app.store.upsert_source_file(
        source_path="/books/reachy.txt",
        source_type="book",
        title="Reachy Book",
        content="Chapter 1\n\nReachy retrieves source chunks from Memory OS.",
        chunks=[{"chapter": "Chapter 1", "text": "Reachy retrieves source chunks from Memory OS."}],
    )

    response = client.post(
        "/v1/search",
        json={"query": "source chunks", "source_types": ["book"], "limit": 5},
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["kind"] == "source_chunk"
    assert result["source_type"] == "book"
    assert result["location"]["source_id"]
    assert result["location"]["chunk_id"]


def test_adjacent_chunks_returns_same_source_neighbors(tmp_path):
    client = _client(tmp_path)
    app = client.app.state.memory_app
    source_id, _created = app.store.upsert_source_file(
        source_path="/books/adjacent.txt",
        source_type="book",
        title="Adjacent",
        content="one two three",
        chunks=[
            {"chapter": "One", "text": "First memory chunk."},
            {"chapter": "Two", "text": "Second memory chunk."},
            {"chapter": "Three", "text": "Third memory chunk."},
        ],
    )
    with app.store.connection() as conn:
        first = conn.execute(
            "SELECT id FROM source_chunks WHERE source_id=? AND chunk_index=0",
            (source_id,),
        ).fetchone()

    response = client.post(
        "/v1/sources/chunks",
        json={"source_id": source_id, "chunk_id": first["id"], "direction": "after", "limit": 1},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["results"][0]["summary"] == "Second memory chunk."
    assert data["results"][0]["location"]["source_id"] == source_id


def test_adjacent_chunks_invalid_metadata_returns_suppressible_reason(tmp_path):
    client = _client(tmp_path)

    response = client.post(
        "/v1/sources/chunks",
        json={"source_id": "src_missing", "chunk_id": "chk_missing", "direction": "after"},
    )

    assert response.status_code == 200
    assert response.json()["results"] == []
    assert response.json()["degraded_reasons"] == ["adjacent_chunks_unavailable"]


def test_candidate_submission_stages_review_candidate(tmp_path):
    client = _client(tmp_path, api_key="secret")

    response = client.post(
        "/v1/candidates",
        headers=_auth(),
        json={
            "candidate_id": "reachy-1",
            "kind": "preference",
            "content": "Mike prefers direct Memory OS recall.",
            "source_text": "Remember that I prefer direct Memory OS recall.",
            "confidence": 0.82,
            "session_id": "s1",
            "turn_id": "t1",
            "speaker": {"display_name": "Mike", "trusted": True},
            "source": "reachy",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] is True
    assert data["candidate_id"].startswith("cand_")
    assert data["status"] == "pending_review"

    candidates = client.app.state.memory_app.store.list_extraction_candidates()
    assert candidates[0]["summary"] == "Mike prefers direct Memory OS recall."
    assert candidates[0]["entities"] == ["Mike"]


def test_candidate_submission_rejects_forbidden_payload_without_persisting(tmp_path):
    client = _client(tmp_path)

    response = client.post(
        "/v1/candidates",
        json={
            "candidate_id": "bad",
            "kind": "semantic",
            "content": "Unsafe",
            "voiceprint": [0.1, 0.2],
        },
    )

    assert response.status_code == 200
    assert response.json()["accepted"] is False
    assert response.json()["reason"] == "forbidden_field"
    assert client.app.state.memory_app.store.list_extraction_candidates() == []
