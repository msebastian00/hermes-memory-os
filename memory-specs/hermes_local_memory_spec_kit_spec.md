# Feature Specification: Hermes Local Memory Operating System

**Feature name:** Hermes Local Memory Operating System  
**Codename:** `mike_memory`  
**Target repo:** `~/agent-platform/agent-dev` or the active Hermes extension/workspace repository  
**Primary runtime host:** DGX Spark 2 (`spark-7a0b`)  
**Primary user:** Mike Sebastian  
**Spec purpose:** Hand this to GitHub Spec Kit / Codex to design and build a durable, local-first memory provider for Hermes.

---

## 1. Product Intent

Build a local-first, durable memory infrastructure for Hermes that gives the agent persistent recall across conversations, notes, captures, projects, and generated outputs.

This system must act less like a passive vector database and more like a practical "personal operating memory" for Hermes:

- Capture messy inputs without requiring perfect organization.
- Preserve raw inputs before summarizing or interpreting them.
- Extract durable memories from conversations, notes, and files.
- Retrieve the right memories at the right time automatically.
- Inject concise, relevant memory context into Hermes before responses.
- Link related ideas, projects, people, content themes, and technical setup details.
- Support Obsidian/Markdown as the human-readable wiki layer.
- Use Qdrant locally for semantic recall.
- Use SQLite locally for durable event/fact metadata, retrieval logs, and state.
- Survive Hermes updates by integrating through the official Hermes MemoryProvider plugin architecture rather than patching Hermes core.

This is not just a task manager or a notes app. It is the local memory substrate for Hermes.

---

## 2. Background and Rationale

Hermes currently has local files such as `MEMORY.md` and `USER.md`, and it supports external memory providers. Hosted memory providers such as Mem0 solve important problems: extraction, deduplication, retrieval, prefetch, and automatic context injection. However, the desired system must keep Mike's raw personal, professional, technical, and strategic thinking local by default.

The first version should not depend on hosted Mem0 or any cloud memory service. Hosted providers may be used later for comparison with sanitized test data, but they must not become the canonical memory source.

The system should be designed around "bad-day" operation:

> Capture should be effortless. Processing should be automatic. Review should be optional but valuable.

If Mike is busy, tired, traveling, or inconsistent, the system must still preserve inputs, process them later, and keep operating without guilt-inducing manual maintenance.

---

## 3. Goals

### 3.1 Primary Goals

1. Implement a Hermes-compatible local memory provider plugin named `mike_memory`.
2. Store all memory data locally using SQLite, Qdrant, and Markdown files.
3. Automatically prefetch relevant memories before each Hermes turn.
4. Automatically sync conversation turns after Hermes responses.
5. Extract durable candidate memories from conversations and captures.
6. Retrieve memories using multiple signals:
   - semantic similarity
   - keyword/full-text match
   - entity match
   - recency
   - scope/project relevance
   - source trust
7. Inject only concise, useful memory context into Hermes responses.
8. Log what was recalled, injected, created, updated, archived, or rejected.
9. Provide explicit tools for Hermes to search, add, update, archive, and inspect memories.
10. Provide a safe migration path to future backends such as Mem0 OSS, hosted Mem0, Hindsight, or another provider.

### 3.2 Secondary Goals

1. Index Obsidian/Markdown wiki notes.
2. Support mobile capture later through Telegram, voice notes, or file drop.
3. Support content workflows for LinkedIn posts, internal briefs, long articles, and thesis development.
4. Detect recurring themes, stale ideas, contradictions, and project momentum.
5. Create generated briefings and reviews from local memory.

---

## 4. Non-Goals for Version 1

The first implementation must not attempt to build everything at once.

Do not implement these in the first version unless the core memory provider is already passing tests:

- Full Telegram bot.
- Full n8n automation.
- Complex UI.
- Multi-user permissions.
- Hosted cloud sync.
- Publishing workflows.
- Calendar integration.
- Email integration.
- Knowledge graph visualization.
- Fully automatic deletion.
- Replacement of Hermes core memory files.
- Patching Hermes core unless absolutely necessary.
- Long-form ingestion of books, lecture transcripts, and large research corpora is not part of Version 1, but the Version 1 data model and retrieval architecture must leave room for this future capability.

---

## 5. Architectural Principles

### 5.1 Local First

All raw data, extracted memories, embeddings, indexes, logs, and generated outputs must be stored locally by default.

The system must work without internet access once dependencies are installed and local models are available.

### 5.2 Durable Across Hermes Updates

The provider must be implemented as a Hermes MemoryProvider plugin, not a fragile side script and not a direct patch to Hermes core.

The plugin and data must live outside disposable containers or inside mounted persistent volumes.

### 5.3 Raw Events Are Sacred

The system must preserve raw inputs before summarizing, extracting, deduplicating, or reclassifying them.

Never overwrite raw event history.

### 5.4 Memory Is Not Just RAG

Qdrant vector search alone is insufficient. The system must distinguish:

- raw events
- extracted candidate memories
- accepted memories
- archived/superseded memories
- injected context
- generated outputs

