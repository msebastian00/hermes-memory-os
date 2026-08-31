---
type: policy
status: active
date: 2026-07-07
policy: bookmark-ingestion
tags: [chief-of-staff, bookmarks, ingestion, resources, dedupe, relevance]
---

# Bookmark Ingestion Policy

## Purpose

This policy defines how Hermes should import, fetch, score, deduplicate, summarize, and route browser bookmarks, X bookmarks, article URLs, and overlapping source references into the vault.

Bookmarks are not knowledge yet. They are leads.

A bookmark becomes useful only after Hermes determines:

1. What source it points to
2. Whether full content can be read
3. Whether it is relevant to Mike's active projects, durable knowledge areas, or open questions
4. Whether it duplicates or overlaps existing material
5. Where the processed output belongs in the vault

## Required Inputs

Before processing bookmarks, read:

- /wiki/vault/04_SYSTEM/HERMES.md
- /wiki/vault/04_SYSTEM/CHIEF_OF_STAFF.md
- /wiki/vault/04_SYSTEM/MEMORY_POLICY.md
- /wiki/vault/04_SYSTEM/policies/BOOKMARK_INGESTION_POLICY.md
- /wiki/vault/04_SYSTEM/workflows/bookmark-ingestion.md

## Source Types

Use these source types:

- browser_bookmark
- x_bookmark
- article
- paper
- documentation
- video
- tool
- reference
- unknown

## Folder Roles

Raw unprocessed exports go here:

- 03_RESOURCES/x-bookmarks/raw
- 03_RESOURCES/articles/raw

Parsed/imported bookmark records go here:

- 03_RESOURCES/x-bookmarks/imported

Detailed processed article/resource notes go here:

- 03_RESOURCES/articles/processed

Queue items go here:

- 05_QUEUE/research
- 05_QUEUE/summarize
- 05_QUEUE/decide
- 05_QUEUE/develop
- 05_QUEUE/draft

Processing reports go here:

- 06_GENERATED/bookmark-imports

Only synthesized, reusable knowledge should be recommended for:

- 02_WIKI/concepts
- 02_WIKI/frameworks
- 02_WIKI/people
- 02_WIKI/organizations
- 02_WIKI/events
- 02_WIKI/real-estate
- 02_WIKI/ai-lab
- 02_WIKI/technical-runbooks

Do not promote raw bookmarks directly into 02_WIKI.

## Content Lookup Rules

For every bookmark, Hermes should attempt to identify and read the highest-value content source.

### Browser bookmarks

For each browser bookmark:

1. Preserve the original bookmark title, URL, folder, and import date.
2. Fetch the URL if possible.
3. Extract readable content.
4. If extraction succeeds, create a processed article/resource note.
5. If extraction fails, record the failure reason and create a queue item only if the bookmark appears relevant.

### X bookmarks

For each X bookmark:

1. Preserve the original X URL or post ID.
2. Capture the post text if available.
3. If the X post links to an external article, GitHub repo, paper, video, or document, treat that linked URL as the primary source.
4. Preserve the X post as commentary/context.
5. Fetch the external linked source when possible.
6. If both X post and external URL are useful, cross-reference them.
7. If the X post is only a pointer to the external article, do not create two full processed notes.

### X post with external URL

If an X bookmark links to an external source:

- The external URL gets the canonical resource note.
- The X post becomes a source/commentary reference.
- Add the X URL to related_sources.
- Do not duplicate the article summary under both the X post and the external URL.

### Threads

If an X bookmark is a thread:

- Preserve the thread URL.
- Extract available post text.
- Summarize the thread as a source if the thread itself contains original insight.
- If the thread primarily summarizes an external article, prefer the external article as canonical.

## Extraction Status

Every processed source must include one extraction status:

- success
- partial
- blocked
- paywalled
- login_required
- non_article
- failed
- url_only

Never claim to have read a source when extraction status is url_only, failed, blocked, paywalled, or login_required.

## Canonical Source ID

Every bookmark/resource should get a canonical source key.

Prefer this order:

1. Final resolved URL after redirects
2. Canonical URL from page metadata
3. Original URL
4. X post ID or URL
5. Hash of title plus URL if no better key exists

Use canonical source IDs to deduplicate.

## Deduplication Policy

Before creating a processed note, search for existing notes with:

