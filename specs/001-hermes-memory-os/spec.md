# Feature Specification: Hermes Memory OS

## Summary

Build `hermes-memory-os` as a standalone, portable, local-first durable memory system for Hermes. Reachy and other clients use it through Hermes/the memory API boundary rather than owning durable storage.

The MVP vertical slice initializes configured storage, creates SQLite schema and optional Qdrant collections, indexes Markdown/wiki-brain content, supports CLI search, exposes a Hermes provider adapter, automatically prefetches source-labeled memories, and syncs raw turns.

## Principles

- Local-first by default.
- Raw inputs are preserved before interpretation.
- Storage location is config-required; no host-specific hardcoded paths.
- Hermes Memory OS owns durable memory; clients never write directly to SQLite or Qdrant.
- Reachy owns embodied working memory locally.
- Existing wiki-brain/Obsidian vaults are indexed by configured paths.
- Chief of Staff workflows are a workflow layer over memory and wiki-brain, not a separate backend.
- Self-learning is log-and-review in v1; no automatic behavior mutation.
- Memory injection is concise, source-labeled, confidence-gated, and logged.

## Interfaces

Required provider operations:

- `initialize(config, hermes_home=None)`
- `get_tool_schemas()`
- `handle_tool_call(name, arguments)`
- `system_prompt_block()`
- `prefetch(query, context=None)`
- `sync_turn(user_message, assistant_message, metadata=None)`
- `on_session_end(messages, metadata=None)`
- `on_memory_write(action, target, content, metadata=None)`

Durable metadata for `sync_turn` is limited to provenance such as `client`, `conversation_id`, `source_ref`, timestamps, role, hashes, and safe tags. It must not persist Reachy runtime control state such as wake state, speaker confidence, robot body state, camera context, room-awareness streams, or latency budgets.

Tools:

- `hermes_memory_search`
- `hermes_memory_add`
- `hermes_memory_related`
- `hermes_memory_archive`
- `hermes_memory_profile`
- `hermes_memory_feedback`

## Acceptance Criteria

- `hermes-memory init` creates configured folders and SQLite schema.
- `hermes-memory doctor` validates required config, storage, SQLite, privacy defaults, and optional services.
- Markdown/wiki-brain ingestion is idempotent.
- CLI search returns source-linked results.
- Provider `prefetch` returns concise injected memory or suppresses weak results.
- `sync_turn` preserves raw events even if Qdrant or extraction is unavailable.
- Self-learning events are available for review but do not mutate behavior.