### 5.5 Personal Memory and External Knowledge Are Different

The system must distinguish Mike's personal memory from external knowledge. Books, lecture transcripts, articles, and research materials may inform Hermes, but they are not automatically treated as Mike's beliefs, preferences, decisions, or durable personal memories.

### 5.6 Additive First, Supersede Later

Memory extraction should initially be ADD-only. Do not aggressively update/delete facts. If a fact becomes stale, contradicted, or replaced, mark it with `status=superseded` or `status=stale` and link it to the replacement.

### 5.7 Minimal Context Injection

The provider must avoid stuffing large memory dumps into the prompt.

Inject only the most relevant, concise, scoped memories with source labels.

### 5.8 Bad-Day Design

The system must tolerate inconsistent input, unprocessed captures, stale project notes, and imperfect organization.

When uncertain, the system should file safely, flag for review, and continue.



---

## 6. System Context

### 6.1 Existing Environment

Assume the user has:

- Hermes running in Docker on Spark 2.
- Qdrant running locally on Spark 2, currently not in active use.
- Open WebUI already in the stack.
- Local LLM serving through vLLM/Atlas/Qwen on Spark hardware.
- Ollama may be available for embeddings, or can be installed.
- Obsidian or Markdown-based wiki is desired as the human-readable memory layer.
- Synology backup is available for persistent backups.

### 6.2 Preferred First Embedding Model

For Version 1, prefer:

- `nomic-embed-text` through Ollama
- vector dimension: 768
- Qdrant distance: cosine

The embedding provider should be configurable so it can later be replaced by an OpenAI-compatible embedding endpoint, vLLM embedding endpoint, or another local embedding model.

---

## 7. Proposed Repository Layout

The implementation should prefer a layout like this:

```text
agent-platform/
  memory/
    vault/
      00_CAPTURE/
      01_ACTIVE/
      02_WIKI/
      03_RESOURCES/
      04_SYSTEM/
      05_QUEUE/
      06_GENERATED/
      07_ARCHIVE/
    db/
      memory.sqlite
    logs/
      ingest.log
      retrieval.log
      injection.log
      extraction.log
    config/
      mike_memory.yaml
    scripts/
      init_memory_db.py
      ingest_markdown.py
      search_memory.py
      backup_memory.sh
  agent-dev/
    plugins/
      memory/
        mike_memory/
          __init__.py
          plugin.yaml
          README.md
          provider.py
          store.py
          retriever.py
          extractor.py
          schemas.py
          cli.py
          tests/
```

If the Hermes plugin discovery mechanism requires a different location, follow Hermes conventions but keep persistent data in `~/agent-platform/memory`.

---

## 8. Obsidian / Wiki Vault Structure

Create and support this vault structure:

```text
00_CAPTURE/
  raw/
  voice/
  links/
  screenshots/

01_ACTIVE/
  projects/
    hermes-memory-system/
    ai-native-pm-company/
    internal-ai-credibility/
    reachy-local-agent/
  content-series/
    business-memory/
    ai-native-property-management/
    agentic-operating-models/
  daily/

02_WIKI/
  concepts/
  frameworks/
  people/
  companies/
  events/
  real-estate/
  ai-lab/
  technical-runbooks/

03_RESOURCES/
  articles/
  x-bookmarks/
  research/
  references/
  transcripts/

04_SYSTEM/
  HERMES.md
  MEMORY_POLICY.md
  workflows/
  prompts/
  skills/
  logs/

05_QUEUE/
  develop/
  research/
  summarize/
  decide/
  draft/

06_GENERATED/
  briefings/
  weekly-reviews/
  drafts/
  analyses/
  project-health/
  content-ideas/

07_ARCHIVE/
  processed-captures/
  completed-projects/
  stale-ideas/
  old-drafts/
```

Version 1 does not need to fully process every folder, but it must support indexing Markdown files from at least:

- `00_CAPTURE`
- `01_ACTIVE`
- `02_WIKI`
- `03_RESOURCES`
- `04_SYSTEM`

---

## 9. Core Operating Files

### 9.1 `HERMES.md`

Create a system context file at:

```text
memory/vault/04_SYSTEM/HERMES.md
```

Minimum content:

```markdown
# HERMES Operating Context

## Identity
Name: Mike Sebastian
Role: Industry Principal at AppFolio
Primary domains: property management, investment management, AI-native operations, real estate technology

## Current Strategic Themes
1. Business memory
2. AI-native property management company
3. Agentic workflows for real estate operators
4. Internal AI credibility through practical systems
5. Local AI lab / Hermes / Reachy as prototype environment

## Active Projects
- Hermes idea and memory system
- AI-native PM company thesis
- LinkedIn thought leadership system
- Internal AI workflow credibility plan
- Reachy local agent interface
- Voice Agent pipeline with reachy mini robot

## Writing Voice
Direct, strategic, practical, reflective.
Avoid hype.
Prefer novel but actionable ideas.
Write for property management executives, investment managers, SaaS leaders, and internal cross-functional partners.

## Operating Rules
- Never delete files; archive them.
- Preserve raw capture before summarizing.
- Always separate raw notes from interpreted notes.
- When uncertain, place in 00_CAPTURE and flag for review.
- Do not publish or send anything without Mike's review.
- Prefer concise daily outputs.
- Surface patterns, contradictions, and recurring themes.
- Convert strong ideas into reusable frameworks.

## Current Priorities
1. Build reliable mobile idea capture.
2. Turn captured ideas into LinkedIn posts and longer thesis material.
3. Create a working business-memory prototype through Hermes.
```

