# Next Session Handoff

Last updated: 2026-06-09
Repo: `hermes-memory-os`
Branch: `master`

## Open This First

This is the short handoff for the next session. For the fuller historical handoff, see:

- `docs/handoff-2026-06-09.md`
- `docs/live-smoke.md`
- `docs/architecture.md`

## Current State

The repo is on `master`. At the start of this handoff update, the working tree was clean.

Recent commits:

- `67dd9de docs: add project handoff notes`
- `14d4cdf feat: add chief of staff draft workflows`
- `dd85f95 docs: mark semantic milestone complete`
- `ce7c76a docs: document semantic and long-form smoke flows`
- `c380fa8 feat: implement semantic retrieval milestone`

Implemented and committed:

- SQLite durable memory store.
- Raw event storage and metadata sanitization.
- Reviewed extraction candidates.
- Long-form ingestion for Markdown, `.txt`, `.epub`, `.srt`, `.vtt`, `.json`, and dependency-gated `.pdf`.
- Optional Ollama embedding and Qdrant indexing.
- Hybrid retrieval that merges semantic Qdrant results with SQLite FTS.
- Source-type filters and citations.
- Hermes provider adapter with add/search/prefetch/sync behavior.
- Chief of Staff deterministic Markdown draft workflows.

## Verification To Re-Run

Use Python 3.11 through `uv`:

```bash
env UV_CACHE_DIR=/tmp/uv-cache /home/mike/.local/bin/uv run --python 3.11 --with pytest --with PyYAML --with requests pytest
```

Expected last-known result:

```text
30 passed
```

Compile check:

```bash
env UV_CACHE_DIR=/tmp/uv-cache /home/mike/.local/bin/uv run --python 3.11 python -m compileall src tests
```

Note: `uv` may generate `uv.lock`; it is not intentionally part of the repo right now.

## Useful Commands

Local keyword-only setup:

```bash
export PYTHONPATH=src
export HERMES_MEMORY_HOME=/tmp/hermes-memory-os-dev
python -m hermes_memory_os.cli init
python -m hermes_memory_os.cli doctor
python -m hermes_memory_os.cli provider-smoke
```

Ingest/search:

```bash
python -m hermes_memory_os.cli ingest --path /path/to/source-dir
python -m hermes_memory_os.cli ingest --path /path/to/book.txt --source-type book
python -m hermes_memory_os.cli search "query text"
python -m hermes_memory_os.cli search "query text" --source-type book
```

Chief of Staff drafts:

```bash
python -m hermes_memory_os.cli chief process-inbox --path /path/to/inbox
python -m hermes_memory_os.cli chief daily-brief
python -m hermes_memory_os.cli chief weekly-connections
python -m hermes_memory_os.cli chief self-review
```

Candidate review:

```bash
python -m hermes_memory_os.cli candidates list --status pending_review
python -m hermes_memory_os.cli candidates update cand_123 --status approved
```

## Design Boundaries To Preserve

- SQLite is the source of truth.
- Qdrant is an optional semantic index, not the authoritative store.
- Source documents are external knowledge, not Mike's personal memory.
- Extraction candidates require review before durable promotion.
- Chief of Staff workflows generate deterministic Markdown drafts only.
- No LLM calls are made by Chief workflows yet.
- No prompt, skill, or profile changes should be applied automatically.
- Reachy runtime state stays out of durable memory metadata.

## Likely Next Work

1. Add provider/tool access for Chief workflows so Hermes can call them without shelling out.
2. Add an approved-candidate promotion command:
   - read `extraction_candidates`
   - create durable memory from reviewed candidate
   - mark candidate as promoted/archived or record promotion metadata
3. Add optional `pypdf` extra and a tiny PDF fixture test.
4. Improve EPUB chapter/section extraction.
5. Add a gated live smoke script for Qdrant/Ollama.
6. Decide whether LLM-assisted Chief summaries should exist behind explicit opt-in config.

## Files Most Likely To Touch Next

- `src/hermes_memory_os/provider/adapter.py`
- `src/hermes_memory_os/chief.py`
- `src/hermes_memory_os/cli.py`
- `src/hermes_memory_os/db/store.py`
- `tests/test_chief.py`
- `tests/test_cli.py`
- `docs/hermes-development.md`

## Pickup Checklist

1. Run `git status --short --branch`.
2. Re-run the test suite.
3. Decide whether the next slice is provider exposure for Chief workflows or candidate promotion.
4. Keep changes local-first and deterministic unless explicitly adding opt-in LLM behavior.
