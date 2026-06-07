"""Embedding providers."""

from __future__ import annotations

import hashlib
from typing import Protocol

import requests


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]:
        """Return a vector embedding for text."""


class DisabledEmbedder:
    """Deterministic no-network embedder for local tests and keyword-only mode."""

    def __init__(self, dimension: int = 768):
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = []
        for index in range(self.dimension):
            byte = digest[index % len(digest)]
            values.append((byte / 255.0) - 0.5)
        return values


class OllamaEmbedder:
    """Ollama embedding provider."""

    def __init__(self, base_url: str, model: str, dimension: int = 768, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dimension = dimension
        self.timeout = timeout

    def embed(self, text: str) -> list[float]:
        response = requests.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": text},
            timeout=self.timeout,
        )
        response.raise_for_status()
        vector = response.json()["embedding"]
        if len(vector) != self.dimension:
            raise ValueError(f"Embedding dimension mismatch: expected {self.dimension}, got {len(vector)}")
        return vector


def build_embedder(config: dict) -> Embedder:
    provider = config.get("provider", "none")
    dimension = int(config.get("dimension", 768))
    if provider == "ollama":
        return OllamaEmbedder(
            base_url=config.get("base_url", "http://localhost:11434"),
            model=config.get("model", "nomic-embed-text"),
            dimension=dimension,
        )
    return DisabledEmbedder(dimension=dimension)
