# Architecture Notes

## Memory Ownership

Hermes Memory OS owns durable memory: raw events, durable memories, source/chunk metadata, retrieval logs, injection logs, feedback, and reviewed self-learning events.

Reachy owns embodied working memory locally. Speaker confidence, wake/listening state, room/body/camera state, latency budgets, and short-lived awareness context are not persisted as Hermes memory metadata. Reachy can summarize durable facts or preferences through the memory API when appropriate.

## Wiki-Brain

The existing Karpathy-style wiki-brain is treated as an external human-readable knowledge layer. Hermes Memory OS indexes configured wiki-brain paths and preserves source paths for retrieval attribution. It does not need to own or relocate that repo/vault.

## Chief Of Staff

Chief of Staff is a workflow layer over Hermes Memory OS and wiki-brain. It is not a separate memory backend.

Future workflow commands should read from durable memory and indexed wiki-brain content, then write generated Markdown outputs such as inbox processing notes, daily briefs, weekly connections, deep research notes, and self-learning review summaries.

Readwise, N8N, Telegram, and Vellum-style orchestration should be optional adapters that call the same memory APIs or CLI commands.

## Self-Learning

Self-learning is log-and-review in v1. Hermes Memory OS can capture retrieval misses, failed plans, useful patterns, user corrections, and candidate improvements in `agent_learning_events`, but it must not automatically modify prompts, skills, profiles, or behavior until a later reviewed workflow is designed.