### 9.2 `MEMORY_POLICY.md`

Create a policy file at:

```text
memory/vault/04_SYSTEM/MEMORY_POLICY.md
```

Minimum content:

```markdown
# MEMORY_POLICY.md

## Save as durable memory when:
- It describes Mike's long-term goals.
- It describes a recurring writing theme.
- It changes how Hermes should help Mike.
- It describes an active project or strategic priority.
- It captures a reusable framework.
- It reflects a repeated preference or pattern.

## Do not save as durable memory when:
- It is a temporary task.
- It is a random article summary.
- It is a one-off opinion.
- It is raw, unprocessed capture.
- It is sensitive or personal without explicit instruction.

## Promote to wiki when:
- The idea appears 3+ times.
- It connects to an active thesis.
- It can become a reusable concept.
- It may support content, internal work, or product strategy.

## Archive when:
- It is processed.
- It is stale but potentially useful.
- It is no longer active but may become relevant later.
```

---

## 10. Data Model

Use SQLite as the durable control plane.

### 10.1 Tables

#### `raw_events`

Stores every raw event or turn before interpretation.

Required fields:

```text
id TEXT PRIMARY KEY
source TEXT NOT NULL              -- chat, obsidian, telegram, file, generated, manual
source_ref TEXT                    -- file path, conversation id, message id, etc.
role TEXT                          -- user, assistant, system, capture, file
content TEXT NOT NULL
content_hash TEXT NOT NULL
created_at TEXT NOT NULL
metadata_json TEXT
status TEXT DEFAULT 'active'       -- active, processed, archived, ignored
```

#### `memories`

Stores extracted memory facts or durable notes.

Required fields:

```text
id TEXT PRIMARY KEY
memory_type TEXT NOT NULL          -- preference, project, decision, fact, content_theme, technical_setup, open_loop, relationship, concept
scope TEXT NOT NULL                -- user, project, content, technical, business, session
title TEXT
summary TEXT NOT NULL
canonical_text TEXT NOT NULL
source_event_ids TEXT              -- JSON array
source_paths TEXT                  -- JSON array
entities_json TEXT                 -- JSON array
tags_json TEXT                     -- JSON array
confidence REAL DEFAULT 0.5
trust_score REAL DEFAULT 0.5
created_at TEXT NOT NULL
updated_at TEXT NOT NULL
last_recalled_at TEXT
status TEXT DEFAULT 'active'       -- active, stale, superseded, archived, rejected
supersedes_id TEXT
superseded_by_id TEXT
qdrant_collection TEXT
qdrant_point_id TEXT
```

#### `entities`

Tracks people, projects, concepts, companies, events, systems, tools.

```text
id TEXT PRIMARY KEY
entity_type TEXT NOT NULL          -- person, project, concept, company, event, system, tool, model
name TEXT NOT NULL
aliases_json TEXT
description TEXT
created_at TEXT NOT NULL
updated_at TEXT NOT NULL
status TEXT DEFAULT 'active'
```

#### `memory_entities`

Many-to-many linking table.

```text
memory_id TEXT NOT NULL
entity_id TEXT NOT NULL
relation_type TEXT                 -- about, mentions, depends_on, contradicts, supports
PRIMARY KEY (memory_id, entity_id, relation_type)
```

#### `retrieval_log`

Logs all retrievals.

```text
id TEXT PRIMARY KEY
query TEXT NOT NULL
query_context_json TEXT
retrieved_memory_ids TEXT          -- JSON array
scores_json TEXT
created_at TEXT NOT NULL
latency_ms INTEGER
```

#### `injection_log`

Logs injected memories.

```text
id TEXT PRIMARY KEY
turn_id TEXT
memory_ids TEXT                    -- JSON array
injected_text TEXT
token_estimate INTEGER
created_at TEXT NOT NULL
```

#### `feedback`

Optional user/agent feedback about memory quality.

```text
id TEXT PRIMARY KEY
memory_id TEXT
retrieval_id TEXT
feedback_type TEXT                 -- useful, irrelevant, wrong, stale, missing
details TEXT
created_at TEXT NOT NULL
```

---

## 11. Qdrant Collections

Create Qdrant collections for distinct memory domains.

### 11.1 Required Collections

```text
hermes_memories
hermes_wiki
hermes_captures
hermes_projects
```

### 11.2 Optional Future Collections

```text
hermes_content
hermes_people
hermes_decisions
hermes_runbooks
hermes_sources
```

### 11.3 Vector Configuration

Default:

