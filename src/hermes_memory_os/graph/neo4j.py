"""Small Neo4j transactional HTTP client; no new driver dependency."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import requests

from hermes_memory_os.utils import now_iso

from .config import GraphConfig

class Neo4jError(RuntimeError):
    """Raised when Neo4j rejects a graph operation."""

class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str, timeout: int = 60, write_batch_size: int = 200):
        self.uri = uri.rstrip("/")
        self.auth = (user, password)
        self.timeout = timeout
        self.write_batch_size = write_batch_size

    @classmethod
    def from_config(cls, config: GraphConfig) -> "Neo4jClient":
        return cls(
            *config.require_neo4j(),
            timeout=config.neo4j_timeout_seconds,
            write_batch_size=config.neo4j_write_batch_size,
        )

    def health(self) -> bool:
        try:
            self.execute("RETURN 1 AS ok")
            return True
        except (requests.RequestException, Neo4jError):
            return False

    def execute(self, statement: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        response = requests.post(
            f"{self.uri}/db/neo4j/tx/commit",
            auth=self.auth,
            json={"statements": [{"statement": statement, "parameters": parameters or {}}]},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        errors = payload.get("errors") or []
        if errors:
            raise Neo4jError(str(errors[0].get("message") or errors[0]))
        results = payload.get("results") or []
        if not results:
            return []
        columns = results[0].get("columns") or []
        return [dict(zip(columns, row.get("row") or [])) for row in results[0].get("data") or []]

    def upsert(self, nodes: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> dict[str, int]:
        by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for node in nodes:
            by_label[node["label"]].append({"id": node["id"], "properties": node["properties"]})
        for label, rows in by_label.items():
            for batch in _batches(rows, self.write_batch_size):
                self.execute(
                    f"UNWIND $rows AS row MERGE (n:{label} {{id: row.id}}) SET n += row.properties",
                    {"rows": batch},
                )

        by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for relation in relationships:
            by_type[relation["type"]].append(
                {
                    "id": relation["id"],
                    "from_id": relation["from_id"],
                    "to_id": relation["to_id"],
                    "properties": relation["properties"],
                }
            )
        for relation_type, rows in by_type.items():
            for batch in _batches(rows, self.write_batch_size):
                self.execute(
                    f"UNWIND $rows AS row MATCH (a {{id: row.from_id}}), (b {{id: row.to_id}}) "
                    f"MERGE (a)-[r:{relation_type} {{id: row.id}}]->(b) SET r += row.properties",
                    {"rows": batch},
                )
        return {"nodes": len(nodes), "relationships": len(relationships)}

    def supersede_visual_variants(self, records: list[dict[str, Any]]) -> dict[str, int]:
        """Retire wording variants after an immutable visual artifact is reprocessed."""
        superseded_evidence = 0
        superseded_claims = 0
        seen: set[tuple[str, int, str, str]] = set()
        for record in records:
            key = (
                str(record["source_id"]),
                int(record["page_number"]),
                str(record["attachment_sha256"]),
                str(record["evidence_id"]),
            )
            if key in seen:
                continue
            seen.add(key)
            rows = self.execute(
                """
                MATCH (e:Evidence {
                    source_id: $source_id,
                    page_number: $page_number,
                    attachment_sha256: $attachment_sha256
                })-[:SUPPORTS]->(c:Claim {claim_type: "visual_source_claim"})
                WHERE e.id <> $evidence_id
                SET e.status = "superseded",
                    e.superseded_by = $evidence_id,
                    e.updated_at = $updated_at,
                    c.status = "superseded",
                    c.superseded_by = $claim_id,
                    c.updated_at = $updated_at
                RETURN count(DISTINCT e) AS evidence, count(DISTINCT c) AS claims
                """,
                {**record, "updated_at": now_iso()},
            )
            if rows:
                superseded_evidence += int(rows[0]["evidence"])
                superseded_claims += int(rows[0]["claims"])
        return {"evidence": superseded_evidence, "claims": superseded_claims}

    def quarantine_source(self, source_id: str, *, reason: str) -> bool:
        """Retire a graph source from expansion while preserving its audit records."""

        rows = self.execute(
            """
            MATCH (source:Source {id: $source_id})
            SET source.graph_status = "quarantined",
                source.graph_status_reason = $reason,
                source.graph_status_updated_at = $updated_at
            RETURN count(source) AS quarantined
            """,
            {"source_id": source_id, "reason": reason, "updated_at": now_iso()},
        )
        return bool(rows and int(rows[0].get("quarantined") or 0))

    def expand_context(self, chunk_ids: list[str], qdrant_point_ids: list[str]) -> list[dict[str, Any]]:
        if not chunk_ids and not qdrant_point_ids:
            return []
        return self.execute(
            """
            MATCH (seed:Chunk)
            WHERE seed.id IN $chunk_ids OR seed.qdrant_point_id IN $qdrant_point_ids
            MATCH (source:Source)-[:CONTAINS]->(document:Document)-[:HAS_CHUNK]->(seed)
            WHERE coalesce(source.graph_status, "active") = "active"
            OPTIONAL MATCH (document)-[:HAS_CHUNK]->(claim_chunk:Chunk)
            OPTIONAL MATCH (claim_chunk)-[:SUPPORTS]->(claim:Claim)
            OPTIONAL MATCH (evidence:Evidence)-[:SUPPORTS]->(claim)
            WHERE evidence.chunk_id = claim_chunk.id
            OPTIONAL MATCH (claim)-[:ABOUT]->(entity:Entity)
            WITH claim_chunk, claim, evidence, entity,
                 collect(DISTINCT seed.qdrant_point_id)[0] AS qdrant_point_id
            RETURN claim_chunk.id AS chunk_id, qdrant_point_id,
                   claim_chunk.source_id AS source_id, claim_chunk.source_chunk_id AS source_chunk_id,
                   claim.id AS claim_id, claim.claim_text AS claim_text,
                   claim.confidence AS claim_confidence, claim.status AS claim_status,
                   claim.claim_basis AS claim_basis, claim.verification_status AS verification_status,
                   evidence.id AS evidence_id, evidence.quote AS evidence_quote,
                   entity.id AS entity_id, entity.canonical_name AS entity_name
            """,
            {"chunk_ids": chunk_ids, "qdrant_point_ids": qdrant_point_ids},
        )


def _batches(rows: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    if size < 1:
        raise ValueError("Neo4j write_batch_size must be positive.")
    return [rows[index : index + size] for index in range(0, len(rows), size)]