- same canonical URL
- same resolved URL
- same source URL
- same X post URL
- same title and domain
- same content hash
- same linked external URL from X

### Exact duplicate

If the same canonical source already exists:

- Do not create a second processed article note.
- Add the new bookmark/import as an additional source reference to the existing note if writing is safe.
- Otherwise, report the duplicate in the processing report.

### Near duplicate

If two sources discuss the same article or same idea but are not identical:

- Keep separate source notes.
- Add related_sources.
- Add a short explanation of the overlap.

### X plus article duplicate

If an X post links to an article already processed:

- Do not summarize the article again.
- Add the X post as commentary/context to the existing article note or create a lightweight X reference note.
- Cross-reference both sources.

### Same file referenced multiple ways

If multiple bookmarks point to the same PDF, GitHub repo, article, or docs page:

- Use one canonical resource note.
- Add all referring URLs under related_sources.
- Preserve all original bookmark records.

## Relevance Scoring

Score each processed source from 0 to 5.

### 5 — Critical

Directly affects an active project, current decision, important belief, or immediate Chief-of-Staff priority.

Examples:

- Hermes memory architecture
- Reachy local agent architecture
- AI-native property management
- AppFolio thought leadership
- active article/session ideas
- local model infrastructure
- Chief-of-Staff automation

Action:

- Create detailed processed note.
- Link to active project.
- Consider queue item.
- Recommend promotion to 02_WIKI if durable.

### 4 — High

Strongly relevant to a current focus area or recurring theme, but not immediately decision-critical.

Action:

- Create processed note.
- Link to related topics/projects.
- Consider future synthesis.

### 3 — Medium

Useful reference material likely to be searched later.

Action:

- Create lighter processed note.
- Keep in 03_RESOURCES.
- Do not promote unless connected later.

### 2 — Low

Interesting but weakly connected to current work.

Action:

- Preserve bookmark/import record.
- Summarize only if easy.
- Do not create queue item unless requested.

### 1 — Very Low

Minimal relevance, generic, outdated, or unclear value.

Action:

- Preserve raw record.
- No detailed processing.

### 0 — Noise

Spam, broken, irrelevant, duplicate with no additional value, or not worth keeping.

Action:

- Preserve raw import if already captured.
- Mark as noise in report.
- Do not process further.

## Relevance Criteria

Score relevance using these factors:

- Active project match
- Current focus area match
- Repeated theme across vault
- Decision impact
- Belief challenge
- Research usefulness
- Content creation usefulness
- Technical runbook usefulness
- Source credibility
- Novelty compared to existing notes
- Actionability

## Source Credibility

Assign one credibility value:

- primary
- expert
- industry
- social
- unknown
- low

Low credibility does not mean useless, but it should affect routing.

## Processing Depth

Use relevance score to choose depth.

### Score 5

Create a detailed note with:

- one-sentence preamble
- detailed summary
- key claims
- evidence/examples
- implications
- related projects
- related notes
- contradictions/tensions
- recommended next action

### Score 4

Create a solid note with:

- summary
- key claims
- relevance
- related projects/topics
- recommended next action

### Score 3

Create a light reference note with:

- summary
- source metadata
- why it may matter later

### Score 0-2

Preserve record and mention in report.

Do not spend significant agent time unless asked.

## Processed Note Required Frontmatter

Use this for processed resources:

    ---
    type: resource
    status: reference
    date:
    source_url:
    canonical_url:
    source_type:
    source_platform:
    extraction_status:
    relevance_score:
    credibility:
    project:
    topics: []
    related_sources: []
    duplicate_of:
    tags: []
    ---

## Processed Note Body Template

This section is part of this policy file. It tells Hermes how to format each processed article or resource note.

Use this structure for processed resource notes:

    # Source Title

    ## One-Sentence Preamble

    What this source is and why it might matter.

    ## Source Metadata

    - Source URL:
    - Canonical URL:
    - Source type:
    - Source platform:
    - Extraction status:
    - Relevance score:
    - Credibility:
    - Original bookmark folder:
    - Date accessed:

    ## Summary

    ## Key Claims

    ## Evidence / Examples

    ## Why This Matters

    ## Relevance to Active Projects

    ## Related Vault Notes

    ## Related Sources

    ## Contradictions or Tensions

    ## Recommended Next Action

    ## Raw Extract / Notes

    Optional. Include only if useful and not too long.

