"""Application wiring."""

from __future__ import annotations

from pathlib import Path

from .config import MemoryConfig, load_config
from .db.store import MemoryStore
from .qdrant import QdrantClient
from .retrieval.retriever import Retriever


class MemoryApp:
    """Convenience object holding configured services."""

    def __init__(self, config: MemoryConfig):
        self.config = config
        self.store = MemoryStore(config.sqlite_path)
        self.retriever = Retriever(self.store, config.retrieval)

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
            "vault_dir_exists": self.config.vault_dir.exists(),
            "sqlite_exists": self.config.sqlite_path.exists(),
            "logs_dir_exists": self.config.logs_dir.exists(),
            "cloud_allowed": self.config.raw.get("privacy", {}).get("cloud_allowed") is True,
            "wiki_paths": [str(path) for path in self.config.wiki_paths],
        }
        if self.config.qdrant.get("enabled") is True:
            status["qdrant_reachable"] = QdrantClient(self.config.qdrant["url"]).health()
        return status

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
