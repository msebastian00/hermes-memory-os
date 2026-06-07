# Tasks: Semantic Retrieval And Workflow Hooks

## Schema And Store

- [x] Add `extraction_candidates` schema.
- [x] Add store methods to create/list/update extraction candidates.
- [x] Add store methods to save Qdrant point IDs for chunks and memories.
- [x] Add tests for candidate lifecycle and point ID persistence.

## Embeddings And Qdrant

- [x] Add embedding health check.
- [x] Extend Qdrant client with collection/status/search helpers.
- [x] Embed/upsert source chunks during ingestion when enabled.
- [x] Embed/upsert durable memories during add when enabled.
- [x] Add mocked tests for Qdrant upsert payload shape.

## Long-Form Ingestion

- [x] Generalize ingestion beyond Markdown-only paths.
- [x] Add `.txt` importer for books, articles, and plain transcripts.
- [x] Add `.pdf` importer with clear local dependency handling.
- [x] Add `.epub` importer with clear local dependency handling.
- [x] Add `.srt` importer with timestamp metadata.
- [x] Add `.vtt` importer with timestamp metadata.
- [x] Add `.json` transcript importer with speaker/timestamp metadata when present.
- [x] Preserve chunk metadata for chapter, section, page, timestamp, speaker, heading, and source type.
- [x] Add source-type-specific filters for `book`, `transcript`, `wiki`, `article`, and `subtitle`.
- [x] Add citation formatting for retrieved source chunks.
- [x] Add deterministic re-indexing when chunking version changes.
- [x] Add deterministic re-indexing when embedding provider/model changes.
- [x] Add tests for long-form importers, metadata preservation, citations, filters, and re-indexing.

## Hybrid Retrieval

- [x] Add semantic search path.
- [x] Merge semantic and FTS results by canonical ID.
- [x] Normalize scores and preserve existing ranking weights.
- [x] Log semantic fallback when Qdrant/embeddings fail.
- [x] Include citation metadata in search and prefetch results.
- [x] Add tests for merged results and fallback behavior.

## CLI And Provider

- [x] Expand `doctor` for embedding/Qdrant/wiki path checks.
- [x] Add ingestion CLI options for source type and re-indexing.
- [x] Add extraction candidate review commands.
- [x] Keep `provider-smoke` passing.

## Docs And Verification

- [x] Update README with semantic setup.
- [x] Update README with long-form ingestion setup.
- [x] Update architecture docs.
- [x] Add live Qdrant/Ollama smoke instructions.
- [x] Add live long-form smoke instructions for book and transcript ingestion.
- [x] Run compile checks.
- [x] Run pytest when installed.
- [ ] Commit changes in logical chunks.
