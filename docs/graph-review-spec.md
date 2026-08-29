# graph_review specification (staged, not activated)

Status: draft. Implement only after the policy adapter design is reviewed.

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

`graph_maintenance` is the read-only scanner. `graph_review` would format those findings as durable review items. Until activation, use `graph_maintenance` reports only.

## Activation gate

1. Policy adapter spec reviewed.
2. Tests prove no merge, no vault write, no Memory OS write.
3. Human approval workflow for later merge actions is defined separately.

Until then the dispatcher returns `status: not_activated` with `auto_merged=false`.