```json
{
  "vectors": {
    "size": 768,
    "distance": "Cosine"
  }
}
```

### 11.4 Payload Requirements

Every Qdrant point must include:

```json
{
  "memory_id": "...",
  "source_path": "...",
  "title": "...",
  "memory_type": "...",
  "scope": "...",
  "tags": [],
  "entities": [],
  "status": "active",
  "created_at": "...",
  "updated_at": "...",
  "text": "..."
}
```

---

## 12. Hermes MemoryProvider Requirements

The provider must implement the Hermes MemoryProvider interface as fully as practical.

### 12.1 Required Provider Methods / Hooks

Implement:

```python
initialize(config, hermes_home)
get_tool_schemas()
handle_tool_call(name, arguments)
system_prompt_block()
prefetch(query, context=None)
queue_prefetch(query, context=None)
sync_turn(user_message, assistant_message, metadata=None)
on_session_end(messages, metadata=None)
on_memory_write(action, target, content, metadata=None)
```

If the exact interface in the installed Hermes version differs, adapt to the installed interface while preserving the same behavior.

### 12.2 Required Provider Tools

Expose tools to Hermes:

#### `mike_memory_search`

Search local memory.

Input:

```json
{
  "query": "string",
  "scope": "optional string",
  "memory_type": "optional string",
  "limit": "optional integer"
}
```

Output:

```json
{
  "results": [
    {
      "memory_id": "string",
      "title": "string",
      "summary": "string",
      "source": "string",
      "score": 0.0,
      "reason": "string"
    }
  ]
}
```

#### `mike_memory_add`

Add a durable memory manually.

Input:

```json
{
  "memory_type": "string",
  "scope": "string",
  "title": "string",
  "summary": "string",
  "canonical_text": "string",
  "tags": [],
  "entities": []
}
```

#### `mike_memory_profile`

Return concise user/project profile context.

Input:

```json
{
  "scope": "optional string"
}
```

#### `mike_memory_related`

Find related memories to a memory or topic.

Input:

```json
{
  "memory_id": "optional string",
  "query": "optional string",
  "limit": 10
}
```

#### `mike_memory_archive`

Archive a memory without deleting it.

Input:

```json
{
  "memory_id": "string",
  "reason": "string"
}
```

#### `mike_memory_feedback`

Record feedback on memory quality.

Input:

```json
{
  "memory_id": "string",
  "feedback_type": "useful|irrelevant|wrong|stale|missing",
  "details": "optional string"
}
```

---

## 13. Automatic Recall and Injection

### 13.1 Prefetch Behavior

Before each Hermes turn, the provider must:

1. Receive the current user message and available context.
2. Build a retrieval query.
3. Search local memory.
4. Rank results.
5. Return a compact memory block.

### 13.2 Injection Format

The injected memory block must be short and source-labeled.

Example:

```markdown
## Relevant Local Memory

- Mike is building Hermes as a local-first personal intelligence layer with Qdrant, SQLite, and Obsidian as core memory infrastructure. Source: hermes-memory-system.
- Mike prefers actionable, novel content ideas connected to AI-native property management and business memory. Source: writing-profile.
- Current priority: build reliable mobile capture before advanced automation. Source: HERMES.md.
- We will upload full books, notes, learnings and lecture transcripts later for use, recall and analysis
```

### 13.3 Injection Rules

The provider must:

- Inject no more than 8 memories by default.
- Prefer high-confidence active memories.
- Prefer project-scoped memories when a project is detected.
- Avoid injecting stale/superseded memories unless specifically relevant.
- Include source/path metadata when useful.
- Log every injection.

---

## 14. Retrieval Ranking Requirements

Retrieval must combine multiple signals.

### 14.1 Minimum Signals

Use at least:

```text
semantic_score
keyword_score
entity_score
recency_score
scope_score
trust_score
```

### 14.2 Suggested Formula

Implementation may start simple:

```text
final_score =
  0.45 * semantic_score +
  0.20 * keyword_score +
  0.15 * entity_score +
  0.10 * scope_score +
  0.05 * recency_score +
  0.05 * trust_score
```

This must be configurable.

### 14.3 Low-Confidence Rejection

If no result exceeds a configurable threshold, the provider must return no memory rather than injecting weak or misleading recall.

Default threshold:

```text
min_final_score = 0.35
```

---

## 15. Memory Extraction

### 15.1 Extraction Timing

The provider should support:

1. `sync_turn`: store raw turn immediately.
2. Background extraction: extract candidate memories asynchronously or after the response.
3. `on_session_end`: extract higher-quality session summaries and durable memories.

### 15.2 Extraction Prompt Requirements

Extraction must follow `MEMORY_POLICY.md`.

For each candidate memory, extract:

```json
{
  "memory_type": "preference|project|decision|fact|content_theme|technical_setup|open_loop|relationship|concept",
  "scope": "user|project|content|technical|business|session",
  "title": "short title",
  "summary": "short summary",
  "canonical_text": "durable memory phrased clearly",
  "entities": ["..."],
  "tags": ["..."],
  "confidence": 0.0,
  "reason_to_save": "why this should be remembered"
}
```

