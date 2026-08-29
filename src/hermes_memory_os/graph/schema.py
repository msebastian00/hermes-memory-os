"""Idempotent Neo4j schema statements from the approved design package."""

from __future__ import annotations

CORE_LABELS = ("Source", "Document", "Chunk", "Entity", "Claim", "Evidence", "Policy", "Task")

SCHEMA_STATEMENTS = tuple(
    [f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE" for label in CORE_LABELS]
    + [
        "CREATE INDEX entity_name IF NOT EXISTS FOR (n:Entity) ON (n.canonical_name)",
        "CREATE INDEX entity_type IF NOT EXISTS FOR (n:Entity) ON (n.entity_type)",
        "CREATE INDEX claim_status IF NOT EXISTS FOR (n:Claim) ON (n.status)",
        "CREATE INDEX chunk_qdrant IF NOT EXISTS FOR (n:Chunk) ON (n.qdrant_point_id)",
        "CREATE INDEX source_type IF NOT EXISTS FOR (n:Source) ON (n.source_type)",
    ]
)


def initialize_schema(client: object) -> int:
    """Create all constraints and indexes; safe to invoke on every deployment."""
    execute = getattr(client, "execute")
    for statement in SCHEMA_STATEMENTS:
        execute(statement)
    return len(SCHEMA_STATEMENTS)
