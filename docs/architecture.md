# Architecture Notes

## Memory Ownership

Hermes Memory OS owns durable memory: raw events, durable memories, source/chunk metadata, retrieval logs, injection logs, feedback, and reviewed self-learning events.

Reachy owns embodied working memory locally. Speaker confidence, wake/listening state, room/body/camera state, latency budgets, and short-lived awareness context are not persisted as Hermes memory metadata. Reachy can summarize durable facts or preferences through the memory API when appropriate.

## Wiki-Brain

The existing Karpathy-style wiki-brain is treated as an external human-readable knowledge layer. Hermes Memory OS indexes configured wiki-brain paths and preserves source paths for retrieval attribution. It does not need to own or relocate that repo/vault.

## Source Ingestion

Source ingestion is generalized around `sources` and `source_chunks`. Markdown/wiki files, books, articles, subtitles, and transcript exports are stored as external knowledge, not as durable personal memory. Supported importer paths include Markdown, plain text, EPUB, SRT, VTT, JSON transcript exports, and PDF when the local parser dependency is available.

Chunk metadata preserves the best available source location: heading, chapter, section, page, timestamp, speaker, source type, chunking version, embedding provider/model, indexing state, and Qdrant point ID. This lets retrieval distinguish `book`, `transcript`, `wiki`, `article`, and `subtitle` material and cite source chunks without treating them as Mike's beliefs.

## Retrieval

Retrieval is hybrid when semantic services are enabled:

- SQLite FTS is always available for durable memories and source chunks.
- Qdrant semantic search is used when `qdrant.enabled=true` and `embeddings.provider` is not `none`.
- Results are hydrated from SQLite, merged by canonical `kind:id`, scored with configured retrieval weights, and filtered by `retrieval.min_final_score`.
- If Qdrant or embeddings fail, search logs semantic fallback context and returns FTS results when available.

Qdrant stores embedded source chunks and durable memories. SQLite remains the source of truth for record content, metadata, status, and citations.

## Reviewed Extraction

Extraction candidates are stored in `extraction_candidates` and default to `pending_review`. Candidate review commands can create, list, and update candidates. No candidate is promoted into active durable memory automatically in this milestone.

## Chief Of Staff

Chief of Staff is a workflow layer over Hermes Memory OS and wiki-brain. It is not a separate memory backend.

The current commands read from durable memory, indexed source content, raw events, extraction candidates, and learning events. They write generated Markdown drafts such as inbox processing notes, daily briefs, weekly connections, and self-learning review summaries.

Chief of Staff commands are deterministic local draft generators. They do not call an LLM, promote extraction candidates, modify prompts, or write durable memory automatically.

Readwise, N8N, Telegram, and Vellum-style orchestration should be optional adapters that call the same memory APIs or CLI commands.

## Self-Learning

Self-learning is log-and-review in v1. Hermes Memory OS can capture retrieval misses, failed plans, useful patterns, user corrections, and candidate improvements in `agent_learning_events`, but it must not automatically modify prompts, skills, profiles, or behavior until a later reviewed workflow is designed.