### 15.3 Rejection Rules

Do not save as durable memory when:

- It is a temporary one-off task.
- It is raw unprocessed capture.
- It is sensitive or personal without explicit instruction.
- Confidence is low.
- It duplicates an existing active memory without adding new information.

### 15.4 Duplicate Handling

If a candidate duplicates an existing memory:

- Do not create a duplicate by default.
- If it adds meaningful new information, add a linked memory or update relationship metadata.
- If it contradicts an existing memory, mark both for review or set relation `contradicts`.

---

## 16. Markdown / Obsidian Indexing

### 16.1 Ingestion

The provider must include a CLI or script to index Markdown files from the vault.

Required command behavior:

```bash
python -m mike_memory.cli ingest --vault ~/agent-platform/memory/vault
```

or equivalent.

### 16.2 Chunking

Chunk Markdown by headings and paragraphs.

Requirements:

- Preserve source path.
- Preserve heading hierarchy when possible.
- Keep chunks small enough for retrieval.
- Store chunk text in Qdrant payload.
- Store document metadata in SQLite.

### 16.3 Re-indexing

Re-indexing must be idempotent.

If the same file has not changed, do not create duplicate points.

Use content hashes.

---

### 17. Future Epic: Long-Form Knowledge Ingestion

### Purpose

The memory system must eventually support ingestion of long-form materials such as books, lecture transcripts, podcast transcripts, conference notes, research papers, and extended personal notes. These sources may be too large to load directly into a model context window and must be processed into structured, searchable, attributable memory artifacts.

This feature is not required for the MVP, but the architecture must avoid decisions that would make long-form ingestion difficult later.

### User Story

As Mike, I want to load long-form sources such as books, lecture transcripts, and extended notes into the Hermes memory system so that Hermes can retrieve relevant concepts, summarize sections, connect ideas to my existing work, and cite the original source when answering or generating content.

### Requirements

1. The system shall support ingestion of large text files, Markdown files, PDFs converted to text, lecture transcripts, and structured notes.
2. The system shall preserve source metadata, including title, author/speaker, date, source type, file path, and ingestion date.
3. The system shall split long sources into semantically meaningful chunks rather than arbitrary fixed-size chunks when possible.
4. The system shall preserve hierarchy when available, including book title, chapter, section, timestamp, heading, or page reference.
5. The system shall store raw source references separately from extracted memories.
6. The system shall distinguish between:
   - external source knowledge
   - Mike’s personal notes
   - Hermes-generated summaries
   - durable personal memories
7. The system shall not automatically promote external source content into durable personal memory unless it is explicitly connected to Mike’s projects, preferences, decisions, or recurring themes.
8. The system shall generate source-level summaries, chapter/section summaries, and concept-level extractions.
9. The system shall support retrieval with source attribution so Hermes can say where an idea came from.
10. The system shall support later re-indexing when chunking, embedding models, or metadata schemas change.
11. The system shall allow a source to be archived, disabled, or excluded from retrieval without deleting the raw source.
12. The system shall log all ingestion actions.

### Data Model Additions

Add a `sources` table:

- `id`
- `title`
- `author_or_speaker`
- `source_type`
- `source_path`
- `source_date`
- `ingested_at`
- `status`
- `summary`
- `metadata_json`

Add a `source_chunks` table:

- `id`
- `source_id`
- `chunk_index`
- `heading`
- `chapter`
- `section`
- `page_start`
- `page_end`
- `timestamp_start`
- `timestamp_end`
- `text`
- `summary`
- `qdrant_point_id`
- `created_at`

Add a `source_concepts` table:

- `id`
- `source_id`
- `concept_name`
- `summary`
- `related_memory_ids`
- `related_project_ids`
- `created_at`

### Qdrant Collection Addition

Add a dedicated collection:

`hermes_sources`

This collection stores embedded chunks from long-form external sources. It must remain separate from `hermes_wiki`, `hermes_captures`, and `hermes_projects` so retrieval can distinguish external knowledge from Mike’s own memory.

### Retrieval Behavior

When Hermes retrieves from long-form sources, it must include:

- source title
- author/speaker when available
- chapter/section/page/timestamp when available
- short excerpt or summary
- relevance score
- reason the source was retrieved

Hermes must avoid presenting external-source content as Mike’s own memory unless Mike has separately captured, endorsed, or synthesized that idea into his own notes.

### Acceptance Criteria

- Given a long lecture transcript, the system can ingest it, chunk it, summarize major sections, and retrieve relevant segments by semantic query.
- Given a book-length text file, the system can preserve chapter/section structure when headings are available.
- Given a query such as “What have I loaded about business memory or organizational memory?”, Hermes can retrieve relevant passages from long-form sources and distinguish them from Mike’s own notes.
- Given a generated content draft, Hermes can cite which long-form source influenced a claim or framework.
- Given a source that should no longer be used, Mike can disable it from retrieval without deleting it.
- Re-ingesting the same source does not create uncontrolled duplicates.

