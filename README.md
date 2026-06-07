# Hermes Memory OS

Local-first durable memory substrate for Hermes, with a clean client boundary for Reachy and other agents. The project is standalone and can be developed directly, from Codex, or from a Hermes development workspace.

## Current Status

This repository contains the first implementation slice:

- config-required storage using `HERMES_MEMORY_HOME` or `--data-dir`
- SQLite schema and local store
- optional Qdrant collection setup and vector search
- Markdown/wiki-brain ingestion with idempotent content hashes
- CLI commands for `init`, `doctor`, `ingest`, `search`, `add`, and `archive`
- Hermes provider adapter skeleton with `prefetch` and `sync_turn`
- reviewed self-learning event logging

## Quick Start

```bash
export HERMES_MEMORY_HOME=/path/to/hermes-memory-data
python -m hermes_memory_os.cli init
python -m hermes_memory_os.cli doctor
python -m hermes_memory_os.cli ingest --path /path/to/wiki-brain
python -m hermes_memory_os.cli search "Reachy memory bridge"
```

Storage paths are intentionally not hardcoded. Use a different `HERMES_MEMORY_HOME` on WSL2, DGX Spark, or any other host.

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

Hermes Memory OS owns durable memory: SQLite, Qdrant, raw events, durable memories, source metadata, retrieval logs, injection logs, feedback, and reviewed self-learning events.

Reachy owns embodied working memory locally: wake/listening state, speaker confidence, body/camera context, room awareness, latency budgets, and short-lived conversational state. Reachy calls Hermes memory through the provider/API boundary and does not write directly to SQLite or Qdrant.
