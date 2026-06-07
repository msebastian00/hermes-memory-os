---
title: Obsidian Memory Systems for Hermes Agents
created: 2026-06-03
updated: 2026-06-03
type: concept
tags: [obsidian, memory, second-brain, chief-of-staff, vault-organization, hermes, integration, cyrilxbt]
sources: [https://x.com/cyrilXBT/status/2059461814333673705, https://x.com/cyrilXBT/status/2058373087330959829, x-bookmarks-page4.json]
confidence: high
---

# Obsidian Memory Systems for Hermes Agents

Obsidian as the persistent, queryable second brain is the highest-leverage Hermes integration. This page captures two key posts from @cyrilXBT (May 2026) that directly address the user's interest in vault organization and Chief of Staff agent architectures.

**Exact sources**:
- https://x.com/cyrilXBT/status/2059461814333673705 — "$0 Chief of Staff System" (Obsidian + Vellum + Readwise + N8N)
- https://x.com/cyrilXBT/status/2058373087330959829 — "Obsidian Vault Organization Guide: Retrieval-First System" (reposted by Charly Wargnier)

Cross-references: [[hermes-agent-best-practices]] (Obsidian as #1 integration), [[hermes-agent]] skill, [[mcp]] for tool integration, [[obsidian]].

## 1. Retrieval-First Vault Organization (Charly Wargnier repost of CyrilXBT)

Core principle: "You do not organize a vault to put things away neatly. You organize a vault to get things back quickly."

### The Four Things You Always Know About a Note
- Type of content (project, daily, book, meeting, etc.)
- When it was created/used (date or period)
- Topic it relates to
- Status (active, complete, archived, waiting)

Every organizational decision must answer: *Does this make retrieval faster?*

### Recommended Folder Structure (5–8 Top-Level Folders)
```
00 - INBOX/          # Temporary processing queue (use numbered prefix)
01 - NOTES/
    daily/
    meetings/
    books/
    courses/
02 - PROJECTS/       # One subfolder per active project (move to ARCHIVE when done)
03 - AREAS/          # Ongoing responsibilities (health, finances, career, etc.)
04 - RESOURCES/      # Reference material (topics, people, tools)
05 - ARCHIVE/        # Completed/outdated items (never delete)
06 - SYSTEM/         # Templates, MOCs, config files
```

**Key Rules**:
- Folders represent broad *content types*, not specific topics
- Projects have end dates; Areas do not
- Archive everything rather than deleting

### File Naming Convention
**Format:** `YYYY-MM-DD-[TYPE]-[TOPIC].md`

Examples:
- `2026-05-20-daily-wednesday.md`
- `2026-05-18-project-website-launch.md`
- `2026-05-15-meeting-client-quarterly-review.md`
- `2026-04-28-resource-claude-prompting-techniques.md`

Benefits: Chronological sorting, date-based retrieval, prevents duplicates.

### Properties (YAML Frontmatter)
**Universal Properties (every note)**:
```yaml
---
type: [daily|meeting|project|area|resource|book|course|idea|task]
status: [active|complete|archived|reference|waiting]
date: 2026-05-20
tags: [topic1, topic2]
---
```

**Type-Specific Properties**:
- Projects: `deadline`, `priority`, `next_action`, `completion`
- Books: `author`, `finished`, `rating`, `key_insight`
- Meetings: `attendees`, `decisions`, `actions`
- Resources: `topic`, `source`, `reliability`

**Status** is the most powerful filter property.

### Tagging System (Three Categories)
| Category     | Prefix       | Purpose                     | Example                  |
|--------------|--------------|-----------------------------|--------------------------|
| Topic        | (none)       | Subject matter              | `#productivity`          |
| Status       | `status/`    | Workflow stage              | `#status/active`         |
| Project      | `project/`   | Links to specific projects  | `#project/website-launch`|

**Rule:** Only create a tag if it will appear on ≥5 notes.

### Maps of Content (MOCs)
Index notes that link to clusters of related notes rather than containing original content.

Example:
```markdown
# Productivity MOC

## Core Framework Notes
- [[The PARA Method Explained]]

## Book Notes
- [[Deep Work - Key Ideas]]

## Open Questions
- What is the relationship between energy and deep work?
```

Create an MOC when a topic exceeds ~20 notes.

### Daily Habits & Maintenance
**Inbox Processing (daily/weekly)**:
1. Identify content type → choose folder
2. Link to existing notes if relevant
3. Add properties + apply naming convention
4. Move out of INBOX

**Quarterly Vault Review**:
- Folder audit
- Tag audit
- Archive sweep
- Fix naming inconsistencies

**Search Strategy**:
- Full-text search — distinctive phrases
- Property search — `type:project status:active`
- Tag search — `#productivity` or `#status/active`

**Advanced: Claude / Hermes Integration**
Connect vault via Filesystem MCP or direct read for natural language queries:
- "Find all notes about pricing strategy from the last six months"
- "Show active projects with deadlines before July"

### Implementation Roadmap
| Timeframe   | Action                                      |
|-------------|---------------------------------------------|
| Week 1      | Create 8 folders                            |
| Week 2      | Apply to all new notes                      |
| Week 3      | Process INBOX backlog                       |
| Month 2     | Add tags + first MOC                        |
| Month 3     | First quarterly review                      |

The system transforms the vault from "another thing to manage" into a reliable thinking system where any note is findable in under 30 seconds.

## 2. $0 Chief of Staff System (Obsidian + Vellum + Readwise + N8N)

> "A chief of staff reads everything you've read, remembers everything you've forgotten, and briefs you every morning on what matters."

### Required Tools
- **Obsidian** (obsidian.md) — local markdown vault
- **Vellum** (vellum.ai) — prepaid credits, connects to vault
- **Readwise** (readwise.io) — captures highlights from articles/Kindle/Twitter/Pocket
- **N8N** (n8n.io) — automation for workflows and Telegram capture

### Vault Architecture (`CHIEF/`)
```
CHIEF/
├── 00-INBOX/               # raw unprocessed captures
├── 01-CAPTURES/
│   ├── articles/
│   ├── ideas/
│   ├── patterns/
│   ├── questions/
│   └── numbers/
├── 02-CONNECTIONS/         # synthesized insights
├── 03-PROJECTS/            # active work
└── 04-VELLUM/
    ├── VELLUM.md
    └── workflows/
```

**Key principle**: Organize by *type* (not topic) so cross-domain patterns are automatically discoverable.

### Essential Obsidian Plugins
- **Templater** — dynamic note formatting
- **Dataview** — database-style queries
- **Obsidian Git** — hourly auto-backup to private GitHub repo

### Automated Capture Setup
- **Articles**: Readwise browser extension → native Obsidian sync → `01-CAPTURES/articles/`
- **Quick capture**: Telegram bot + N8N workflow → `00-INBOX/`
  - Node 1: Telegram Trigger
  - Node 2: Code Node (filename + content template)
  - Node 3: Write File
- **Voice notes**: Whisper transcription → paste into Telegram bot

### VELLUM.md (Critical Context File)
Must include:
- Identity & current focus
- Vault structure explanation
- Current projects + stuck points
- Explicit instructions for Vellum ("Surface connections...", "Challenge my assumptions...")
- Weekly-updated "What I Am Reading And Thinking About Right Now"

### Four Core Workflows (saved in `04-VELLUM/workflows/`)
1. **Process Inbox** — routes & sharpens raw captures
2. **Daily Brief** (auto 6am via N8N) — 3 connections + 1 pattern + 1 question
3. **Weekly Connections** — finds TYPE A–D connections across all captures
4. **Deep Research** — surfaces contradictions, missing perspectives, and unasked questions

### Daily Ritual (15 minutes)
1. 5 min raw capture (Telegram)
2. Run "Process Inbox"
3. Read auto-generated daily brief (before any apps)

### Weekly Ritual (Sunday)
Run Weekly Connections workflow → review new notes in `02-CONNECTIONS` → select top 2 insights.

### Compounding Effect
- **30 days**: Occasional forgotten insights surface
- **90 days**: Cross-month connections appear
- **6 months**: Complete record of belief evolution + pattern recognition that compounds intelligence

> "The intelligence you have after 6 months of this is not the same intelligence you started with."

## Hermes Integration Patterns

These two systems map directly onto Hermes capabilities:

- **Vault as long-term memory**: Use the retrieval-first structure + MOCs so Hermes (via Obsidian MCP or filesystem tools) can deterministically surface context for any agent in a swarm.
- **Chief of Staff as Hermes profile**: Create a dedicated `chief-of-staff` Hermes profile with Obsidian read/write, cron daily brief generation, and N8N/Telegram hooks.
- **Auto-think over vault**: Run the "Weekly Connections" and "Deep Research" workflows as Hermes cron jobs or Auto-think triggers.
- **Multi-agent memory sharing**: Different Hermes agents (researcher, executor, reviewer) all read from the same structured CHIEF/ vault using consistent type/status properties.
- **Skill authoring from patterns**: Save successful vault queries and connection workflows as reusable skills in the Hermes skill library.

**Related page4.json bookmarks**:
- Agentic reasoning survey (135+ pages) — reasoning layer over the memory vault
- Local Claude Code workflows — private full agent stack on top of Obsidian memory
- Document AI (LandingAI) — ingest external PDFs/PPTs into the `01-CAPTURES/` system

## Next Steps
- Implement the 00-INBOX / 01-CAPTURES / 02-CONNECTIONS structure in a test Hermes profile
- Wire N8N + Telegram capture into Hermes cron
- Create Dataview queries for "active projects" and "status/waiting" as Hermes tools
- Test Vellum-style daily brief generation via Hermes Auto-think + Obsidian export

---

**Provenance**: Direct extraction from the two provided X posts via web_extract on 2026-06-03. Integrated with Hermes best practices from [[hermes-agent-best-practices]] and page4.json agent bookmarks. ^[cyrilXBT posts + page4.json]

**See also**: [[hermes-agent-best-practices]], [[hermes-agent]], [[obsidian]]