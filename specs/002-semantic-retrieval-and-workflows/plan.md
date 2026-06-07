# Implementation Plan: Semantic Retrieval And Workflow Hooks

## Summary

Implement the next vertical slice in five parts: semantic indexing, long-form ingestion, hybrid retrieval, service health checks, and reviewed extraction candidates. Preserve keyword-only local operation as the fallback path.

Today's target is not limited to short wiki notes. Hermes must be able to ingest and retrieve from long-form books and transcripts with useful metadata, citations, source-type filters, and re-indexing support.

## Implementation Steps

1. **Schema And Store**
   - Add `extraction_candidates` table.
   - Add store methods for updating Qdrant point IDs on chunks and memories.
   - Add store methods for creating/listing extraction candidates.
   - Add retrieval fallback/error logging fields if current logs are insufficient.

2. **Embeddings And Qdrant**
   - Add embedding health check abstraction.
   - Extend Qdrant client with collection existence, payload upsert, and search helpers.
   - During source ingestion, embed/upsert chunks when semantic indexing is enabled.
   - During memory add, embed/upsert durable memories when semantic indexing is enabled.
   - Keep deterministic disabled embedder for tests only; do not treat it as real semantic search.

3. **Long-Form Ingestion**
   - Generalize ingestion around source documents and chunks instead of Markdown-only paths.
   - Add importers for `.txt`, `.pdf`, `.epub`, `.srt`, `.vtt`, and `.json` transcript exports.
   - Preserve chapter, section, page, timestamp, speaker, heading, and source type when available.
   - Route source types into Qdrant payloads and SQLite metadata for filtering.
   - Add citation formatting for retrieved chunks.
   - Add deterministic re-indexing for changed chunking version, embedding model/provider, and metadata schema.

4. **Hybrid Retriever**
   - Add semantic search path for configured Qdrant collections.
   - Merge semantic and FTS results by canonical ID.
   - Normalize semantic and keyword scores before ranking.
   - Keep FTS fallback on Qdrant/embedding failure.
   - Add source-type filters for `book`, `transcript`, `wiki`, `article`, and `subtitle`.
   - Include citation metadata in search and prefetch results.
   - Ensure `prefetch` logs suppressed and fallback cases.

5. **CLI And Provider**
   - Expand `doctor` output for embeddings, Qdrant, collections, and wiki paths.
   - Add `extraction candidate` commands or equivalent review commands.
   - Add ingestion CLI options for source type, re-indexing, and long-form paths.
   - Keep `provider-smoke` as the Hermes/Codex integration check.

6. **Tests And Docs**
   - Add unit tests for schema migration, candidate creation, Qdrant point IDs, score merge, and fallback behavior.
   - Add importer tests for `.txt`, `.pdf`, `.epub`, `.srt`, `.vtt`, and `.json` fixtures.
   - Add tests for long-form chunk metadata, citations, source-type filters, and re-indexing.
   - Add mocked Qdrant/embedding tests; do not require live Qdrant in default tests.
   - Add optional integration instructions for running live Qdrant/Ollama tests.
   - Update README and architecture docs with semantic retrieval and Chief of Staff workflow status.

## Test Plan

- `pytest` default suite:
  - config-required storage
  - no-cloud default
  - metadata sanitization
  - idempotent Markdown ingestion
  - long-form `.txt`, `.pdf`, `.epub`, `.srt`, `.vtt`, and `.json` ingestion
  - chunk metadata preservation for chapter, section, page, timestamp, speaker, heading, and source type
  - citation formatting for retrieved long-form chunks
  - source-type search filters
  - deterministic re-indexing without duplicated source rows
  - mocked embedding upsert
  - mocked Qdrant search merge
  - FTS fallback when semantic search fails
  - extraction candidate review lifecycle
  - provider smoke behavior

- Manual/live smoke:
  - start Qdrant
  - start Ollama with `nomic-embed-text`
  - set `HERMES_MEMORY_HOME`
  - enable `qdrant.enabled=true` and `embeddings.provider=ollama`
  - run `hermes-memory init`
  - run `hermes-memory doctor`
  - ingest a wiki-brain note
  - ingest a book-length text or EPUB source
  - ingest an SRT/VTT/JSON transcript source
  - search semantically related wording that does not share exact keywords
  - search with `book`, `transcript`, and `wiki` source-type filters
  - run `hermes-memory provider-smoke`

## Assumptions

- Qdrant and Ollama are optional in local development but enabled for the semantic integration path.
- The project remains standalone and can be driven by Codex or imported from Hermes.
- Chief of Staff workflows are deferred to the following slice.
- Extraction candidates require review before promotion to durable memories.
- Optional parsers for PDF and EPUB may be dependency-gated, but the ingestion pipeline must expose the importer path and fail clearly when a local parser is unavailable.
