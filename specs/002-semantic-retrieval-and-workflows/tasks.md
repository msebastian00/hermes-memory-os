# Tasks: Semantic Retrieval And Workflow Hooks

## Schema And Store

- [ ] Add `extraction_candidates` schema.
- [ ] Add store methods to create/list/update extraction candidates.
- [ ] Add store methods to save Qdrant point IDs for chunks and memories.
- [ ] Add tests for candidate lifecycle and point ID persistence.

## Embeddings And Qdrant

- [ ] Add embedding health check.
- [ ] Extend Qdrant client with collection/status/search helpers.
- [ ] Embed/upsert Markdown chunks during ingestion when enabled.
- [ ] Embed/upsert durable memories during add when enabled.
- [ ] Add mocked tests for Qdrant upsert payload shape.

## Hybrid Retrieval

- [ ] Add semantic search path.
- [ ] Merge semantic and FTS results by canonical ID.
- [ ] Normalize scores and preserve existing ranking weights.
- [ ] Log semantic fallback when Qdrant/embeddings fail.
- [ ] Add tests for merged results and fallback behavior.

## CLI And Provider

- [ ] Expand `doctor` for embedding/Qdrant/wiki path checks.
- [ ] Add extraction candidate review commands.
- [ ] Add `chief process-inbox`.
- [ ] Add `chief daily-brief`.
- [ ] Add `chief weekly-connections`.
- [ ] Add `chief self-review`.
- [ ] Keep `provider-smoke` passing.

## Docs And Verification

- [ ] Update README with semantic setup.
- [ ] Update architecture docs.
- [ ] Add live Qdrant/Ollama smoke instructions.
- [ ] Run compile checks.
- [ ] Run pytest when installed.
- [ ] Commit changes in logical chunks.