---

## 18. CLI Requirements

Provide commands similar to:

```bash
mike-memory init
mike-memory status
mike-memory ingest
mike-memory search "query"
mike-memory add --type preference --scope user --text "..."
mike-memory archive MEMORY_ID --reason "..."
mike-memory backup
mike-memory doctor
```

If integrated into Hermes CLI, also support:

```bash
hermes memory status
hermes memory setup
hermes plugins
```

as appropriate for the installed Hermes version.

---

## 19. Configuration

Create a YAML config:

```yaml
provider:
  name: mike_memory
  enabled: true

paths:
  base_dir: /home/mike/agent-platform/memory
  vault_dir: /home/mike/agent-platform/memory/vault
  sqlite_path: /home/mike/agent-platform/memory/db/memory.sqlite
  logs_dir: /home/mike/agent-platform/memory/logs

qdrant:
  url: http://localhost:6333
  collections:
    memories: hermes_memories
    wiki: hermes_wiki
    captures: hermes_captures
    projects: hermes_projects
  vector_size: 768
  distance: Cosine

embeddings:
  provider: ollama
  base_url: http://localhost:11434
  model: nomic-embed-text
  dimension: 768

retrieval:
  default_limit: 8
  max_injected_memories: 8
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
  mode: local_llm
  model_profile: qwen
  min_confidence: 0.65
  add_only: true

privacy:
  cloud_allowed: false
  redact_sensitive_by_default: true
  never_send_raw_events_to_cloud: true

logging:
  retrieval: true
  injection: true
  extraction: true
```

---

## 20. Security and Privacy Requirements

1. Default mode must be local-only.
2. No raw events, memories, embeddings, or notes may be sent to hosted APIs unless explicitly configured.
3. Cloud-backed memory providers must be disabled by default.
4. The system must clearly log if any cloud endpoint is used.
5. The provider must preserve raw captures locally.
6. The provider must support backup of SQLite database, Qdrant data, and Markdown vault.
7. The provider must never delete memory permanently by default.
8. Archive is allowed; delete requires explicit user command and confirmation.
9. Secrets must not be hardcoded.
10. Config must support environment variables for endpoints and keys.

---

## 21. User Stories and Acceptance Criteria

### Story 1: Local Memory Provider Activation

As Mike, I want Hermes to load `mike_memory` as an external memory provider so that memory works through Hermes' native plugin lifecycle.

Acceptance criteria:

- GIVEN Hermes is running
- WHEN `mike_memory` is configured as the memory provider
- THEN `hermes memory status` or equivalent must show the provider as active
- AND the provider must expose its tools to Hermes
- AND no Hermes core files must be modified manually

### Story 2: Raw Conversation Preservation

As Mike, I want raw conversation turns stored before extraction so that I never lose the original context.

Acceptance criteria:

- WHEN Mike sends a message and Hermes responds
- THEN the provider must write the user message and assistant response to `raw_events`
- AND the raw event must include source, role, timestamp, hash, and metadata
- AND this must happen even if extraction fails

### Story 3: Automatic Memory Recall

As Mike, I want Hermes to automatically recall relevant memories before answering.

Acceptance criteria:

- GIVEN existing memories about a project
- WHEN Mike asks about that project in a later session
- THEN the provider must retrieve relevant active memories
- AND inject a concise memory block before the response
- AND log the injected memory IDs

### Story 4: Low-Confidence Suppression

As Mike, I want Hermes to avoid injecting irrelevant memories.

Acceptance criteria:

- GIVEN a query unrelated to stored memory
- WHEN prefetch runs
- THEN the provider must return no memory if all results are below threshold
- AND log the low-confidence retrieval

### Story 5: Markdown Wiki Indexing

As Mike, I want Hermes to search my Obsidian/wiki notes.

Acceptance criteria:

- GIVEN Markdown files in `02_WIKI`
- WHEN the ingest command runs
- THEN the files must be chunked, embedded, and stored in Qdrant
- AND source paths must be preserved
- AND repeated ingestion must not create duplicate points

### Story 6: Durable Memory Extraction

As Mike, I want Hermes to extract durable facts from conversations only when they meet the memory policy.

Acceptance criteria:

- GIVEN a conversation with durable project or preference information
- WHEN the extraction process runs
- THEN candidate memories must be created with type, scope, title, summary, entities, tags, confidence, and source events
- AND low-confidence or temporary facts must be rejected
- AND rejected candidates must be logged

### Story 7: Explicit Memory Search Tool

As Mike, I want Hermes to explicitly search memory when needed.

Acceptance criteria:

- WHEN Hermes calls `mike_memory_search`
- THEN the provider must return ranked memory results with title, summary, score, and source
- AND the tool must support optional scope and memory type filters

### Story 8: Archive Never Delete

As Mike, I want old or stale memories archived instead of deleted.

Acceptance criteria:

- WHEN a memory is archived
- THEN its status must change to `archived`
- AND Qdrant payload/status must update if needed
- AND raw source events must remain untouched

### Story 9: Bad-Day Capture Compatibility

