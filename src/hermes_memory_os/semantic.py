"""Semantic indexing into Qdrant."""

from __future__ import annotations

import uuid
from typing import Any

from hermes_memory_os.db.store import DEFAULT_CHUNKING_VERSION, MemoryStore, format_source_citation
from hermes_memory_os.embeddings import Embedder
from hermes_memory_os.qdrant import QdrantClient


class SemanticIndexer:
    """Indexes source chunks and durable memories into Qdrant."""

    def __init__(
        self,
        *,
        store: MemoryStore,
        embedder: Embedder,
        qdrant: QdrantClient,
        collections: dict[str, str],
        embedding_provider: str,
        embedding_model: str,
        chunking_version: str = DEFAULT_CHUNKING_VERSION,
    ):
        self.store = store
        self.embedder = embedder
        self.qdrant = qdrant
        self.collections = collections
        self.embedding_provider = embedding_provider
        self.embedding_model = embedding_model
        self.chunking_version = chunking_version

    def index_pending_source_chunks(self, *, limit: int = 100) -> dict[str, int]:
        chunks = self.store.list_chunks_needing_index(
            embedding_provider=self.embedding_provider,
            embedding_model=self.embedding_model,
            chunking_version=self.chunking_version,
            limit=limit,
        )
        indexed = 0
        failed = 0
        collection = self.collections.get("sources") or self.collections.get("wiki") or "hermes_sources"
        for chunk in chunks:
            try:
                point_id = source_chunk_point_id(chunk)
                vector = self.embedder.embed(chunk["text"])
                payload = source_chunk_payload(chunk)
                payload["embedding_provider"] = self.embedding_provider
                payload["embedding_model"] = self.embedding_model
                self.qdrant.upsert_point(
                    collection,
                    point_id,
                    vector,
                    payload,
                )
                self.store.mark_source_chunk_indexed(
                    chunk["id"],
                    qdrant_point_id=point_id,
                    embedding_provider=self.embedding_provider,
                    embedding_model=self.embedding_model,
                    chunking_version=self.chunking_version,
                )
                indexed += 1
            except Exception:
                failed += 1
        return {"semantic_indexed": indexed, "semantic_failed": failed}

    def index_memory(self, memory_id: str) -> dict[str, int]:
        memory = self.store.get_memory(memory_id)
        if memory is None or memory["status"] != "active":
            return {"semantic_indexed": 0, "semantic_failed": 1}
        collection = self.collections.get("memories", "hermes_memories")
        try:
            point_id = memory_point_id(memory)
            vector = self.embedder.embed(memory["canonical_text"])
            self.qdrant.upsert_point(
                collection,
                point_id,
                vector,
                memory_payload(memory),
            )
            self.store.save_memory_qdrant_point(
                memory_id,
                collection=collection,
                point_id=point_id,
            )
            return {"semantic_indexed": 1, "semantic_failed": 0}
        except Exception:
            return {"semantic_indexed": 0, "semantic_failed": 1}


class SemanticSearchBackend:
    """Semantic retrieval over Qdrant with SQLite hydration."""

    def __init__(
        self,
        *,
        store: MemoryStore,
        embedder: Embedder,
        qdrant: QdrantClient,
        collections: dict[str, str],
    ):
        self.store = store
        self.embedder = embedder
        self.qdrant = qdrant
        self.collections = collections

    def search(
        self,
        query: str,
        *,
        limit: int,
        source_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        vector = self.embedder.embed(query)
        results: list[dict[str, Any]] = []
        if not source_types:
            memory_collection = self.collections.get("memories")
            if memory_collection:
                results.extend(
                    self._search_collection(
                        memory_collection,
                        vector,
                        limit=limit,
                        kind="memory",
                    )
                )
        source_collection = self.collections.get("sources") or self.collections.get("wiki")
        if source_collection:
            results.extend(
                self._search_collection(
                    source_collection,
                    vector,
                    limit=limit,
                    kind="source_chunk",
                    query_filter=source_type_filter(source_types),
                )
            )
        return sorted(results, key=lambda item: item.get("semantic_score", 0.0), reverse=True)[:limit]

    def _search_collection(
        self,
        collection: str,
        vector: list[float],
        *,
        limit: int,
        kind: str,
        query_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        raw_results = self.qdrant.search(
            collection,
            vector,
            limit=limit,
            query_filter=query_filter,
        )
        hydrated = []
        for raw in raw_results:
            payload = raw.get("payload") or {}
            score = _semantic_score(raw.get("score", 0.0))
            if kind == "memory":
                item = self.store.get_memory_result(payload.get("memory_id", ""))
            else:
                item = self.store.get_source_chunk_result(payload.get("chunk_id", ""))
            if item is None:
                continue
            item["semantic_score"] = score
            item["qdrant_score"] = raw.get("score", 0.0)
            hydrated.append(item)
        return hydrated


def source_type_filter(source_types: list[str] | None) -> dict[str, Any] | None:
    if not source_types:
        return None
    if len(source_types) == 1:
        return {"must": [{"key": "source_type", "match": {"value": source_types[0]}}]}
    return {"must": [{"key": "source_type", "match": {"any": source_types}}]}


def source_chunk_point_id(chunk: dict[str, Any]) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"hermes-source-chunk:{chunk['id']}:{chunk['content_hash']}"))


def memory_point_id(memory: dict[str, Any]) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"hermes-memory:{memory['id']}:{memory['updated_at']}"))


def source_chunk_payload(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "source_chunk",
        "chunk_id": chunk["id"],
        "source_id": chunk["source_id"],
        "source_path": chunk["source_path"],
        "source_type": chunk["source_type"],
        "title": chunk["source_title"],
        "heading": chunk.get("heading"),
        "chapter": chunk.get("chapter"),
        "section": chunk.get("section"),
        "page_start": chunk.get("page_start"),
        "page_end": chunk.get("page_end"),
        "timestamp_start": chunk.get("timestamp_start"),
        "timestamp_end": chunk.get("timestamp_end"),
        "speaker": chunk.get("speaker"),
        "content_hash": chunk["content_hash"],
        "chunking_version": chunk.get("chunking_version"),
        "embedding_provider": chunk.get("embedding_provider"),
        "embedding_model": chunk.get("embedding_model"),
        "citation": format_source_citation(chunk),
        "text_excerpt": chunk["text"][:1000],
    }


def memory_payload(memory: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "memory",
        "memory_id": memory["id"],
        "memory_type": memory["memory_type"],
        "scope": memory["scope"],
        "title": memory.get("title"),
        "summary": memory["summary"],
        "entities": memory.get("entities", []),
        "tags": memory.get("tags", []),
        "confidence": memory.get("confidence"),
        "trust_score": memory.get("trust_score"),
        "created_at": memory["created_at"],
        "updated_at": memory["updated_at"],
        "text_excerpt": memory["canonical_text"][:1000],
    }


def _semantic_score(score: float) -> float:
    return max(0.0, min(1.0, float(score)))
