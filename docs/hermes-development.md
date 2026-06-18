# Developing Hermes Memory OS

This project is standalone. It can be developed directly from this repository, by Codex, or from a Hermes development workspace.

## Direct Or Codex Development

From the repository root:

```bash
export PYTHONPATH=src
export HERMES_MEMORY_HOME=/tmp/hermes-memory-os-dev
python -m hermes_memory_os.cli init
python -m hermes_memory_os.cli doctor
python -m hermes_memory_os.cli provider-smoke
```

## Hermes Workspace Development

From a Hermes development environment, install this project in editable mode:

```bash
pip install -e /path/to/hermes-memory-os
```

Or run from source by adding this repo's `src` directory to `PYTHONPATH`.

Set runtime storage independently:

```bash
export HERMES_MEMORY_HOME=/path/to/memory-data
```

## Hermes Import Path

Hermes should load the provider through one of these stable paths:

```text
hermes_memory_os.hermes_plugin:create_provider
hermes_memory_os.hermes_plugin:load
hermes_memory_os.provider:HermesMemoryOSProvider
```

The root `hermes-plugin.yaml` records these paths for plugin loaders that use manifests. This does not make Hermes the owner of the project; it only exposes a stable integration point.

## Provider Behavior

The provider exposes local durable memory through tool calls and prefetch:

- `hermes_memory_add` writes a durable memory and semantically indexes it when local semantic services are enabled.
- `hermes_memory_search` returns hybrid FTS/Qdrant results with source labels and citations.
- `prefetch` injects source-labeled local memory context for Hermes turns.
- `sync_turn` persists raw provenance events after dropping blocked runtime metadata.

Use `python -m hermes_memory_os.cli provider-smoke` from a Hermes workspace to verify import paths, memory add, prefetch, and turn sync.

## HTTP Adapter For Reachy

The HTTP adapter is not a Hermes core route. It is a separate Memory OS service boundary for Reachy and other clients that need direct low-latency recall.

```bash
python -m pip install -e ".[http]"
export HERMES_MEMORY_HOME=/path/to/memory-data
export HERMES_MEMORY_HTTP_HOST=0.0.0.0
export HERMES_MEMORY_HTTP_PORT=8765
export HERMES_MEMORY_HTTP_API_KEY=change-me-local-dev
python -m hermes_memory_os.http_api
```

Use separate URLs in Reachy:

```text
MEMORY_OS_BASE_URL=http://SPARK_HOST:8765
HERMES_DELEGATION_BASE_URL=http://SPARK_HOST:<hermes-runs-port>
NAT Hermes tool base_url=http://SPARK_HOST:<hermes-chat-port>/v1
```

If `GET /health` works but `POST /v1/search` returns 404, the client is probably pointed at Hermes or another service rather than the Memory OS HTTP adapter.

## Source Ingestion

Long-form source ingestion is available through the CLI:

```bash
python -m hermes_memory_os.cli ingest --path /path/to/wiki-or-source-dir
python -m hermes_memory_os.cli ingest --path /path/to/book.txt --source-type book
python -m hermes_memory_os.cli ingest --path /path/to/transcript.srt
python -m hermes_memory_os.cli search "relevant concept" --source-type book
```

When Qdrant and Ollama are enabled, ingested source chunks are embedded into the configured source collection. Without semantic services, the same sources remain searchable through SQLite FTS.

Live Qdrant/Ollama and long-form smoke steps are documented in [live-smoke.md](live-smoke.md).

## Chief Of Staff Drafts

Chief of Staff commands generate local Markdown drafts without autonomous memory writes:

```bash
python -m hermes_memory_os.cli chief process-inbox --path /path/to/inbox
python -m hermes_memory_os.cli chief daily-brief
python -m hermes_memory_os.cli chief weekly-connections
python -m hermes_memory_os.cli chief self-review
```

Hermes can treat these drafts as review artifacts. If a draft identifies a durable fact or preference, route it through extraction candidate review before writing memory.

## Runtime Data

Do not store runtime memory data in the Hermes repo or in this repo. Set `HERMES_MEMORY_HOME` per machine:

- WSL2 Alienware: choose a local dev path.
- DGX Spark: choose the mounted production memory volume.
- CI/tests: use `/tmp/...`.

## Boundary

Hermes calls the provider adapter when Hermes is doing reasoning work. Reachy calls the Memory OS HTTP adapter for fast recall and candidate handoff. Neither Hermes nor Reachy writes directly to SQLite, Qdrant, or wiki-brain files.
