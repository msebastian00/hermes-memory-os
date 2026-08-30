# graph_review specification

Status: active read-only review gate. It does not perform resolution actions.

## Purpose

Create review items or reports for:

- ambiguous identity resolution
- duplicate entity candidates
- low-confidence claims
- unsupported edges
- contradictions
- policy conflicts

## Hard prohibitions

- Never merge canonical entities automatically.
- Never promote generated graph material into vault canon (`02_WIKI`).
- Never promote generated graph material into Memory OS durable memory.
- Never rewrite notes, policies, raw sources, or Qdrant collections.

## Output

Write Markdown review reports under the configured graph reports directory (`graph.review_report_path`), not under vault canon.

Each item must include status, confidence, candidates, evidence quotes, source/chunk IDs, Qdrant point IDs when known, and a recommended human action.

## Relationship to maintenance

`graph_maintenance` scans graph hygiene. `graph_review` creates a source-specific overlap artifact by querying the Memory OS semantic backend (Qdrant) first, then Neo4j entity names/aliases and canonical vault concept pages/aliases.

## Upsert gate

A graph upsert requires a matching complete report under `graph/reports` with `review_complete: true`, `status: approved`, `approved_by`, and `approved_at` in frontmatter. Approval is human-only and authorizes only the matching graph upsert. It does not authorize aliases, merges, vault rewrites, or Memory OS promotion.
