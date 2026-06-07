# Live Smoke Checks

These checks exercise live local services. The default test suite uses mocks and does not require Qdrant or Ollama.

## Prerequisites

- Python 3.11+
- Qdrant listening on `http://localhost:6333`
- Ollama listening on `http://localhost:11434`
- `nomic-embed-text` available in Ollama

Example service setup:

```bash
docker run --rm -p 6333:6333 qdrant/qdrant
ollama pull nomic-embed-text
```

## Semantic Config

Create a local config file outside committed runtime data, for example `/tmp/hermes-memory-semantic.yml`:

```yaml
paths:
  base_dir: /tmp/hermes-memory-os-live
  vault_dir: /tmp/hermes-memory-os-live/vault
  sqlite_path: /tmp/hermes-memory-os-live/db/memory.sqlite
  logs_dir: /tmp/hermes-memory-os-live/logs

wiki_brain:
  enabled: true
  paths: []

qdrant:
  enabled: true
  url: http://localhost:6333
  vector_size: 768
  distance: Cosine
  collections:
    memories: hermes_memories
    wiki: hermes_wiki
    captures: hermes_captures
    sources: hermes_sources
    agent_learning: hermes_agent_learning

embeddings:
  provider: ollama
  base_url: http://localhost:11434
  model: nomic-embed-text
  dimension: 768

privacy:
  cloud_allowed: false
```

## Qdrant/Ollama Smoke

```bash
export PYTHONPATH=src
python -m hermes_memory_os.cli --config /tmp/hermes-memory-semantic.yml init
python -m hermes_memory_os.cli --config /tmp/hermes-memory-semantic.yml doctor
python -m hermes_memory_os.cli --config /tmp/hermes-memory-semantic.yml add \
  --type fact \
  --scope system \
  --title "Hermes semantic smoke" \
  --summary "Hermes can index local durable memories into Qdrant." \
  --text "Hermes can index local durable memories into Qdrant for semantic recall."
python -m hermes_memory_os.cli --config /tmp/hermes-memory-semantic.yml search "vector recall substrate"
python -m hermes_memory_os.cli --config /tmp/hermes-memory-semantic.yml provider-smoke
```

Expected:

- `doctor` reports `semantic_enabled: true`.
- `doctor` reports `embedding_reachable: true`.
- `doctor` reports `qdrant_reachable: true`.
- `add` returns `semantic_indexed: 1`.
- `search` returns the durable memory even when the query does not share exact wording.
- `provider-smoke` returns `provider_imported: true` and `prefetch_nonempty: true`.

## Long-Form Smoke

Create a book-like text file:

```bash
cat >/tmp/hermes-memory-book.txt <<'EOF'
Chapter 1 Organizational Memory

Hermes should connect durable personal memory with external source libraries.
The memory substrate keeps books separate from Mike's own durable preferences.
EOF
```

Create a transcript file:

```bash
cat >/tmp/hermes-memory-transcript.srt <<'EOF'
1
00:00:01,000 --> 00:00:04,000
Mike: Hermes should cite transcript moments when recalling source material.
EOF
```

Ingest and search:

```bash
python -m hermes_memory_os.cli --config /tmp/hermes-memory-semantic.yml ingest \
  --path /tmp/hermes-memory-book.txt \
  --source-type book
python -m hermes_memory_os.cli --config /tmp/hermes-memory-semantic.yml ingest \
  --path /tmp/hermes-memory-transcript.srt
python -m hermes_memory_os.cli --config /tmp/hermes-memory-semantic.yml search \
  "external source libraries" \
  --source-type book
python -m hermes_memory_os.cli --config /tmp/hermes-memory-semantic.yml search \
  "cite what Mike said" \
  --source-type subtitle
```

Expected:

- Each ingest returns `indexed: 1` and `semantic_indexed` greater than zero.
- Book search returns a `source_type` of `book`.
- Transcript search returns a `source_type` of `subtitle`.
- Results include `citation` with chapter or timestamp information when available.

## Re-Index Smoke

Use `--reindex` after changing embedding model, provider, or chunking behavior:

```bash
python -m hermes_memory_os.cli --config /tmp/hermes-memory-semantic.yml ingest \
  --path /tmp/hermes-memory-book.txt \
  --source-type book \
  --reindex
```

Expected:

- Unchanged sources are skipped for SQLite duplication.
- Existing chunks are marked for semantic refresh.
- Qdrant points are refreshed without creating duplicate SQLite source records.