## Routing Rules

### Route to 03_RESOURCES/articles/processed

Use for processed article/resource notes.

### Route to 05_QUEUE/research

Use when:

- source is high relevance but extraction failed
- source raises a significant unanswered question
- source needs comparison against other sources
- source should be read manually

### Route to 05_QUEUE/summarize

Use when:

- source is readable but too long for current processing
- source is a video, transcript, or paper requiring a second pass

### Route to 05_QUEUE/decide

Use when:

- the source affects a pending decision
- the source challenges a current assumption
- the correct route is ambiguous

### Route to 05_QUEUE/draft

Use when:

- source supports a LinkedIn post
- source supports an article, session, talk, or internal memo

### Route to 02_WIKI

Only recommend promotion when:

- relevance score is 4 or 5
- idea is durable and reusable
- insight appears across multiple sources
- note is written in Mike's own synthesized understanding
- source is not merely a one-off article summary

### Route to 01_ACTIVE/projects

Only recommend or lightly update active projects unless explicitly authorized.

### Route to 06_GENERATED/bookmark-imports

Use for:

- import reports
- batch processing reports
- deduplication reports
- relevance scoring reports

## MOC Policy

A MOC is a Map of Content: an index note that links a cluster of related notes.

Do not create a MOC just because a topic exists.

Create or recommend a MOC only when one of these is true:

1. A topic has 20 or more related notes.
2. A topic spans at least 3 different top-level folders.
3. The topic is an active strategic focus area.
4. Navigation by search/filter is becoming slower than browsing an index.
5. The topic has multiple subthemes that need a hub.

Before creating a MOC, prefer Dataview/filtering when:

- topic has fewer than 20 notes
- notes already have good tags/frontmatter
- the topic is temporary
- the topic maps to one project only

Recommended MOC location:

- 02_WIKI/concepts
- 02_WIKI/frameworks
- 02_WIKI/ai-lab
- 02_WIKI/real-estate

MOC filename pattern:

YYYY-MM-DD-moc-topic-name.md

## Capture Optimization

Fast capture should be low friction.

Capture tools should write to:

- 00_CAPTURE/raw for text
- 00_CAPTURE/links for URLs
- 00_CAPTURE/voice for transcriptions
- 00_CAPTURE/screenshots for images or OCR outputs

Capture tools should not require the user to classify the note at capture time.

Hermes should classify later.

For bookmark imports:

- Raw browser exports belong in 03_RESOURCES/x-bookmarks/raw
- Parsed bookmark records belong in 03_RESOURCES/x-bookmarks/imported
- Extracted article text belongs in 03_RESOURCES/articles/raw
- Processed article notes belong in 03_RESOURCES/articles/processed

## Batch Processing Limits

To avoid flooding the vault:

- First run: process 5 bookmarks
- Second run: process 25 bookmarks
- Third run: process 100 bookmarks
- Large backlog: process in batches of 50-100

For each batch, produce a report with:

- total reviewed
- extraction successes
- failures
- duplicates
- high-relevance items
- queue items created
- MOC recommendations
- suggested next batch

Do not process all X bookmarks in one autonomous run unless explicitly approved.

## Output Report Format

Each bookmark processing batch should write a report to:

06_GENERATED/bookmark-imports/YYYY-MM-DD-bookmark-processing-report.md

Report structure:

    ---
    type: processing-report
    status: generated
    date: YYYY-MM-DD
    workflow: bookmark-ingestion
    tags: [chief-of-staff, bookmarks]
    ---

    # Bookmark Processing Report - YYYY-MM-DD

    ## Batch Summary

    - Sources reviewed:
    - Successfully extracted:
    - Failed / blocked / login required:
    - Duplicates found:
    - High relevance:
    - Queue items created:
    - Notes created:

    ## High-Relevance Sources

    ## Duplicate / Overlap Decisions

    ## X Bookmark Handling

    ## Routing Decisions

    ## MOC Recommendations

    ## Open Questions

    ## Recommended Next Action

## Human Approval Required

Require approval before:

- processing more than 100 bookmarks in one run
- promoting notes to 02_WIKI
- modifying active project notes
- deleting or archiving source material
- creating a new MOC
- changing this policy
POLICY