As Mike, I want the memory system to accept messy captures without making me classify them.

Acceptance criteria:

- GIVEN a raw note in `00_CAPTURE`
- WHEN ingestion or capture processing runs
- THEN the item must be preserved, classified, and made searchable
- AND uncertain classification must be flagged rather than dropped

### Story 10: Backup and Recovery

As Mike, I want memory to survive container rebuilds and system updates.

Acceptance criteria:

- GIVEN Docker containers are rebuilt
- WHEN persistent volumes are mounted
- THEN SQLite, Qdrant data, Markdown vault, and logs must remain intact
- AND the `doctor` command must verify all paths and services

---

## 22. Testing Requirements

### 22.1 Unit Tests

Implement tests for:

- SQLite schema creation
- event insertion
- memory insertion
- duplicate detection
- keyword search
- Qdrant upsert
- retrieval ranking
- low-confidence rejection
- archive behavior
- config loading

### 21.2 Integration Tests

Implement tests for:

- provider initialization
- tool schema exposure
- `mike_memory_search`
- `sync_turn`
- `prefetch`
- Markdown ingestion
- Qdrant retrieval
- no-cloud default behavior

### 22.3 Golden Test Dataset

Create a small fixture dataset with memories about:

- Hermes memory system
- business memory
- AI-native property management
- Reachy local agent
- Spark/vLLM technical setup
- Mike's writing voice

Example test query:

```text
What have I been saying about business memory?
```

Expected behavior:

- Return memories about business memory.
- Prefer active concept/project memories.
- Do not return unrelated technical runbooks.

---

## 23. Observability

The system must log:

- raw event writes
- memory extraction attempts
- accepted memories
- rejected memories
- Qdrant indexing
- retrieval queries
- retrieval scores
- injected memories
- provider errors
- cloud endpoint usage if any

Logs should be stored in:

```text
~/agent-platform/memory/logs/
```

---

## 24. Failure Behavior

The provider must fail safely.

If Qdrant is down:

- raw events still write to SQLite
- provider returns no injected memory
- Hermes chat continues

If SQLite is down:

- provider disables writes
- logs error
- Hermes chat continues

If embedding service is down:

- raw events still write
- retrieval falls back to SQLite FTS if possible
- ingestion pauses

If extraction model fails:

- raw events remain stored
- extraction can be retried later

---

## 25. Phase Plan

### Phase 0: Research and Repo Grounding

Codex must first inspect:

- current Hermes version
- plugin discovery mechanism
- current memory provider interface
- Docker compose paths
- current Qdrant service
- current Hermes config location
- current Python environment and dependencies

Do not assume interface details without checking the repo.

### Phase 1: Local Substrate

Deliver:

- persistent folder structure
- SQLite schema
- Qdrant collection creation
- config file
- `doctor` command
- basic backup command

Exit criteria:

- `mike-memory doctor` confirms SQLite, Qdrant, vault paths, and embedding endpoint.

### Phase 2: Markdown Ingestion and Search

Deliver:

- Markdown ingestion
- chunking
- embedding
- Qdrant upsert
- SQLite registry
- CLI search

Exit criteria:

- `mike-memory search "business memory"` returns the expected local wiki note.

### Phase 3: Hermes MemoryProvider Plugin Skeleton

Deliver:

- `plugin.yaml`
- provider class
- provider initialization
- tool schemas
- basic search tool
- Hermes config instructions

Exit criteria:

- Hermes sees provider as active and exposes `mike_memory_search`.

### Phase 4: Automatic Prefetch and Injection

Deliver:

- `prefetch`
- ranking
- injection block formatting
- retrieval/injection logging
- low-confidence rejection

Exit criteria:

- In a Hermes session, asking about a stored topic injects the relevant local memory automatically.

### Phase 5: Raw Turn Sync and Extraction

Deliver:

- `sync_turn`
- raw event storage
- local LLM extraction
- memory policy enforcement
- duplicate handling
- accepted/rejected memory logs

Exit criteria:

- A conversation about a durable project produces candidate memories and searchable durable memories.

### Phase 6: Polish and Operations

Deliver:

- tests
- README
- setup instructions
- backup/recovery docs
- sample config
- troubleshooting guide

Exit criteria:

- Fresh clone/container rebuild can restore and run memory provider using persistent data.

---

## 26. Implementation Guidance for Codex

### 26.1 Do First

1. Locate Hermes MemoryProvider interface in the installed source.
2. Locate examples of existing provider plugins.
3. Create an implementation plan using the actual interface.
4. Build minimal working path before extraction:
   - SQLite
   - Qdrant
   - Markdown ingestion
   - explicit memory search tool
   - Hermes provider activation

### 26.2 Avoid

- Do not hardcode Mike's secrets.
- Do not call hosted APIs by default.
- Do not store data only inside a container filesystem.
- Do not delete raw events.
- Do not implement Telegram before core recall works.
- Do not overwrite Hermes core files unless no plugin route exists.
- Do not rely only on vector similarity.
- Do not inject memory without a confidence threshold.

