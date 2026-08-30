"""Minimal Qdrant HTTP client."""

from __future__ import annotations

from typing import Any

import requests


class QdrantClient:
    def __init__(self, url: str, timeout: int = 10, api_key: str | None = None):
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key or ""

    def _request_kwargs(self) -> dict[str, Any]:
        if not self.api_key:
            return {"timeout": self.timeout}
        return {"timeout": self.timeout, "headers": {"api-key": self.api_key}}

    def health(self) -> bool:
        try:
            response = requests.get(f"{self.url}/", **self._request_kwargs())
            return response.status_code < 500
        except requests.RequestException:
            return False

    def collection_exists(self, name: str) -> bool:
        try:
            response = requests.get(f"{self.url}/collections/{name}", **self._request_kwargs())
            if response.status_code == 404:
                return False
            response.raise_for_status()
            return True
        except requests.RequestException:
            return False

    def collection_status(self, name: str) -> dict[str, Any]:
        response = requests.get(f"{self.url}/collections/{name}", **self._request_kwargs())
        response.raise_for_status()
        return response.json().get("result", {})

    def ensure_collection(self, name: str, vector_size: int, distance: str = "Cosine") -> None:
        if self.collection_exists(name):
            return
        response = requests.put(
            f"{self.url}/collections/{name}",
            json={"vectors": {"size": vector_size, "distance": distance}},
            **self._request_kwargs(),
        )
        if response.status_code == 409:
            return
        response.raise_for_status()

    def upsert_point(self, collection: str, point_id: str, vector: list[float], payload: dict[str, Any]) -> None:
        response = requests.put(
            f"{self.url}/collections/{collection}/points",
            json={"points": [{"id": point_id, "vector": vector, "payload": payload}]},
            **self._request_kwargs(),
        )
        response.raise_for_status()

    def upsert_points(self, collection: str, points: list[dict[str, Any]]) -> None:
        response = requests.put(
            f"{self.url}/collections/{collection}/points",
            json={"points": points},
            **self._request_kwargs(),
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
            **self._request_kwargs(),
        )
        response.raise_for_status()
        return response.json().get("result", [])
