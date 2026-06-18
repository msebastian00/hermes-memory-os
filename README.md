# Hermes Memory OS

Local-first durable memory substrate for Hermes, with a clean client boundary for Reachy and other agents. The project is standalone and can be developed directly, from Codex, or from a Hermes development workspace.

## Current Status

This repository contains the local memory substrate and current semantic retrieval milestone:

- config-required storage using `HERMES_MEMORY_HOME` or `--data-dir`
- SQLite schema and local store
- optional Qdrant collection setup, semantic indexing, and hybrid vector/FTS search
- Markdown/wiki-brain and long-form source ingestion with idempotent content hashes
- `.txt`, `.epub`, `.srt`, `.vtt`, `.json`, and dependency-gated `.pdf` ingestion
- source-type filters, citations, and re-index state for books, transcripts, wiki notes, articles, and subtitles
- CLI commands for `init`, `doctor`, `ingest`, `search`, `add`, `archive`, `candidates`, and `provider-smoke`
- Hermes provider adapter with `prefetch`, `sync_turn`, and source-labeled retrieval
- optional HTTP adapter for direct Reachy/agent recall over `/health`, `/v1/search`, `/v1/sources/chunks`, and `/v1/candidates`
- reviewed extraction candidates and self-learning event logging

## Quick Start

```bash
export HERMES_MEMORY_HOME=/path/to/hermes-memory-data
python -m hermes_memory_os.cli init
python -m hermes_memory_os.cli doctor
python -m hermes_memory_os.cli ingest --path /path/to/wiki-brain
python -m hermes_memory_os.cli search "Reachy memory bridge"
```

Storage paths are intentionally not hardcoded. Use a different `HERMES_MEMORY_HOME` on WSL2, DGX Spark, or any other host.

## HTTP Adapter

The HTTP adapter is the direct Memory OS service boundary for Reachy and other clients that should not call Hermes for fast recall. It is separate from Hermes core and reuses the same Memory OS storage/retrieval code as the CLI and provider.

```bash
python -m pip install -e ".[http]"
export HERMES_MEMORY_HOME=/path/to/hermes-memory-data
export HERMES_MEMORY_HTTP_HOST=0.0.0.0
export HERMES_MEMORY_HTTP_PORT=8765
export HERMES_MEMORY_HTTP_API_KEY=change-me-local-dev
python -m hermes_memory_os.http_api
```

Smoke check:

```bash
curl -sS "http://127.0.0.1:${HERMES_MEMORY_HTTP_PORT}/health" | python -m json.tool
```

Reachy should point `MEMORY_OS_BASE_URL` at this adapter, not at a Hermes chat/runs endpoint.

## Semantic Setup

Semantic retrieval is local-first and optional. The default config uses `embeddings.provider: none`, so keyword/FTS retrieval works without Qdrant or Ollama.

To enable local semantic indexing with Qdrant and Ollama:

```yaml
qdrant:
  enabled: true
  url: http://localhost:6333
  vector_size: 768
  distance: Cosine

embeddings:
  provider: ollama
  base_url: http://localhost:11434
  model: nomic-embed-text
  dimension: 768
```

Then run:

```bash
python -m hermes_memory_os.cli init
python -m hermes_memory_os.cli doctor
python -m hermes_memory_os.cli ingest --path /path/to/wiki-brain
python -m hermes_memory_os.cli search "conceptually related wording"
```

When semantic services are enabled, `ingest` embeds source chunks into Qdrant and `add` embeds durable memories. `search` merges Qdrant semantic results with SQLite FTS results and falls back to FTS if Qdrant or embeddings fail.

## Long-Form Ingestion

`ingest` accepts files or directories. Supported source formats:

- `.md` wiki/Markdown notes
- `.txt` books, articles, and plain transcripts
- `.epub` books via local ZIP/XHTML extraction
- `.srt` and `.vtt` subtitles/transcripts with timestamp and speaker metadata
- `.json` transcript exports with speaker/timestamp metadata when present
- `.pdf` when the local `pypdf` dependency is installed

Examples:

```bash
python -m hermes_memory_os.cli ingest --path /path/to/book.txt --source-type book
python -m hermes_memory_os.cli ingest --path /path/to/transcript.srt
python -m hermes_memory_os.cli search "organizational memory" --source-type book
python -m hermes_memory_os.cli search "what did Mike say about memory" --source-type subtitle
```

Use `--reindex` to mark unchanged sources for re-indexing when the chunking version, embedding provider, or embedding model changes:

```bash
python -m hermes_memory_os.cli ingest --path /path/to/sources --reindex
```

Retrieved source chunks include citations using the best available location marker: heading, chapter, section, page, timestamp, or speaker metadata.

## Candidate Review

Extraction candidates are staged for review and are not promoted into durable memories automatically.

```bash
python -m hermes_memory_os.cli candidates create \
  --source-event-id evt_123 \
  --type fact \
  --scope system \
  --summary "Hermes should preserve reviewed candidates." \
  --text "Hermes should preserve reviewed candidates before durable promotion."

python -m hermes_memory_os.cli candidates list --status pending_review
python -m hermes_memory_os.cli candidates update cand_123 --status approved
```

## Chief Of Staff Drafts

Chief of Staff workflows are local deterministic draft generators over existing memory, source retrieval, candidates, and learning events. They write Markdown under `vault/chief/` by default and do not promote candidates or modify durable memory automatically.

```bash
python -m hermes_memory_os.cli chief process-inbox --path /path/to/inbox
python -m hermes_memory_os.cli chief daily-brief
python -m hermes_memory_os.cli chief weekly-connections
python -m hermes_memory_os.cli chief self-review
```

Use `--output-dir` on any Chief command to write drafts somewhere else.

## Development Modes

Direct/Codex development from this repo:

```bash
export PYTHONPATH=src
export HERMES_MEMORY_HOME=/tmp/hermes-memory-os-dev
python -m hermes_memory_os.cli init
python -m hermes_memory_os.cli provider-smoke
```

Hermes development workspace:

```bash
pip install -e /path/to/hermes-memory-os
export HERMES_MEMORY_HOME=/path/to/memory-data
```

Hermes should import the provider through `hermes_memory_os.hermes_plugin:create_provider`.

## Design Boundary

Hermes Memory OS owns durable memory: SQLite, Qdrant, raw events, durable memories, source/chunk metadata, retrieval logs, injection logs, feedback, extraction candidates, and reviewed self-learning events.

Reachy owns embodied working memory locally: wake/listening state, speaker confidence, body/camera context, room awareness, latency budgets, and short-lived conversational state. Reachy calls the Memory OS HTTP adapter for fast recall and candidate handoff, and Hermes calls Memory OS through the provider when Hermes is the active reasoning agent. Neither Hermes nor Reachy writes directly to SQLite or Qdrant.
