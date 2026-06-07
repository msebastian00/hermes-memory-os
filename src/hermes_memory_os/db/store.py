"""SQLite-backed store operations."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from hermes_memory_os.db.connection import connect, initialize_schema
from hermes_memory_os.utils import content_hash, dumps, new_id, now_iso

BLOCKED_RUNTIME_METADATA = {
    "speaker_confidence",
    "wake_state",
    "listening_state",
    "body_state",
    "camera_context",
    "room_awareness",
    "room_context",
    "latency_budget",
    "latency_budget_ms",
    "device_state",
    "robot_state",
}

ALLOWED_PROVENANCE_METADATA = {
    "client",
    "conversation_id",
    "session_id",
    "source_ref",
    "source",
    "tags",
}


class MemoryStore:
    """Durable SQLite store."""

    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path

    def init(self) -> None:
        initialize_schema(self.sqlite_path)

    def connection(self) -> sqlite3.Connection:
        return connect(self.sqlite_path)

    def add_raw_event(
        self,
        content: str,
        *,
        source: str = "chat",
        role: str | None = None,
        client: str | None = None,
        conversation_id: str | None = None,
        source_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        event_id = new_id("evt")
        clean_metadata = sanitize_metadata(metadata or {})
        created_at = now_iso()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO raw_events (
                  id, source, client, conversation_id, source_ref, role, content,
                  content_hash, created_at, metadata_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
                """,
                (
                    event_id,
                    source,
                    client,
                    conversation_id,
                    source_ref,
                    role,
                    content,
                    content_hash(content),
                    created_at,
                    dumps(clean_metadata),
                ),
            )
        return event_id

    def sync_turn(
        self,
        user_message: str,
        assistant_message: str,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        metadata = metadata or {}
        client = metadata.get("client")
        conversation_id = metadata.get("conversation_id") or metadata.get("session_id")
        source_ref = metadata.get("source_ref")
        user_id = self.add_raw_event(
            user_message,
            source="chat",
            role="user",
            client=client,
            conversation_id=conversation_id,
            source_ref=source_ref,
            metadata=metadata,
        )
        assistant_id = self.add_raw_event(
            assistant_message,
            source="chat",
            role="assistant",
            client=client,
            conversation_id=conversation_id,
            source_ref=source_ref,
            metadata=metadata,
        )
        return user_id, assistant_id

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
    ) -> str:
        memory_id = new_id("mem")
        created_at = now_iso()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO memories (
                  id, memory_type, scope, title, summary, canonical_text,
                  source_event_ids, source_paths, entities_json, tags_json,
                  confidence, trust_score, created_at, updated_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
                """,
                (
                    memory_id,
                    memory_type,
                    scope,
                    title,
                    summary,
                    canonical_text,
                    dumps(source_event_ids or []),
                    dumps(source_paths or []),
                    dumps(entities or []),
                    dumps(tags or []),
                    confidence,
                    trust_score,
                    created_at,
                    created_at,
                ),
            )
            conn.execute(
                "INSERT INTO memories_fts(memory_id, title, summary, canonical_text) VALUES (?, ?, ?, ?)",
                (memory_id, title or "", summary, canonical_text),
            )
        return memory_id

    def archive_memory(self, memory_id: str, reason: str | None = None) -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE memories SET status='archived', updated_at=? WHERE id=?",
                (now_iso(), memory_id),
            )
            if reason:
                conn.execute(
                    """
                    INSERT INTO feedback (id, memory_id, feedback_type, details, created_at)
                    VALUES (?, ?, 'archived', ?, ?)
                    """,
                    (new_id("fb"), memory_id, reason, now_iso()),
                )

    def upsert_source_file(
        self,
        *,
        source_path: str,
        source_type: str,
        title: str,
        content: str,
        chunks: list[dict[str, Any]],
    ) -> tuple[str, bool]:
        file_hash = content_hash(content)
        with self.connection() as conn:
            existing = conn.execute(
                "SELECT id FROM sources WHERE source_path=? AND content_hash=?",
                (source_path, file_hash),
            ).fetchone()
            if existing:
                return existing["id"], False

            source_id = new_id("src")
            conn.execute(
                """
                INSERT INTO sources (
                  id, title, source_type, source_path, ingested_at, status,
                  metadata_json, content_hash
                ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    source_id,
                    title,
                    source_type,
                    source_path,
                    now_iso(),
                    dumps({}),
                    file_hash,
                ),
            )
            for index, chunk in enumerate(chunks):
                chunk_id = new_id("chk")
                text = chunk["text"]
                heading = chunk.get("heading")
                conn.execute(
                    """
                    INSERT INTO source_chunks (
                      id, source_id, chunk_index, heading, text, content_hash, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk_id,
                        source_id,
                        index,
                        heading,
                        text,
                        content_hash(text),
                        now_iso(),
                    ),
                )
                conn.execute(
                    "INSERT INTO source_chunks_fts(chunk_id, source_id, heading, text) VALUES (?, ?, ?, ?)",
                    (chunk_id, source_id, heading or "", text),
                )
        return source_id, True

    def search_keyword(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        started = time.perf_counter()
        results: list[dict[str, Any]] = []
        with self.connection() as conn:
            memory_rows = conn.execute(
                """
                SELECT m.*, bm25(memories_fts) AS rank
                FROM memories_fts
                JOIN memories m ON m.id = memories_fts.memory_id
                WHERE memories_fts MATCH ? AND m.status='active'
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()
            for row in memory_rows:
                results.append(
                    {
                        "id": row["id"],
                        "kind": "memory",
                        "title": row["title"],
                        "summary": row["summary"],
                        "text": row["canonical_text"],
                        "source": row["source_paths"],
                        "keyword_score": _rank_to_score(row["rank"]),
                        "trust_score": row["trust_score"],
                    }
                )

            remaining = max(limit - len(results), 0)
            if remaining:
                chunk_rows = conn.execute(
                    """
                    SELECT sc.*, s.title AS source_title, s.source_path, bm25(source_chunks_fts) AS rank
                    FROM source_chunks_fts
                    JOIN source_chunks sc ON sc.id = source_chunks_fts.chunk_id
                    JOIN sources s ON s.id = sc.source_id
                    WHERE source_chunks_fts MATCH ? AND s.status='active'
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (query, remaining),
                ).fetchall()
                for row in chunk_rows:
                    results.append(
                        {
                            "id": row["id"],
                            "kind": "source_chunk",
                            "title": row["heading"] or row["source_title"],
                            "summary": row["text"][:240],
                            "text": row["text"],
                            "source": row["source_path"],
                            "keyword_score": _rank_to_score(row["rank"]),
                            "trust_score": 0.5,
                        }
                    )

        latency_ms = int((time.perf_counter() - started) * 1000)
        self.log_retrieval(query, results, latency_ms, suppressed=False)
        return results

    def log_retrieval(
        self,
        query: str,
        results: list[dict[str, Any]],
        latency_ms: int,
        *,
        context: dict[str, Any] | None = None,
        suppressed: bool = False,
    ) -> str:
        retrieval_id = new_id("ret")
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO retrieval_log (
                  id, query, query_context_json, retrieved_ids_json, scores_json,
                  created_at, latency_ms, result_count, suppressed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    retrieval_id,
                    query,
                    dumps(sanitize_metadata(context or {})),
                    dumps([item["id"] for item in results]),
                    dumps({item["id"]: item.get("final_score") for item in results}),
                    now_iso(),
                    latency_ms,
                    len(results),
                    1 if suppressed else 0,
                ),
            )
        return retrieval_id

    def log_injection(self, memory_ids: list[str], injected_text: str, turn_id: str | None = None) -> str:
        injection_id = new_id("inj")
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO injection_log (
                  id, turn_id, memory_ids_json, injected_text, token_estimate, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    injection_id,
                    turn_id,
                    dumps(memory_ids),
                    injected_text,
                    max(1, len(injected_text.split())),
                    now_iso(),
                ),
            )
        return injection_id

    def log_agent_learning_event(
        self,
        *,
        event_type: str,
        summary: str,
        evidence: dict[str, Any] | None = None,
        candidate_change: str | None = None,
    ) -> str:
        event_id = new_id("learn")
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_learning_events (
                  id, event_type, summary, evidence_json, candidate_change, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 'pending_review', ?)
                """,
                (event_id, event_type, summary, dumps(evidence or {}), candidate_change, now_iso()),
            )
        return event_id


def sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Keep provenance metadata and drop Reachy/runtime control state."""

    clean = {}
    for key, value in metadata.items():
        if key in BLOCKED_RUNTIME_METADATA:
            continue
        if key in ALLOWED_PROVENANCE_METADATA or key.startswith("tag_"):
            clean[key] = value
    return clean


def _rank_to_score(rank: float) -> float:
    # SQLite bm25 is lower-is-better and often negative. This maps it to a compact positive score.
    return max(0.0, min(1.0, 1.0 / (1.0 + abs(rank))))