### 26.3 Prefer

- Small modules.
- Clear interfaces.
- Local-only defaults.
- Idempotent ingestion.
- Explicit logs.
- Tests before automation.
- Config-driven endpoints.
- Backup-friendly file paths.

---

## 27. Open Questions for Implementation

Codex should answer these during `/plan`:

1. What exact Hermes MemoryProvider interface exists in the installed version?
2. Where should external memory plugins be placed for this deployment?
3. Does Hermes Gateway load memory providers the same way as Hermes CLI?
4. Should the plugin run inside the Hermes container or as a local service reachable from the container?
5. Can the Hermes container reach Qdrant at `http://host.docker.internal:6333`, Docker service name, or localhost?
6. Can the Hermes container reach Ollama embeddings at `http://host.docker.internal:11434` or another endpoint?
7. What volume mounts are needed for `~/agent-platform/memory`?
8. What is the safest command to test provider activation without disrupting current Hermes service?

---

## 28. Success Definition

The feature is successful when Mike can do this:

1. Add or create Markdown notes about Hermes, business memory, Reachy, or AI-native property management.
2. Run an ingestion command.
3. Ask Hermes later about one of those topics.
4. Hermes automatically recalls and injects the right memory without Mike explicitly telling it to search.
5. Hermes can also explicitly search memory through a tool.
6. Conversations create raw events.
7. Durable facts can be extracted into local memory.
8. All memory survives container rebuilds and Hermes updates.
9. No cloud service is required.
10. The design can later swap or add Mem0 OSS/hosted as a backend behind the same provider contract.
11. Mike can ingest books and transcripts into memory easily with a tool.

---

## 29. Suggested `/specify` Prompt

Paste this into Spec Kit as the initial `/specify` content:

```text
Build a local-first Hermes memory provider plugin named mike_memory. It must provide durable cross-session memory for Hermes using local SQLite, Qdrant, and an Obsidian-compatible Markdown vault. The provider must integrate through Hermes' MemoryProvider plugin interface, not by patching Hermes core, so it survives Hermes updates.

The system must preserve raw conversation events, extract durable candidate memories according to a MEMORY_POLICY.md file, index Markdown wiki notes, retrieve relevant memories using semantic search plus keyword/entity/recency/scope ranking, and automatically prefetch/inject concise memory context before Hermes responses. It must expose explicit tools for search, add, archive, feedback, profile, and related-memory lookup.

Default behavior must be local-only. No raw events, notes, memories, or embeddings may be sent to hosted APIs unless explicitly configured. Qdrant is already running locally but not yet in use. The first version should use SQLite as the control plane, Qdrant as the vector index, Markdown/Obsidian as the human-readable wiki, and a configurable local embedding endpoint such as Ollama nomic-embed-text.

The implementation must be durable across Docker rebuilds and Hermes updates. Persistent data should live under ~/agent-platform/memory. The plugin should include CLI commands for init, status/doctor, ingest, search, add, archive, backup, and test. It should include tests for schema creation, ingestion, retrieval, ranking, low-confidence suppression, provider activation, and no-cloud default behavior.

The first milestone is not Telegram, n8n, or UI. The first milestone is a complete vertical slice: create the local substrate, ingest a Markdown note, search it from the CLI, activate the provider in Hermes, and have Hermes automatically recall and inject the relevant local memory in a later turn.
```

---

## 30. Suggested `/plan` Technical Preferences

When running `/plan`, provide these preferences:

```text
Use Python for the provider and memory service because Hermes providers are Python-based. Use SQLite for durable metadata and event storage. Use Qdrant for vector search. Use SQLite FTS5 or another local full-text index for keyword retrieval. Use Ollama nomic-embed-text as the default local embedding provider, but make embedding provider configurable. Use YAML for config. Keep all persistent data under ~/agent-platform/memory and ensure Docker volume mounts preserve it.

Do not modify Hermes core unless the installed version lacks plugin support. Prefer the official Hermes MemoryProvider plugin interface. Inspect existing Hermes memory providers before implementing. Implement small modules: provider.py, store.py, retriever.py, extractor.py, schemas.py, cli.py. Add pytest tests. Provide a README with setup, Docker networking notes, backup, troubleshooting, and restore instructions.

Default to no cloud access. Add a config field cloud_allowed=false and fail closed if a hosted endpoint is configured while cloud_allowed is false.
```

---

## 31. Suggested Constitution Addendum

Add this to the project constitution if appropriate:

```markdown
## Memory and Privacy Constitution

1. Local-first memory is a non-negotiable architectural principle.
2. Raw user data must never be sent to cloud services unless explicitly configured and documented.
3. Raw events must be preserved before summarization, extraction, or deduplication.
4. The system must archive rather than delete by default.
5. Memory recall must be explainable: every injected memory must be source-linked and logged.
6. The memory provider must integrate through stable extension points, not fragile patches to core dependencies.
7. Retrieval must use confidence thresholds to avoid false memory injection.
8. Implementations must include backup and recovery paths for SQLite, Qdrant, and Markdown vault data.
```
