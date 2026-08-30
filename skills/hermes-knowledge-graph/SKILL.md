---
name: hermes-knowledge-graph
description: Qdrant-first graph retrieve and constrained book builds.
version: 0.1.0
author: Mike, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [memory, knowledge-graph, neo4j, qdrant]
    related_skills: [hermes-memory-system]
---

# Hermes Knowledge Graph Skill

Optional evidence-backed graph tools at the Memory OS provider boundary. The vault stays canonical. Qdrant stays the vector layer. Memory OS stays the durable memory owner. Honcho is out of scope.

## When to Use

- Need claims with evidence quotes, chunk IDs, and Qdrant point IDs after Memory OS search.
- Dry-run the one supported book slice: `book-finite-infinite-games-undated`.
- Produce a read-only graph hygiene report.

Don't use for: merging entities, rewriting notes, ingesting policies, promoting graph output into Memory OS, starting Neo4j, or scheduling cron.

## Prerequisites

- Memory OS provider loaded.
- `HERMES_GRAPH_ENABLED=true` for graph expansion or upserts (default false).
- `HERMES_GRAPH_CONFIG` pointing at `config/hermes-graph.example.yml` when Neo4j is used.
- Neo4j credentials only in local env (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`). Never print them.

## Procedure

1. Call `graph_retrieve` with the user query. Confirm the packet has Memory OS `semantic_hits` even if graph warnings are present.
2. Treat `claims` as source-attributed (`claim_basis: author-framework`) unless a policy claim is marked policy-authoritative.
3. For book builds, call `graph_build_book` with the allowed source ID and omit `write_mode` (dry_run). Read `report_path` and `warnings`.
4. Set `write_mode=upsert` only when the human passed `human_approved=true` in the same tool call.
5. Call `graph_maintenance` for duplicate entities, claims without evidence, low-confidence edges, policy conflicts, and missing Qdrant crosswalks. Do not merge or rewrite.

## Pitfalls

- Feature flag off still allows `graph_retrieve`; it must not fail.
- Neo4j down still allows `graph_retrieve`; it must not fail.
- Low-confidence and unsupported graph facts are excluded by default.
- `graph_policy_ingest` and `graph_review` return `not_activated` until their specs are reviewed.
- Report paths must stay under the configured graph reports directory.
- Only the checked-in crosswalk adapter may write graph crosswalk points or indexing state; embedding text must exactly equal its declared source span.

## Verification

```bash
cd agent-dev/hermes-memory-os
PYTHONPATH=src python -m pytest tests/test_graph.py tests/test_graph_tools.py -q
hermes-graph --config config/hermes-graph.example.yml check
```

Enablement, rollback, and health-check details: `docs/knowledge-graph-runbook.md`.
