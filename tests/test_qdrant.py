import requests

from hermes_memory_os.qdrant import QdrantClient


class FakeResponse:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")

    def json(self) -> dict:
        return {"result": {}}


def test_ensure_collection_skips_existing_collection(monkeypatch):
    calls = []

    def fake_get(url, timeout):
        calls.append(("get", url, timeout))
        return FakeResponse(200)

    def fake_put(url, json, timeout):
        calls.append(("put", url, json, timeout))
        return FakeResponse(200)

    monkeypatch.setattr("hermes_memory_os.qdrant.requests.get", fake_get)
    monkeypatch.setattr("hermes_memory_os.qdrant.requests.put", fake_put)

    QdrantClient("http://qdrant.test").ensure_collection("hermes_memories", 768)

    assert calls == [("get", "http://qdrant.test/collections/hermes_memories", 10)]


def test_ensure_collection_treats_conflict_as_existing(monkeypatch):
    calls = []

    def fake_get(url, timeout):
        calls.append(("get", url, timeout))
        return FakeResponse(404)

    def fake_put(url, json, timeout):
        calls.append(("put", url, json, timeout))
        return FakeResponse(409)

    monkeypatch.setattr("hermes_memory_os.qdrant.requests.get", fake_get)
    monkeypatch.setattr("hermes_memory_os.qdrant.requests.put", fake_put)

    QdrantClient("http://qdrant.test").ensure_collection("hermes_memories", 768)

    assert calls == [
        ("get", "http://qdrant.test/collections/hermes_memories", 10),
        (
            "put",
            "http://qdrant.test/collections/hermes_memories",
            {"vectors": {"size": 768, "distance": "Cosine"}},
            10,
        ),
    ]
