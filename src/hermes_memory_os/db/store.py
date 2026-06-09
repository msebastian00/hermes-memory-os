"""SQLite-backed store operations."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from hermes_memory_os.db.connection import connect, initialize_schema
from hermes_memory_os.utils import content_hash, dumps, loads, new_id, now_iso

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
    "semantic_error",
    "semantic_fallback",
    "semantic_result_count",
}

DEFAULT_CHUNKING_VERSION = "v1"


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

    def get_memory(self, memory_id: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM memories WHERE id=?",
                (memory_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "memory_type": row["memory_type"],
            "scope": row["scope"],
            "title": row["title"],
            "summary": row["summary"],
            "canonical_text": row["canonical_text"],
            "source_event_ids": loads(row["source_event_ids"], []),
            "source_paths": loads(row["source_paths"], []),
            "entities": loads(row["entities_json"], []),
            "tags": loads(row["tags_json"], []),
            "confidence": row["confidence"],
            "trust_score": row["trust_score"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "status": row["status"],
            "qdrant_collection": row["qdrant_collection"],
            "qdrant_point_id": row["qdrant_point_id"],
        }

    def get_memory_result(self, memory_id: str) -> dict[str, Any] | None:
        memory = self.get_memory(memory_id)
        if memory is None or memory["status"] != "active":
            return None
        return {
            "id": memory["id"],
            "kind": "memory",
            "title": memory["title"],
            "summary": memory["summary"],
            "text": memory["canonical_text"],
            "source": memory["source_paths"],
            "trust_score": memory["trust_score"],
        }

    def list_memories(
        self,
        *,
        status: str = "active",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM memories
                WHERE status=?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (status, limit),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "memory_type": row["memory_type"],
                "scope": row["scope"],
                "title": row["title"],
                "summary": row["summary"],
                "canonical_text": row["canonical_text"],
                "entities": loads(row["entities_json"], []),
                "tags": loads(row["tags_json"], []),
                "confidence": row["confidence"],
                "trust_score": row["trust_score"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "status": row["status"],
            }
            for row in rows
        ]

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

    def save_memory_qdrant_point(
        self,
        memory_id: str,
        *,
        collection: str,
        point_id: str,
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE memories
                SET qdrant_collection=?, qdrant_point_id=?, updated_at=?
                WHERE id=?
                """,
                (collection, point_id, now_iso(), memory_id),
            )

    def save_source_chunk_qdrant_point(self, chunk_id: str, point_id: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE source_chunks SET qdrant_point_id=? WHERE id=?",
                (point_id, chunk_id),
            )

    def upsert_source_file(
        self,
        *,
        source_path: str,
        source_type: str,
        title: str,
        content: str,
        chunks: list[dict[str, Any]],
        source_metadata: dict[str, Any] | None = None,
        chunking_version: str = DEFAULT_CHUNKING_VERSION,
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
                    dumps(source_metadata or {}),
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
                      id, source_id, chunk_index, heading, chapter, section,
                      page_start, page_end, timestamp_start, timestamp_end, speaker,
                      text, summary, content_hash, metadata_json, chunking_version,
                      indexing_state, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                    """,
                    (
                        chunk_id,
                        source_id,
                        index,
                        heading,
                        chunk.get("chapter"),
                        chunk.get("section"),
                        chunk.get("page_start"),
                        chunk.get("page_end"),
                        chunk.get("timestamp_start"),
                        chunk.get("timestamp_end"),
                        chunk.get("speaker"),
                        text,
                        chunk.get("summary"),
                        content_hash(text),
                        dumps(chunk.get("metadata") or {}),
                        chunk.get("chunking_version") or chunking_version,
                        now_iso(),
                    ),
                )
                conn.execute(
                    "INSERT INTO source_chunks_fts(chunk_id, source_id, heading, text) VALUES (?, ?, ?, ?)",
                    (chunk_id, source_id, heading or "", text),
                )
        return source_id, True

    def list_chunks_needing_index(
        self,
        *,
        embedding_provider: str,
        embedding_model: str,
        chunking_version: str = DEFAULT_CHUNKING_VERSION,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT sc.*, s.title AS source_title, s.source_path, s.source_type
                FROM source_chunks sc
                JOIN sources s ON s.id = sc.source_id
                WHERE s.status='active'
                  AND (
                    sc.qdrant_point_id IS NULL
                    OR sc.indexing_state != 'indexed'
                    OR sc.chunking_version != ?
                    OR COALESCE(sc.embedding_provider, '') != ?
                    OR COALESCE(sc.embedding_model, '') != ?
                  )
                ORDER BY sc.created_at
                LIMIT ?
                """,
                (chunking_version, embedding_provider, embedding_model, limit),
            ).fetchall()
        return [_source_chunk_from_row(row) for row in rows]

    def mark_source_chunk_indexed(
        self,
        chunk_id: str,
        *,
        qdrant_point_id: str,
        embedding_provider: str,
        embedding_model: str,
        chunking_version: str = DEFAULT_CHUNKING_VERSION,
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE source_chunks
                SET qdrant_point_id=?, embedding_provider=?, embedding_model=?,
                    chunking_version=?, indexing_state='indexed'
                WHERE id=?
                """,
                (qdrant_point_id, embedding_provider, embedding_model, chunking_version, chunk_id),
            )

    def mark_source_chunks_for_reindex(
        self,
        *,
        source_id: str | None = None,
        source_type: str | None = None,
    ) -> int:
        clauses = ["id IN (SELECT sc.id FROM source_chunks sc JOIN sources s ON s.id = sc.source_id WHERE 1=1"]
        values: list[Any] = []
        if source_id:
            clauses.append("AND s.id=?")
            values.append(source_id)
        if source_type:
            clauses.append("AND s.source_type=?")
            values.append(source_type)
        clauses.append(")")
        with self.connection() as conn:
            cursor = conn.execute(
                f"""
                UPDATE source_chunks
                SET qdrant_point_id=NULL, embedding_provider=NULL, embedding_model=NULL,
                    indexing_state='pending'
                WHERE {' '.join(clauses)}
                """,
                values,
            )
            return cursor.rowcount

    def get_source_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT sc.*, s.title AS source_title, s.source_path, s.source_type
                FROM source_chunks sc
                JOIN sources s ON s.id = sc.source_id
                WHERE sc.id=? AND s.status='active'
                """,
                (chunk_id,),
            ).fetchone()
        if row is None:
            return None
        return _source_chunk_from_row(row)

    def get_source_chunk_result(self, chunk_id: str) -> dict[str, Any] | None:
        chunk = self.get_source_chunk(chunk_id)
        if chunk is None:
            return None
        return source_chunk_result_from_chunk(chunk)

    def create_extraction_candidate(
        self,
        *,
        source_event_ids: list[str],
        memory_type: str,
        scope: str,
        title: str | None,
        summary: str,
        canonical_text: str,
        entities: list[str] | None = None,
        tags: list[str] | None = None,
        confidence: float = 0.5,
        reason_to_save: str | None = None,
    ) -> str:
        candidate_id = new_id("cand")
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO extraction_candidates (
                  id, source_event_ids_json, memory_type, scope, title, summary,
                  canonical_text, entities_json, tags_json, confidence,
                  reason_to_save, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_review', ?)
                """,
                (
                    candidate_id,
                    dumps(source_event_ids),
                    memory_type,
                    scope,
                    title,
                    summary,
                    canonical_text,
                    dumps(entities or []),
                    dumps(tags or []),
                    confidence,
                    reason_to_save,
                    now_iso(),
                ),
            )
        return candidate_id

    def list_extraction_candidates(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        with self.connection() as conn:
            if status:
                rows = conn.execute(
                    """
                    SELECT * FROM extraction_candidates
                    WHERE status=?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM extraction_candidates
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [_candidate_from_row(row) for row in rows]

    def update_extraction_candidate(
        self,
        candidate_id: str,
        *,
        status: str | None = None,
        title: str | None = None,
        summary: str | None = None,
        canonical_text: str | None = None,
        confidence: float | None = None,
        reason_to_save: str | None = None,
    ) -> None:
        assignments: list[str] = []
        values: list[Any] = []
        for column, value in (
            ("status", status),
            ("title", title),
            ("summary", summary),
            ("canonical_text", canonical_text),
            ("confidence", confidence),
            ("reason_to_save", reason_to_save),
        ):
            if value is not None:
                assignments.append(f"{column}=?")
                values.append(value)

        if status and status != "pending_review":
            assignments.append("reviewed_at=?")
            values.append(now_iso())

        if not assignments:
            return

        values.append(candidate_id)
        with self.connection() as conn:
            conn.execute(
                f"UPDATE extraction_candidates SET {', '.join(assignments)} WHERE id=?",
                values,
            )

    def search_keyword(
        self,
        query: str,
        limit: int = 8,
        *,
        source_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        started = time.perf_counter()
        results: list[dict[str, Any]] = []
        with self.connection() as conn:
            if not source_types:
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
                source_filter_sql = ""
                params: list[Any] = [query]
                if source_types:
                    placeholders = ", ".join("?" for _ in source_types)
                    source_filter_sql = f" AND s.source_type IN ({placeholders})"
                    params.extend(source_types)
                params.append(remaining)
                chunk_rows = conn.execute(
                    f"""
                    SELECT sc.*, s.title AS source_title, s.source_path, s.source_type,
                           bm25(source_chunks_fts) AS rank
                    FROM source_chunks_fts
                    JOIN source_chunks sc ON sc.id = source_chunks_fts.chunk_id
                    JOIN sources s ON s.id = sc.source_id
                    WHERE source_chunks_fts MATCH ? AND s.status='active'
                    {source_filter_sql}
                    ORDER BY rank
                    LIMIT ?
                    """,
                    params,
                ).fetchall()
                for row in chunk_rows:
                    chunk = _source_chunk_from_row(row)
                    result = source_chunk_result_from_chunk(chunk)
                    result["keyword_score"] = _rank_to_score(row["rank"])
                    results.append(result)

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

    def list_recent_raw_events(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, source, client, conversation_id, source_ref, role,
                       content, created_at, metadata_json, status
                FROM raw_events
                WHERE status='active'
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "source": row["source"],
                "client": row["client"],
                "conversation_id": row["conversation_id"],
                "source_ref": row["source_ref"],
                "role": row["role"],
                "content": row["content"],
                "created_at": row["created_at"],
                "metadata": loads(row["metadata_json"], {}),
                "status": row["status"],
            }
            for row in rows
        ]

    def list_agent_learning_events(
        self,
        *,
        status: str | None = "pending_review",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        with self.connection() as conn:
            if status:
                rows = conn.execute(
                    """
                    SELECT * FROM agent_learning_events
                    WHERE status=?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM agent_learning_events
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [
            {
                "id": row["id"],
                "event_type": row["event_type"],
                "summary": row["summary"],
                "evidence": loads(row["evidence_json"], {}),
                "candidate_change": row["candidate_change"],
                "status": row["status"],
                "created_at": row["created_at"],
                "reviewed_at": row["reviewed_at"],
            }
            for row in rows
        ]


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


def _source_chunk_from_row(row: sqlite3.Row) -> dict[str, Any]:
    chunk = {
        "id": row["id"],
        "source_id": row["source_id"],
        "source_title": row["source_title"],
        "source_path": row["source_path"],
        "source_type": row["source_type"],
        "chunk_index": row["chunk_index"],
        "heading": row["heading"],
        "chapter": row["chapter"],
        "section": row["section"],
        "page_start": row["page_start"],
        "page_end": row["page_end"],
        "timestamp_start": row["timestamp_start"],
        "timestamp_end": row["timestamp_end"],
        "speaker": row["speaker"],
        "text": row["text"],
        "summary": row["summary"],
        "content_hash": row["content_hash"],
        "metadata": loads(row["metadata_json"], {}),
        "chunking_version": row["chunking_version"],
        "embedding_provider": row["embedding_provider"],
        "embedding_model": row["embedding_model"],
        "indexing_state": row["indexing_state"],
        "qdrant_point_id": row["qdrant_point_id"],
    }
    chunk["citation"] = format_source_citation(chunk)
    return chunk


def format_source_citation(chunk: dict[str, Any]) -> str:
    title = chunk.get("source_title") or Path(str(chunk.get("source_path"))).stem
    markers = []
    if chunk.get("chapter"):
        markers.append(str(chunk["chapter"]))
    if chunk.get("section") and chunk.get("section") != chunk.get("chapter"):
        markers.append(str(chunk["section"]))
    if chunk.get("page_start") is not None:
        page = f"p. {chunk['page_start']}"
        if chunk.get("page_end") and chunk["page_end"] != chunk["page_start"]:
            page = f"{page}-{chunk['page_end']}"
        markers.append(page)
    if chunk.get("timestamp_start"):
        timestamp = str(chunk["timestamp_start"])
        if chunk.get("timestamp_end"):
            timestamp = f"{timestamp}-{chunk['timestamp_end']}"
        markers.append(timestamp)
    if chunk.get("heading") and chunk.get("heading") not in markers:
        markers.append(str(chunk["heading"]))
    location = ", ".join(markers)
    if location:
        return f"{title} ({location})"
    return str(title)


def source_chunk_result_from_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": chunk["id"],
        "kind": "source_chunk",
        "title": chunk.get("heading") or chunk.get("source_title"),
        "summary": chunk["text"][:240],
        "text": chunk["text"],
        "source": chunk["source_path"],
        "source_type": chunk["source_type"],
        "citation": chunk["citation"],
        "metadata": chunk["metadata"],
        "chapter": chunk["chapter"],
        "section": chunk["section"],
        "page_start": chunk["page_start"],
        "page_end": chunk["page_end"],
        "timestamp_start": chunk["timestamp_start"],
        "timestamp_end": chunk["timestamp_end"],
        "speaker": chunk["speaker"],
        "trust_score": 0.5,
    }


def _candidate_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "source_event_ids": loads(row["source_event_ids_json"], []),
        "memory_type": row["memory_type"],
        "scope": row["scope"],
        "title": row["title"],
        "summary": row["summary"],
        "canonical_text": row["canonical_text"],
        "entities": loads(row["entities_json"], []),
        "tags": loads(row["tags_json"], []),
        "confidence": row["confidence"],
        "reason_to_save": row["reason_to_save"],
        "status": row["status"],
        "created_at": row["created_at"],
        "reviewed_at": row["reviewed_at"],
    }
