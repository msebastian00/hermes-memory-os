"""Application wiring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import MemoryConfig, load_config
from .db.store import MemoryStore
from .embeddings import build_embedder
from .ingest.sources import ingest_paths
from .qdrant import QdrantClient
from .retrieval.retriever import Retriever
from .semantic import SemanticIndexer, SemanticSearchBackend


class MemoryApp:
    """Convenience object holding configured services."""

    def __init__(self, config: MemoryConfig):
        self.config = config
        self.store = MemoryStore(config.sqlite_path)
        self.semantic_indexer: SemanticIndexer | None = None
        semantic_search: SemanticSearchBackend | None = None
        if self.semantic_enabled:
            embedder = build_embedder(config.embeddings)
            qdrant = QdrantClient(config.qdrant["url"])
            self.semantic_indexer = SemanticIndexer(
                store=self.store,
                embedder=embedder,
                qdrant=qdrant,
                collections=config.qdrant.get("collections", {}),
                embedding_provider=config.embeddings.get("provider", "none"),
                embedding_model=config.embeddings.get("model", ""),
            )
            semantic_search = SemanticSearchBackend(
                store=self.store,
                embedder=embedder,
                qdrant=qdrant,
                collections=config.qdrant.get("collections", {}),
            )
        self.retriever = Retriever(self.store, config.retrieval, semantic_backend=semantic_search)

    @property
    def semantic_enabled(self) -> bool:
        return (
            self.config.qdrant.get("enabled") is True
            and self.config.embeddings.get("provider", "none") != "none"
        )

    @classmethod
    def from_config(cls, config_path: str | Path | None = None, data_dir: str | Path | None = None) -> "MemoryApp":
        return cls(load_config(config_path=config_path, data_dir=data_dir))

    def init_storage(self) -> None:
        self.config.base_dir.mkdir(parents=True, exist_ok=True)
        self.config.vault_dir.mkdir(parents=True, exist_ok=True)
        self.config.logs_dir.mkdir(parents=True, exist_ok=True)
        self.config.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.store.init()
        self._init_qdrant_if_enabled()

    def doctor(self) -> dict[str, object]:
        status = {
            "base_dir": str(self.config.base_dir),
            "base_dir_exists": self.config.base_dir.exists(),
            "vault_dir": str(self.config.vault_dir),
            "vault_dir_exists": self.config.vault_dir.exists(),
            "sqlite_path": str(self.config.sqlite_path),
            "sqlite_exists": self.config.sqlite_path.exists(),
            "logs_dir": str(self.config.logs_dir),
            "logs_dir_exists": self.config.logs_dir.exists(),
            "cloud_allowed": self.config.raw.get("privacy", {}).get("cloud_allowed") is True,
            "wiki_paths": [str(path) for path in self.config.wiki_paths],
            "wiki_path_status": [
                {"path": str(path), "exists": path.exists()}
                for path in self.config.wiki_paths
            ],
            "embedding_provider": self.config.embeddings.get("provider", "none"),
            "embedding_model": self.config.embeddings.get("model"),
            "embedding_dimension": self.config.embeddings.get("dimension"),
            "semantic_enabled": self.semantic_enabled,
            "qdrant_enabled": self.config.qdrant.get("enabled") is True,
            "qdrant_url": self.config.qdrant.get("url"),
        }
        if self.config.embeddings.get("provider", "none") != "none":
            status["embedding_reachable"] = build_embedder(self.config.embeddings).health()
        if self.config.qdrant.get("enabled") is True:
            client = QdrantClient(self.config.qdrant["url"])
            status["qdrant_reachable"] = client.health()
            status["qdrant_collections"] = {
                role: {
                    "name": name,
                    "exists": client.collection_exists(name),
                }
                for role, name in self.config.qdrant.get("collections", {}).items()
            }
        return status

    def ingest_sources(
        self,
        paths: list[Path],
        *,
        source_type: str | None = None,
        reindex: bool = False,
    ) -> dict[str, int]:
        result = ingest_paths(
            self.store,
            paths,
            source_type=source_type,
            reindex=reindex,
        )
        if self.semantic_indexer is not None:
            result.update(self.semantic_indexer.index_pending_source_chunks())
        return result

    def add_memory(
        self,
        *,
        memory_type: str,
        scope: str,
        title: str | None,
        summary: str,
        canonical_text: str,
        source_event_ids: list[str] | None = None,
        source_paths: list[str] | None = None,
        entities: list[str] | None = None,
        tags: list[str] | None = None,
        confidence: float = 0.5,
        trust_score: float = 0.5,
    ) -> dict[str, Any]:
        memory_id = self.store.add_memory(
            memory_type=memory_type,
            scope=scope,
            title=title,
            summary=summary,
            canonical_text=canonical_text,
            source_event_ids=source_event_ids,
            source_paths=source_paths,
            entities=entities,
            tags=tags,
            confidence=confidence,
            trust_score=trust_score,
        )
        result: dict[str, Any] = {"memory_id": memory_id}
        if self.semantic_indexer is not None:
            result.update(self.semantic_indexer.index_memory(memory_id))
        return result

    def _init_qdrant_if_enabled(self) -> None:
        qdrant = self.config.qdrant
        if qdrant.get("enabled") is not True:
            return
        client = QdrantClient(qdrant["url"])
        for name in qdrant.get("collections", {}).values():
            client.ensure_collection(
                name,
                vector_size=int(qdrant.get("vector_size", 768)),
                distance=qdrant.get("distance", "Cosine"),
            )
