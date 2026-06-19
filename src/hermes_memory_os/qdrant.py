"""Minimal Qdrant HTTP client.

The implementation intentionally uses HTTP instead of requiring qdrant-client for the MVP.
"""

from __future__ import annotations

from typing import Any

import requests


class QdrantClient:
    def __init__(self, url: str, timeout: int = 10):
        self.url = url.rstrip("/")
        self.timeout = timeout

    def health(self) -> bool:
        try:
            response = requests.get(f"{self.url}/", timeout=self.timeout)
            return response.status_code < 500
        except requests.RequestException:
            return False

    def collection_exists(self, name: str) -> bool:
        try:
            response = requests.get(f"{self.url}/collections/{name}", timeout=self.timeout)
            if response.status_code == 404:
                return False
            response.raise_for_status()
            return True
        except requests.RequestException:
            return False

    def collection_status(self, name: str) -> dict[str, Any]:
        response = requests.get(f"{self.url}/collections/{name}", timeout=self.timeout)
        response.raise_for_status()
        return response.json().get("result", {})

    def ensure_collection(self, name: str, vector_size: int, distance: str = "Cosine") -> None:
        if self.collection_exists(name):
            return
        response = requests.put(
            f"{self.url}/collections/{name}",
            json={"vectors": {"size": vector_size, "distance": distance}},
            timeout=self.timeout,
        )
        if response.status_code == 409:
            return
        response.raise_for_status()

    def upsert_point(self, collection: str, point_id: str, vector: list[float], payload: dict[str, Any]) -> None:
        response = requests.put(
            f"{self.url}/collections/{collection}/points",
            json={"points": [{"id": point_id, "vector": vector, "payload": payload}]},
            timeout=self.timeout,
        )
        response.raise_for_status()

    def upsert_points(self, collection: str, points: list[dict[str, Any]]) -> None:
        response = requests.put(
            f"{self.url}/collections/{collection}/points",
            json={"points": points},
            timeout=self.timeout,
        )
        response.raise_for_status()

    def search(
        self,
        collection: str,
        vector: list[float],
        limit: int = 8,
        *,
        query_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        body: dict[str, Any] = {"vector": vector, "limit": limit, "with_payload": True}
        if query_filter:
            body["filter"] = query_filter
        response = requests.post(
            f"{self.url}/collections/{collection}/points/search",
            json=body,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json().get("result", [])
