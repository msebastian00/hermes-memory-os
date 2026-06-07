---
title: Hermes Memory OS — Full System Specification
created: 2026-06-03
updated: 2026-06-03
type: spec
tags: [hermes, memory, second-brain, chief-of-staff, vellum, qdrant, sqlite, obsidian, retrieval, long-form-ingestion]
sources: [hermes_local_memory_spec_kit_spec.md, https://x.com/cyrilXBT/status/2059461814333673705, https://x.com/cyrilXBT/status/2058373087330959829, x-bookmarks-page4.json, Garry Tan Moss post]
confidence: high
status: design
---

# Hermes Memory OS — Full System Specification

**Name**: `hermes-memory-os` (formerly `mike_memory`)  
**Goal**: A local-first, fast, compounding second brain for Hermes agents that feels like a Chief of Staff.

This spec merges the original detailed `hermes_local_memory_spec_kit_spec.md` with the retrieval-first vault organization and Chief of Staff patterns from CyrilXBT, while targeting Moss-like sub-50ms local retrieval performance.

## 1. Core Principles

1. **Raw capture is sacred** — Never lose the original signal.
2. **Layered memory** — Raw → Durable → Human-readable Wiki → Synthesis.
3. **Retrieval-first organization** — Every decision optimizes for <30s retrieval.
4. **Local-only by default** — No cloud unless explicitly configured.
5. **Compounding intelligence** — The system gets meaningfully smarter over months, not just bigger.
6. **Hermes-native** — Implemented as a proper MemoryProvider plugin.

## 2. Four-Layer Architecture

### Layer 0 — Raw Capture (Sacred)
Location: `00_CAPTURE/`

- `raw/` — Quick notes, voice memos, unprocessed thoughts
- `links/` — Web clips with URL + date
- `transcripts/` — Video/podcast transcripts (with speaker/timestamp metadata)
- `books/` — Book chapters and long-form sources (structured Markdown)
- `voice/` — Whisper outputs

All ingestion lands here first. Processing is asynchronous.

### Layer 1 — Durable Structured Memory (Fast Retrieval)
- **SQLite**: `memory.sqlite` with tables for `raw_events`, `memories`, `entities`, `sources`, `source_chunks`, `retrieval_log`, `injection_log`, `feedback`
- **Qdrant** collections (separate for personal vs external knowledge):
  - `hermes_memories` — Durable personal facts, preferences, decisions, projects
  - `hermes_wiki` — Obsidian notes
  - `hermes_captures` — Processed raw captures
  - `hermes_sources` — External long-form content (books, transcripts, articles)

**Fast path**:
- HNSW index + 4-bit quantization
- Hybrid search (Qdrant vector + SQLite FTS5)
- Target: sub-50ms p99 retrieval (Moss-inspired)

### Layer 2 — Human-Readable Wiki (Obsidian)
Retrieval-first structure + Chief of Staff `CHIEF/` layout:

```
CHIEF/
├── 00-INBOX/
├── 01-CAPTURES/
│   ├── raw/
│   ├── links/
│   ├── transcripts/
│   └── books/
├── 02-CONNECTIONS/
├── 03-PROJECTS/
└── 04-VELLUM/
    ├── VELLUM.md
    └── workflows/
```

- Type-based folders + `YYYY-MM-DD-[TYPE]-[TOPIC].md` naming
- Universal + type-specific YAML properties
- `status/` and `project/` tags
- MOCs for clusters

### Layer 3 — Synthesis & Briefing
- Generated daily/weekly briefs, connection notes, and pattern summaries
- Cron/Auto-think jobs run the four core workflows
- Output lands in `06_GENERATED/`

## 3. VELLUM.md — The Operating Context File

`VELLUM.md` is the single source of truth the Chief of Staff agent reads on every workflow run.

**Required sections**:
- Identity & current focus
- Vault structure explanation
- Current projects + stuck points
- Explicit operating instructions ("Surface cross-domain connections", "Challenge assumptions", "Prioritize X")
- Weekly-updated "What I Am Reading And Thinking About Right Now"

This file enables the compounding intelligence effect and high-quality Daily Briefs without prompt bloat.

## 4. Ingestion Pipelines

- **Notes**: Direct to `00_CAPTURE/raw/`
- **Web clips**: URL + date + content → `00_CAPTURE/links/`
- **Video transcripts**: yt-dlp + fw-transcribe-gpu → `00_CAPTURE/transcripts/` (preserve speaker/timestamp)
- **Book chapters**: PDF → structured Markdown with chapter/section/page metadata → `hermes_sources` collection (external knowledge only, never auto-promoted to personal memory)

All pipelines preserve source attribution and hierarchy.

## 5. Retrieval & Ranking

Multi-signal ranking (configurable weights):

```
final_score = 0.45*semantic + 0.20*keyword + 0.15*entity + 0.10*scope + 0.05*recency + 0.05*trust
```

- Low-confidence suppression (configurable threshold)
- Max 8 memories injected by default
- Source-labeled injection format

## 6. Hermes MemoryProvider Interface

The provider implements the standard Hermes MemoryProvider contract:

**Required methods**:
- `initialize(config, hermes_home)`
- `prefetch(query, context=None)`
- `sync_turn(user_message, assistant_message)`
- `on_session_end(messages)`
- Tool handlers for `hermes_memory_search`, `hermes_memory_add`, `hermes_memory_related`, `hermes_memory_archive`, `hermes_memory_profile`, `hermes_memory_feedback`

**Injection rules**:
- Source-labeled
- Never inject stale or low-confidence memories
- Log every retrieval and injection

## 7. Synthesis Workflows (Chief of Staff)

1. **Process Inbox** — Route and sharpen raw captures
2. **Daily Brief** (cron 6am) — 3 connections + 1 pattern + 1 question
3. **Weekly Connections** — TYPE A–D connection detection across domains
4. **Deep Research** — Contradictions, missing perspectives, unasked questions

All workflows read from and update `VELLUM.md`.

## 8. Performance Targets

- Retrieval: sub-50ms p99 (target sub-20ms with quantization)
- Ingestion: background, non-blocking
- Daily brief generation: <30 seconds
- Long-form chunking: preserve chapter/section/page/timestamp hierarchy

## 9. Configuration (hermes-memory-os.yaml)

```yaml
provider:
  name: hermes-memory-os
  enabled: true

paths:
  base_dir: ~/.hermes/memory
  vault_dir: ~/.hermes/memory/vault
  sqlite_path: ~/.hermes/memory/db/memory.sqlite

qdrant:
  url: http://localhost:6333
  collections: [hermes_memories, hermes_wiki, hermes_captures, hermes_sources]

embeddings:
  provider: ollama
  model: nomic-embed-text
  dimension: 768

retrieval:
  max_injected: 8
  min_final_score: 0.35
  weights:
    semantic: 0.45
    keyword: 0.20
    entity: 0.15
    scope: 0.10
    recency: 0.05
    trust: 0.05

extraction:
  enabled: true
  min_confidence: 0.65

vellum:
  enabled: true
  daily_brief_cron: "0 6 * * *"
```

## 10. Implementation Phases

**Phase 0** — Design complete (this document) + vault structure prototype  
**Phase 1** — MemoryProvider plugin + SQLite + basic Qdrant + prefetch/injection  
**Phase 2** — Obsidian vault + retrieval-first properties + VELLUM.md  
**Phase 3** — Long-form ingestion (books, transcripts, web clips) + `hermes_sources`  
**Phase 4** — Synthesis workflows + cron integration + Chief of Staff daily brief  
**Phase 5** — Performance tuning (quantization, hybrid search) + feedback loops

## 11. Security & Privacy

- Local-only by default
- Raw events never leave the machine
- Archive instead of delete
- Full backup support (SQLite + Qdrant + vault)
- Sensitive redaction configurable

## 12. Key Differentiators vs Previous Spec

- Explicit 4-layer architecture
- VELLUM.md as the operating context layer
- Retrieval-first vault + Chief of Staff rituals
- Moss-inspired performance targets
- Dedicated long-form ingestion pipelines with source attribution
- Stronger emphasis on compounding intelligence over 6+ months

---

**Provenance**: Synthesized from `hermes_local_memory_spec_kit_spec.md`, the two CyrilXBT posts (extracted 2026-06-03), page4.json agent bookmarks, and Moss performance goals.

**See also**: [[hermes-agent-best-practices]], [[obsidian-memory-systems]], [[hermes-agent]]

^ hermes-memory-os spec v1.0 — 2026-06-03
