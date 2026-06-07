# Implementation Plan: Semantic Retrieval And Workflow Hooks

## Summary

Implement the next vertical slice in five parts: semantic indexing, hybrid retrieval, service health checks, reviewed extraction candidates, and Chief of Staff command skeletons. Preserve keyword-only local operation as the fallback path.

## Implementation Steps

1. **Schema And Store**
   - Add `extraction_candidates` table.
   - Add store methods for updating Qdrant point IDs on chunks and memories.
   - Add store methods for creating/listing extraction candidates.
   - Add retrieval fallback/error logging fields if current logs are insufficient.

2. **Embeddings And Qdrant**
   - Add embedding health check abstraction.
   - Extend Qdrant client with collection existence, payload upsert, and search helpers.
   - During Markdown ingestion, embed/upsert chunks when semantic indexing is enabled.
   - During memory add, embed/upsert durable memories when semantic indexing is enabled.
   - Keep deterministic disabled embedder for tests only; do not treat it as real semantic search.

3. **Hybrid Retriever**
   - Add semantic search path for configured Qdrant collections.
   - Merge semantic and FTS results by canonical ID.
   - Normalize semantic and keyword scores before ranking.
   - Keep FTS fallback on Qdrant/embedding failure.
   - Ensure `prefetch` logs suppressed and fallback cases.

4. **CLI And Provider**
   - Expand `doctor` output for embeddings, Qdrant, collections, and wiki paths.
   - Add `extraction candidate` commands or equivalent review commands.
   - Add `chief` command group with skeleton workflows.
   - Keep `provider-smoke` as the Hermes/Codex integration check.

5. **Tests And Docs**
   - Add unit tests for schema migration, candidate creation, Qdrant point IDs, score merge, and fallback behavior.
   - Add mocked Qdrant/embedding tests; do not require live Qdrant in default tests.
   - Add optional integration instructions for running live Qdrant/Ollama tests.
   - Update README and architecture docs with semantic retrieval and Chief of Staff workflow status.

## Test Plan

- `pytest` default suite:
  - config-required storage
  - no-cloud default
  - metadata sanitization
  - idempotent Markdown ingestion
  - mocked embedding upsert
  - mocked Qdrant search merge
  - FTS fallback when semantic search fails
  - extraction candidate review lifecycle
  - Chief of Staff draft file creation
  - provider smoke behavior

- Manual/live smoke:
  - start Qdrant
  - start Ollama with `nomic-embed-text`
  - set `HERMES_MEMORY_HOME`
  - enable `qdrant.enabled=true` and `embeddings.provider=ollama`
  - run `hermes-memory init`
  - run `hermes-memory doctor`
  - ingest a wiki-brain note
  - search semantically related wording that does not share exact keywords
  - run `hermes-memory provider-smoke`

## Assumptions

- Qdrant and Ollama are optional in local development but enabled for the semantic integration path.
- The project remains standalone and can be driven by Codex or imported from Hermes.
- Chief of Staff workflows are local commands first; N8N/Readwise/Vellum integration remains future adapter work.
- Extraction candidates require review before promotion to durable memories.
