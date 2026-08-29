"""Read-only graph hygiene queries and an Obsidian-readable review report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hermes_memory_os.utils import now_iso


MAINTENANCE_QUERIES = {
    "duplicate_entities": """
        MATCH (a:Entity), (b:Entity)
        WHERE a.id < b.id
          AND toLower(a.canonical_name) = toLower(b.canonical_name)
          AND a.entity_type = b.entity_type
        RETURN a.id AS left_id, b.id AS right_id, a.canonical_name AS summary
    """,
    "claims_without_evidence": """
        MATCH (claim:Claim)
        WHERE NOT EXISTS { MATCH (:Evidence)-[:SUPPORTS]->(claim) }
        RETURN claim.id AS id, claim.claim_text AS summary, claim.confidence AS confidence
    """,
    "low_confidence_relationships": """
        MATCH ()-[r]->()
        WHERE r.confidence IS NOT NULL AND r.confidence < $threshold
        RETURN r.id AS id, type(r) AS relationship_type, r.confidence AS confidence, r.evidence_id AS evidence_id
    """,
    "policy_conflicts": """
        MATCH (policy:Policy)-[:CONSTRAINS]->(claim:Claim)
        WHERE claim.status = 'contradicted'
        RETURN policy.id AS policy_id, claim.id AS claim_id, claim.claim_text AS summary
    """,
    "missing_qdrant_crosswalk": """
        MATCH (source:Source)-[:CONTAINS]->(:Document)-[:HAS_CHUNK]->(chunk:Chunk)
        WHERE source.source_type = "book"
          AND chunk.qdrant_point_id IS NULL
        RETURN chunk.id AS id, chunk.source_id AS source_id, chunk.source_chunk_id AS source_chunk_id
    """,
}


def collect_maintenance(client: Any, *, min_confidence: float = 0.75) -> dict[str, list[dict[str, Any]]]:
    return {
        name: client.execute(query, {"threshold": min_confidence} if name == "low_confidence_relationships" else None)
        for name, query in MAINTENANCE_QUERIES.items()
    }


def write_maintenance_report(findings: dict[str, list[dict[str, Any]]], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---", "type: graph-maintenance-report", "status: generated", f"date: {now_iso()}", "---", "", "# Graph Maintenance Review", ""]
    for title, rows in findings.items():
        lines.extend([f"## {title.replace('_', ' ').title()}", f"- Count: {len(rows)}"])
        for row in rows[:20]:
            summary = row.get("summary") or row.get("id") or row.get("source_chunk_id") or "review item"
            lines.append(f"- {summary}")
        if not rows:
            lines.append("- None found.")
        lines.append("")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path
