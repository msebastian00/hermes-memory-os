# Feature Specification: Semantic Retrieval And Workflow Hooks

## Summary

Extend Hermes Memory OS from keyword-capable local memory into the intended hybrid retrieval substrate. The next milestone adds Qdrant-backed semantic indexing/search, embedding endpoint validation, tighter Hermes provider integration tests, a reviewed extraction queue, and initial Chief of Staff workflow commands.

This feature keeps the project standalone. It must continue to work from direct/Codex development and from a Hermes workspace, with runtime data configured through `HERMES_MEMORY_HOME` or explicit config.

## Goals

- Embed Markdown/wiki-brain chunks and durable memories when embeddings are enabled.
- Upsert embedded records into Qdrant and persist point IDs in SQLite.
- Merge Qdrant semantic search with SQLite FTS results.
- Preserve FTS-only fallback when Qdrant or embeddings are unavailable.
- Make `doctor` verify enabled embedding and Qdrant services.
- Add provider-level smoke coverage that mirrors Hermes calling tools, `prefetch`, and `sync_turn`.
- Add reviewed extraction candidates without auto-promoting memories.
- Add Chief of Staff command skeletons that operate over the same memory/wiki substrate.

## Non-Goals

- No hosted embeddings by default.
- No automatic memory extraction promotion in this milestone.
- No autonomous prompt/profile/skill self-modification.
- No hard dependency on Readwise, N8N, Telegram, or Vellum.
- No Reachy runtime-state persistence.

## Functional Requirements

### Semantic Indexing

- When `embeddings.provider` is enabled and `qdrant.enabled=true`, Markdown ingestion shall:
  - embed each new or changed chunk
  - upsert the vector into the configured Qdrant collection
  - store `qdrant_point_id` on `source_chunks`
  - include source path, title, heading, status, content hash, and text excerpt in Qdrant payload

- Manual durable memory add shall:
  - store the memory in SQLite
  - index it in SQLite FTS
  - embed and upsert into the configured memories collection when semantic indexing is enabled
  - store `qdrant_collection` and `qdrant_point_id`

### Hybrid Retrieval

- `search` and `prefetch` shall query both:
  - Qdrant semantic search when available
  - SQLite FTS keyword search always

- Retrieval shall merge duplicate records by canonical ID and combine scores.
- If semantic search fails, retrieval shall log the failure and return FTS results if available.
- If all merged results are below `retrieval.min_final_score`, `prefetch` shall return no injection.

### Doctor Checks

`hermes-memory doctor` shall report:

- SQLite availability
- configured storage paths
- privacy mode
- embedding provider status when enabled
- Qdrant reachability when enabled
- configured collection names
- wiki-brain path existence

Doctor should fail only for required local substrate problems. Optional service failures should be clearly reported and should cause nonzero exit only when that service is enabled.

### Hermes Provider Fidelity

- Keep stable import paths:
  - `hermes_memory_os.hermes_plugin:create_provider`
  - `hermes_memory_os.hermes_plugin:load`
  - `hermes_memory_os.provider:HermesMemoryOSProvider`

- Add a Hermes-facing smoke fixture or test helper that verifies:
  - provider initialization
  - tool schemas
  - `hermes_memory_search`
  - `hermes_memory_add`
  - `prefetch`
  - `sync_turn`

### Reviewed Extraction Queue

- Add an extraction candidate path that can record candidate memories from raw turns.
- Candidates must include source event IDs, proposed memory type, scope, summary, canonical text, confidence, and reason.
- Candidates default to `pending_review`.
- No candidate becomes an active durable memory automatically in this milestone.

### Chief Of Staff Skeleton

Add CLI command group:

- `hermes-memory chief process-inbox`
- `hermes-memory chief daily-brief`
- `hermes-memory chief weekly-connections`
- `hermes-memory chief self-review`

For this milestone, commands may generate structured Markdown drafts from retrieved memory/wiki content. They should write outputs to configured wiki-brain or vault output folders and preserve source links.

## Data Model Changes

Add `extraction_candidates`:

- `id`
- `source_event_ids_json`
- `memory_type`
- `scope`
- `title`
- `summary`
- `canonical_text`
- `entities_json`
- `tags_json`
- `confidence`
- `reason_to_save`
- `status`
- `created_at`
- `reviewed_at`

Ensure existing `source_chunks.qdrant_point_id`, `memories.qdrant_collection`, and `memories.qdrant_point_id` are used by semantic indexing.

## Acceptance Criteria

- With Qdrant and Ollama enabled, ingesting a Markdown note creates SQLite source/chunk records and Qdrant points.
- Re-ingesting the same unchanged note does not duplicate SQLite rows or Qdrant points.
- `search` returns merged semantic and FTS results with source labels and final scores.
- If Qdrant is unavailable, `search` still returns FTS results and logs fallback.
- `doctor` reports embedding and Qdrant status accurately.
- `provider-smoke` still passes in keyword-only mode and semantic-enabled mode.
- `sync_turn` still stores only durable provenance metadata.
- Extraction candidates can be created and listed for review.
- Chief of Staff commands create Markdown drafts without requiring external workflow tools.
