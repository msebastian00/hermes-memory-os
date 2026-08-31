---
title: Book and Long-Form Knowledge Ingestion Policy
id: policy-book-longform-ingestion
type: policy
version: 1.0.0
status: active
owner: Mike
applies_to:
  - Hermes core agent
  - Hermes memory agent
  - Hermes chief-of-staff workflows
  - Vault ingestion automations
  - Books
  - Long-form articles
related_policies:
  - knowledge-and-memory-architecture.md
  - source-quality-policy.md
  - privacy-and-access-policy.md
  - ingestion-policy.md
  - entity-resolution-policy.md
  - claim-and-provenance-policy.md
  - HERMES_KNOWLEDGE_GRAPH_POLICY.md
  - HERMES_SOURCE_INTEGRITY_POLICY.md
last_updated: 2026-08-01
---

# Book and Long-Form Knowledge Ingestion Policy

## 1. Purpose

This policy defines how Hermes MUST process books and long-form articles into the Vault Knowledge Graph.

The objective is not to produce a large collection of summaries. The objective is to convert high-value source material into durable, connected, source-grounded knowledge that can improve:

1. Reachy and other robotics projects.
2. Mike's work as an Industry Principal.
3. Product, market, and strategic thinking.
4. Mike's personal operating system and daily decision-making.
5. Cross-domain discovery, including connections Mike may not have identified.
6. Future writing, speaking, planning, research, and agent reasoning.

The resulting system MUST allow Hermes to:

- Know that relevant knowledge exists.
- Know where that knowledge is stored.
- Retrieve the appropriate level of detail.
- Trace important statements back to the original source.
- Distinguish an author's claims from established facts, Mike's interpretations, and observed outcomes.
- Connect new knowledge to existing projects, goals, people, systems, concepts, and decisions.
- Avoid placing large bodies of reference knowledge into long-term agent memory.

## 2. Core Mental Model

The system uses four complementary knowledge layers.

### 2.1 Raw source layer

The original book, article, transcript, or licensed file is preserved in `03_RESOURCES`.

This layer answers:

- What did the source actually say?
- Where was the statement located?
- What version was processed?
- Can the source be reprocessed?

### 2.2 Canonical wiki layer

The wiki contains human-readable, synthesized, maintained knowledge.

This layer answers:

- What are the source's central ideas?
- What is the Vault's current understanding of a concept?
- How does an idea relate to Mike's work or life?
- What evidence, limitations, and disagreements exist?

### 2.3 Graph and retrieval layer

The Vault's Markdown links and typed metadata form the canonical Vault Knowledge Graph. Derived graph and vector indexes MAY be created from it. Derived Neo4j/Qdrant indexes MUST follow `HERMES_KNOWLEDGE_GRAPH_POLICY.md`; that policy does not replace this Vault graph.

This layer answers:

- How are entities, concepts, claims, projects, and sources connected?
- Which sources support or contradict a claim?
- What applies to a current project or goal?
- What source passages should be retrieved for a question?

### 2.4 Memory OS layer

Memory OS stores small, high-value operating memories and knowledge locators.

It MUST NOT become a second copy of the books or wiki.

A knowledge locator tells Hermes:

- A body of knowledge exists.
- When it may be relevant.
- Which canonical wiki pages, graph nodes, and source indexes to query.
- Which retrieval order to use.

## 3. Design Principles

### 3.1 Purpose before ingestion

Hermes MUST NOT deeply process a source merely because the file is available.

Before processing, Hermes MUST identify:

- Why the source may matter.
- Which current or likely future questions it may help answer.
- Which domains, projects, goals, or decisions it may inform.
- The appropriate processing depth.

### 3.2 Preserve raw sources; synthesize knowledge

The original source MUST remain available and unchanged.

Derived notes MUST summarize, interpret, classify, connect, and cite the source. They MUST NOT replace it.

### 3.3 Source pages are not the final knowledge architecture

Every processed book or major article receives a source synthesis page. However, the Vault MUST NOT become a set of isolated book summaries.

Important ideas MUST update or create canonical concept, framework, person, organization, system, project, decision, or practice pages.

### 3.4 Extract signal, not book length

Books often use stories, repetition, and examples to explain a smaller number of important ideas.

Hermes MUST prioritize:

- Core thesis.
- Definitions.
- Frameworks and models.
- Mechanisms and causal explanations.
- Actionable methods.
- Important claims.
- Evidence and limitations.
- Contradictions.
- Reusable examples.
- Applications to Mike's domains.

Hermes SHOULD omit repetitive explanation and low-value filler.

### 3.5 Preserve provenance

Every important derived idea, claim, framework, or relationship MUST be traceable to:

- Source ID.
- Chapter or section.
- Page, location, or paragraph when available.
- The processing model and policy version.
- Confidence and review status when extracted automatically.

### 3.6 Use "just enough semantics"

Hermes MUST use the approved entity and relationship vocabulary where possible.

Hermes MUST NOT create a new entity type, relationship type, or taxonomy category merely because a source uses different wording.

When the current schema cannot represent important knowledge, Hermes MUST propose a schema extension for review.

### 3.7 Separate claims, evidence, interpretations, and experience

Hermes MUST distinguish:

1. What the author asserts.
2. What evidence the source supplies.
3. What external sources support or contradict.
4. Mike's interpretation.
5. Mike's observed experience.
6. A proposed application or experiment.

An author's confident statement MUST NOT automatically be promoted to a verified fact.

### 3.8 Memory routes; the Vault stores

Long-term Memory OS MUST contain concise routing cues and operating context, not detailed book content.

### 3.9 Human review for consequential knowledge

Hermes MAY automatically create candidate notes and relationships.

Hermes MUST request review before promoting:

- Sensitive personal guidance.
- High-impact professional claims.
- Causal claims.
- Claims that conflict with existing canonical knowledge.
- Low-confidence entity resolutions.
- New policy or decision principles.
- Major changes to a canonical system architecture.

## 4. Scope

This policy applies to:

- Nonfiction books.
- Academic and technical books.
- Self-development and leadership books.
- Long-form essays and articles.
- Industry reports.
- White papers.
- Long transcripts that function as long-form sources.
- Course manuals and structured educational material.

This policy does not govern:

- Short bookmarks and social posts.
- Routine meeting notes.
- Email ingestion.
- Source code repositories.
- Daily captures.
- Personal journals.

Those sources MAY link to knowledge created under this policy but require their own ingestion rules.

## 5. Intended Outcomes

A successful ingestion MUST produce the following outcomes when appropriate.

### 5.1 Source preservation outcome

The original source is registered, hashed, classified, and stored in the correct resource location.

### 5.2 Source understanding outcome

A book or article source page explains:

- The source's purpose.
- Its central thesis.
- The most important ideas.
- Its frameworks and methods.
- The evidence it uses.
- Its limitations and disagreements.
- Where it applies to Mike's work and life.
- Which canonical wiki pages were created or updated.

### 5.3 Canonical knowledge outcome

Important ideas are integrated into existing canonical wiki pages or promoted into new pages only when justified.

### 5.4 Graph outcome

The source, author, concepts, claims, examples, applications, projects, and evidence are connected with typed relationships and provenance.

### 5.5 Retrieval outcome

Hermes can answer both broad and precise questions by retrieving:

1. Canonical wiki knowledge first.
2. Relevant graph paths when relationships matter.
3. Original source chunks when evidence or detail is required.
4. Vector search as discovery or fallback.

### 5.6 Memory outcome

Memory OS contains a concise locator only when repeated future retrieval is likely to be useful.

### 5.7 Learning outcome

Processing errors, failed extractions, duplicate entities, and corrections are recorded so the ingestion skill can improve.

## 6. Storage and Routing

Create these directories if they do not exist.

```text
03_RESOURCES/
├── books/
│   ├── raw/<source-id>/
│   │   ├── manifest.md       # identity, hash, NAS path to PDF, rights, status
│   │   ├── attachments/      # optional
│   │   └── *.md              # immutable OCR/full text (prefer chapter files)
│   └── processed/<source-id>/
│       └── *.md              # chapter notes / claims still tied to the book
└── articles/
    ├── raw/                  # short-form / bookmark pipeline (existing)
    ├── processed/            # existing bookmark/article processed notes
    └── longform/<source-id>/ # optional long-form article parallel to books
        ├── manifest.md
        ├── attachments/
        └── *.md

02_WIKI/
├── sources/
│   ├── books/
│   └── articles/
├── concepts/
├── frameworks/
├── people/
├── organizations/
├── systems/
├── practices/
├── technical-runbooks/
├── topic-maps/
├── events/
├── real-estate/
└── ai-lab/

05_QUEUE/
├── ingestion-review/       # long-form review items
├── entity-resolution/
├── conflicts/
├── memory-promotion/
├── summarize/              # existing CoS / bookmark queues
├── draft/
├── decide/
├── research/
└── develop/

06_GENERATED/
└── source-analysis/
    └── <source-id>/
        ├── section-notes/
        ├── candidate-insights.md
        └── ingestion-report.md

04_SYSTEM/
└── logs/
    └── ingestion/
```

### 6.1 Raw source

Store immutable book text under:

```text
03_RESOURCES/books/raw/<source-id>/
```

Binary originals (PDF/EPUB) SHOULD remain on NAS; record the absolute NAS path in `manifest.md`. If a text extract is copied into the vault, it lives under `raw/<source-id>/` and MUST NOT be modified after registration.

For long-form articles that use this policy (not short bookmarks):

```text
03_RESOURCES/articles/longform/<source-id>/
```

Short bookmarks and ordinary article URLs continue to follow `BOOKMARK_INGESTION_POLICY.md` (`articles/raw`, `articles/processed`).

### 6.2 Source manifest

Create:

```text
03_RESOURCES/books/raw/<source-id>/manifest.md
```

or for long-form articles:

```text
03_RESOURCES/articles/longform/<source-id>/manifest.md
```

`_meta.md` is an accepted alias for `manifest.md`. The manifest records technical, rights, security, NAS path, and processing metadata.

Book-tied working notes (not canonical wiki) go under:

```text
03_RESOURCES/books/processed/<source-id>/
```

### 6.3 Intermediate analyses

Chapter and section analyses are temporary derived artifacts and MUST be stored under:

```text
06_GENERATED/source-analysis/<source-id>/
```

They MUST NOT automatically become canonical wiki pages.

Scratch extracts outside the vault (optional):

```text
/workspace/output/books/<source-id>/
```

### 6.4 Final source synthesis

Create the final source page under:

```text
02_WIKI/sources/books/<source-slug>.md
```

or:

```text
02_WIKI/sources/articles/<source-slug>.md
```

### 6.5 Canonical concepts and frameworks

Promote durable knowledge into the appropriate existing wiki area.

Examples:

```text
02_WIKI/concepts/graph-rag.md
02_WIKI/frameworks/rapid-planning-method.md
02_WIKI/systems/reachy-routing-architecture.md
02_WIKI/practices/weekly-review.md
02_WIKI/organizations/example-org.md
02_WIKI/technical-runbooks/example-runbook.md
```

## 7. Source Identification

Use a stable source ID.

### 7.1 Book ID

```text
book-<author-slug>-<title-slug>-<publication-year>
```

### 7.2 Article ID

```text
article-<author-or-organization-slug>-<title-slug>-<publication-year>
```

When the year is unknown, use `undated`.

The source ID MUST remain unchanged if filenames or locations change.

## 8. Intake Gate

Before deep processing, Hermes MUST complete an intake assessment.

### 8.1 Required intake questions

1. What type of source is this?
2. Who created it?
3. When was it published or last revised?
4. Is it complete and readable?
5. What privacy classification applies?
6. Which domains may it inform?
7. Which active projects or goals may benefit?
8. What questions should the source help answer?
9. Does the Vault already contain the same source or a different edition?
10. Does a prior source synthesis already exist?
11. What processing mode is justified?

### Structural completeness gate

Before standard or deep processing, source-chunk indexing, canonical promotion, or graph promotion, Hermes MUST run the deterministic source-integrity preflight defined in `HERMES_SOURCE_INTEGRITY_POLICY.md`. A source that is `blocked` MUST remain preserved but MUST NOT generate new Qdrant chunks, Neo4j claims or relationships, source synthesis changes, or canonical wiki updates.


### 8.2 Processing modes

#### Catalog mode

Use when the source is low priority, weakly relevant, duplicative, or being preserved for possible future use.

Required output:

- Source registration.
- Hash and deduplication check.
- Manifest.
- Basic metadata.
- Optional source chunk index.
- No canonical wiki extraction.

#### Standard mode

Use for useful books and long articles that are relevant but do not justify exhaustive analysis.

Required output:

- Source registration and manifest.
- Source-level synthesis.
- Three to ten important ideas.
- Updates to existing canonical pages when clearly justified.
- Graph relationships.
- Wiki and source indexing.
- Memory locator only if repeated use is likely.

#### Deep mode

Use for foundational, high-authority, high-relevance, or repeatedly useful sources.

Required output:

- Structured chapter or section analysis.
- Book-level synthesis.
- Core claims and evidence.
- Framework extraction.
- Canonical wiki integration.
- Cross-domain application analysis.
- Contradiction and limitation review.
- Graph-ready entity and relationship extraction.
- Retrieval tests.
- Knowledge locator or domain locator update.

### 8.3 Processing-depth score

Score each category from 0 to 2:

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| Relevance to current goals | None | Possible | Direct |
| Expected reuse | Rare | Occasional | Frequent |
| Source authority | Weak | Moderate | Strong |
| Novelty to Vault | Duplicative | Adds nuance | Adds major knowledge |
| Cross-domain value | Narrow | One domain | Multiple domains |

Interpretation:

- `0-3`: Catalog mode.
- `4-6`: Standard mode.
- `7-10`: Deep mode.

Hermes MAY recommend a different mode when there is a documented reason.

## 9. Long-Source Processing Method

Books and very long articles MUST be processed in multiple passes.

### 9.1 Pass 1: Structural survey

Inspect:

- Title and publication metadata.
- Table of contents.
- Preface or introduction.
- Chapter and section headings.
- Conclusion.
- Notes, references, appendices, and index when useful.
- Repeated concepts and terms.

Produce:

- Source outline.
- Candidate domains.
- Candidate core questions.
- Proposed processing mode.
- Initial entity and concept vocabulary.
- Potential duplicates already in the Vault.

Hermes MUST NOT finalize the source thesis based only on the introduction or publisher description.

### 9.2 Pass 2: Section or chapter extraction

Process each meaningful section independently.

For each section, extract only candidate knowledge units that satisfy the signal rubric in section 10.

Each candidate MUST include:

- Candidate title.
- Knowledge type.
- Concise statement.
- Source locator.
- Importance score.
- Confidence.
- Related existing wiki pages.
- Potential application domains.
- Whether it is repeated elsewhere in the source.
- Whether it needs review.

### 9.3 Pass 3: Source-level synthesis

After all section analyses are complete:

- Deduplicate repeated ideas.
- Identify the actual core thesis.
- Separate major ideas from supporting material.
- Identify frameworks and procedures.
- Identify claims and their evidence.
- Identify limitations and unresolved questions.
- Compare the source with existing Vault knowledge.
- Identify contradictions.
- Select ideas for canonical promotion.
- Identify likely applications.
- Create or update the source synthesis page.

### 9.4 Pass 4: Canonical integration

For each promoted insight:

1. Search for an existing canonical page.
2. Resolve aliases and near-duplicates.
3. Update the existing page when one exists.
4. Create a new page only when promotion criteria are met.
5. Add source-grounded statements and provenance.
6. Add typed links to relevant entities.
7. Log the change.

### 9.5 Pass 5: Retrieval preparation

- Index raw source chunks in `hermes_sources`.
- Index canonical wiki pages in `hermes_wiki`.
- Update graph relationships.
- Create or update a Memory OS locator when justified.
- Run retrieval acceptance tests.

## 10. Signal Extraction Rubric

Hermes MUST distinguish durable knowledge from supporting narrative.

### 10.1 Knowledge types worth extracting

- `thesis`: The source's central argument.
- `concept`: A durable idea with a stable meaning.
- `framework`: An organized model of concepts or steps.
- `principle`: A general decision or operating rule.
- `method`: A repeatable procedure.
- `claim`: A proposition asserted by the author.
- `evidence`: Data, research, observation, or reasoning supporting a claim.
- `counterclaim`: A disagreement or alternative interpretation.
- `limitation`: A boundary, weakness, or condition.
- `example`: A case that materially improves understanding or later communication.
- `analogy`: A memorable explanatory comparison.
- `question`: An unresolved issue worth future investigation.
- `application`: A proposed use in Mike's work, projects, or life.
- `experiment`: A testable application with an expected outcome.
- `quote`: A short, unusually precise passage that is necessary and legally appropriate to retain.

### 10.2 Material normally excluded

Hermes SHOULD exclude:

- Repetition of an already captured point.
- Extended narrative that adds no new mechanism, evidence, or memorable example.
- Marketing copy.
- Anecdotes that do not support a durable idea.
- Lists that are merely exhaustive rather than useful.
- Unsupported speculation presented as filler.
- Large copied passages.

### 10.3 Story and example retention test

Retain a story or example only when at least one is true:

- It is evidence for or against an important claim.
- It reveals a mechanism or causal chain.
- It is a useful counterexample.
- It is unusually memorable and valuable for teaching, speaking, or writing.
- It directly maps to a current Mike project or decision.
- It contains a reusable pattern.
- Removing it would materially reduce understanding of the idea.

Retained stories MUST be labeled `example`, not `fact` or `concept`.

### 10.4 Insight importance score

Score each candidate insight from 0 to 2 on:

- Centrality to the source.
- Reusability across future questions.
- Relevance to Mike's goals or projects.
- Explanatory or decision value.
- Evidence or authority.

Promotion guidance:

- `8-10`: Promote to a canonical page or make a major update.
- `5-7`: Include on the source page; update an existing canonical page when appropriate.
- `0-4`: Keep only in intermediate analysis or omit.

A source's core thesis MAY be promoted regardless of score.

## 11. Source Manifest Template

```yaml
---
id: book-author-title-year
type: source-manifest
source_type: book
title:
subtitle:
authors: []
organization:
publication_year:
edition:
publisher:
url:
isbn:
original_path:
content_hash:
language: en
sensitivity: personal
domains: []
related_projects: []
related_goals: []
processing_mode: standard
processing_status: registered
ingestion_policy_version: 1.0.0
extraction_model:
extraction_prompt_version:
registered_at:
processed_at:
last_verified:
duplicate_of:
supersedes:
---
```

## 12. Book or Article Wiki Page Template

```markdown
---
id:
type: source-synthesis
source_type: book
title:
authors: []
publication_year:
source_id:
source_manifest:
processing_mode:
processing_status: complete
domains: []
key_concepts: []
key_frameworks: []
related_projects: []
related_goals: []
source_quality:
sensitivity:
created:
updated:
---

# Title

## Why this source matters

Explain why the source was processed and which questions it can help answer.

## Executive synthesis

A concise explanation of the source's actual central argument and contribution.

## Core thesis

State the primary thesis in one to three paragraphs.

## Key ideas

### Idea 1

- **Statement:**
- **Knowledge type:**
- **Why it matters:**
- **Source locator:**
- **Canonical page:**
- **Applications:**
- **Confidence:**

## Frameworks and methods

Describe reusable models, steps, practices, or procedures.

## Claims, evidence, and limitations

| Claim | Claim basis | Evidence supplied | Limitations | Source locator |
|---|---|---|---|---|

## Stories and examples worth retaining

Include only high-value examples and explain why each was retained.

## Relationship to existing Vault knowledge

- Reinforces:
- Extends:
- Contradicts:
- Supersedes:
- Requires clarification:

## Applications to Mike's domains

### Reachy

### Other robotics projects

### Industry Principal work

### Personal operating system

### Cross-domain opportunities

## Candidate experiments or actions

List testable applications, not vague recommendations.

## Open questions

## Derived and updated pages

- Created:
- Updated:
- Proposed for review:

## Retrieval cues

List representative questions this source and its derived pages should answer.

## Source and provenance

Link to the manifest and original source location.
```

## 13. Canonical Page Promotion Rules

Create a new canonical wiki page only when one or more is true:

- The idea is central to a high-value source.
- The idea appears in multiple sources.
- The idea is directly relevant to an active project, goal, role, or recurring decision.
- The idea is expected to be retrieved repeatedly.
- The idea has meaningful relationships to several existing entities.
- The idea is needed to resolve ambiguity or contradiction in the Vault.

Do not create a new page when:

- An existing page can be updated.
- The idea is only a minor restatement.
- The idea is source-specific vocabulary for an existing concept.
- The idea is a low-value story or detail.
- The page would contain only one weak statement.

Every canonical page SHOULD synthesize across sources rather than mirror one source.

## 14. Claim and Evidence Handling

Create a claim object or clearly labeled claim section when a statement is:

- Debatable.
- Causal.
- Predictive.
- Normative.
- Temporal.
- Evidence-bearing.
- Important enough to affect decisions.
- Likely to conflict with another source.

Each claim MUST record:

```yaml
claim_id:
statement:
asserted_by:
source_id:
source_locator:
claim_basis:
confidence:
verification_status:
valid_from:
valid_to:
supports: []
contradicts: []
applies_to: []
reviewed_by:
```

Allowed `claim_basis` values include:

```text
author-framework
author-opinion
anecdotal
case-study
research-cited
primary-data
secondary-synthesis
personal-observation
inference
unverified
```

Hermes MUST NOT silently convert `author-framework`, `author-opinion`, or `anecdotal` into established fact.

## 15. Entity Resolution

Before creating an entity page or graph node, Hermes MUST:

1. Search the Vault by exact name.
2. Search known aliases and abbreviations.
3. Compare contextual relationships.
4. Prefer stable canonical IDs.
5. Record the source's original wording as an alias.
6. Queue uncertain matches for review.

Examples:

```text
Qwen 3.6
Qwen3.6
Qwen/Qwen3.6-35B-A3B-FP8
```

These may refer to related but not always identical entities. Hermes MUST preserve model-level specificity.

A low-confidence match MUST remain a candidate mention and MUST NOT be merged automatically.

## 16. Graph Representation

The Vault's Markdown pages and typed links are the canonical graph representation.

Derived Neo4j or other graph indexes MUST be rebuildable from the Vault.

### 16.1 Preferred source relationships

```text
AUTHORED_BY
PUBLISHED_BY
HAS_PART
ABOUT
INTRODUCES
ASSERTS
SUPPORTS
CONTRADICTS
EXEMPLIFIES
APPLIES_TO
DERIVED_FROM
MENTIONS
SUMMARIZED_BY
LOCATED_AT
```

### 16.2 Preferred knowledge relationships

```text
RELATED_TO
PART_OF
DEPENDS_ON
ENABLES
REQUIRES
IMPLEMENTS
INFLUENCES
SUPPORTS
CONTRADICTS
APPLIES_TO
TESTED_BY
RESULTED_IN
SUPERSEDES
```

### 16.3 Relationship provenance

Important relationships MUST include or resolve to:

- Source ID.
- Source locator.
- Extraction confidence.
- Verification status.
- Created date.
- Validity dates when temporal.
- Sensitivity classification.

## 17. Chunking and Source Indexing

A book MUST NOT be represented only as one giant text or one embedding.

### 17.1 Chunk boundaries

Prefer natural boundaries:

1. Chapter.
2. Section.
3. Subsection.
4. Paragraph group.

Do not split a definition, procedure, table explanation, or argument across chunks when avoidable.

### 17.2 Chunk size

Use semantically coherent chunks suitable for the configured embedding model. As an initial operating range, prefer approximately 600 to 1,200 tokens with limited overlap.

For the current local `nomic-embed-text` configuration, vector input has a hard maximum of 4,000 Unicode characters. When a logical chunk exceeds that limit, generate stable child spans (for example, `parent__pNN`) at natural boundaries. Each child vector text MUST exactly equal its declared immutable raw-source span; truncation is forbidden. This hard limit overrides the initial range when they conflict.

The ingestion implementation MAY tune this range based on retrieval evaluation, but any model or input-limit change MUST be dry-validated and applied through a complete replacement crosswalk before the prior active crosswalk is superseded.

### 17.3 Required chunk metadata

```yaml
source_id:
source_type:
title:
author:
publication_year:
chapter:
section:
page_start:
page_end:
chunk_index:
chunk_hash:
domains:
sensitivity:
processing_version:
```

### 17.4 Memory OS collections

Use the existing collections as follows:

- `hermes_sources`: Original source chunks and source-level metadata.
- `hermes_wiki`: Canonical source syntheses, concepts, frameworks, and topic maps.
- `hermes_memories`: Small operating memories and knowledge locators only.
- `hermes_agent_learning`: Extraction failures, corrections, prompt improvements, and workflow lessons.
- `hermes_captures`: Unprocessed or recently captured source candidates.

### 17.5 Visual and mathematical evidence

When a source contains meaningful figures, tables, charts, images, or equations, preserve the original source page and process the visual material as derived evidence rather than replacing OCR/full text.

Each derived visual record MUST retain the source ID, page locator, immutable rendered-attachment SHA-256, extractor/model identity, factual description, confidence, and the reviewed retrieval chunk covering that page. Equations SHOULD retain normalized LaTeX only when directly visible and sufficiently confident.

Only records with verified hashes, valid chunk mappings, source-integrity clearance, and confidence of at least 0.75 MAY become derived graph evidence. Blank pages, unsupported output, failed OCR/vision extraction, uncertain equations, and unmapped pages MUST be reported and retried or deferred; they MUST NOT create canonical claims.

Visual evidence links to the existing source chunk so Qdrant-first retrieval can expand through the graph. Do not embed image bytes, replace raw OCR/full text, or silently modify canonical Vault pages.

## 18. Retrieval Policy

When answering a question informed by processed long-form material, Hermes SHOULD use this order.

### 18.1 Canonical knowledge first

Retrieve relevant canonical wiki pages and graph entities.

Use this for:

- Established summaries.
- Definitions.
- Framework comparisons.
- Cross-source synthesis.
- Application to projects and goals.

### 18.2 Graph retrieval second

Use graph traversal when the question asks about:

- Relationships.
- Dependencies.
- Evidence chains.
- Contradictions.
- Shared concepts.
- Multi-source aggregation.
- Cross-domain connections.

### 18.3 Original source retrieval for grounding

Retrieve source chunks when:

- The user asks what a specific source says.
- A precise explanation is needed.
- A claim requires verification.
- The canonical page lacks sufficient detail.
- Conflicting sources must be compared.
- A citation or source location is required.

### 18.4 Vector search as discovery or fallback

Use vector retrieval to:

- Find semantically related source passages.
- Discover relevant material when entities are not known.
- Search unstructured sources.
- Recover from incomplete graph or wiki retrieval.

Vector search MUST NOT be assumed complete for broad aggregate or multi-hop questions.

### 18.5 Combined retrieval

For complex questions, Hermes SHOULD:

1. Resolve the question's entities and intent.
2. Retrieve the relevant graph neighborhood.
3. Identify attached canonical pages and sources.
4. Retrieve the most relevant source chunks.
5. Build a compact evidence packet.
6. Synthesize the answer from that packet.
7. Preserve citations and uncertainty.

## 19. Memory OS Knowledge Locator Policy

### 19.1 What a knowledge locator is

A knowledge locator is a compact memory record that helps Hermes route future questions to durable Vault knowledge.

It is not a source summary.

### 19.2 When to create or update a locator

Create or update a locator only when:

- The knowledge is likely to be reused.
- The topic is important to an active or enduring domain.
- Forgetting the knowledge's existence would cause repeated missed retrieval.
- The correct retrieval path is not obvious from current operating context.
- The source materially expands an existing topic map.

Prefer updating a domain-level locator over creating one locator per book.

Examples of good locator subjects:

- Reachy voice and routing architecture.
- GraphRAG and knowledge architecture.
- Investor-owner market strategy.
- Mike's personal operating system.
- Tony Robbins frameworks and applications.

### 19.3 Locator format

```yaml
memory_type: knowledge_locator
subject:
summary:
retrieval_triggers: []
preferred_retrieval_order:
  - hermes_wiki
  - knowledge_graph
  - hermes_sources
vault_paths: []
topic_map:
graph_entity_ids: []
source_ids: []
qdrant_filters:
  domains: []
  source_ids: []
priority:
sensitivity:
created_at:
updated_at:
review_after:
```

### 19.4 Locator content limits

A locator SHOULD contain:

- One or two sentences explaining what knowledge exists.
- Common retrieval triggers.
- Canonical locations.
- Relevant source or graph IDs.
- Retrieval priority.

A locator MUST NOT contain:

- Full chapter summaries.
- Long lists of key ideas.
- Copied source passages.
- Detailed claims that belong in the wiki.
- The entire book's contents.

### 19.5 Example locator

```yaml
memory_type: knowledge_locator
subject: knowledge-graphs-and-graphrag
summary: >
  The Vault contains a source synthesis and canonical pages covering
  purpose-driven graph design, entity resolution, GraphRAG, graph retrieval,
  and graph machine learning.
retrieval_triggers:
  - knowledge graph design
  - graph rag
  - entity resolution
  - book ingestion
  - vector rag limitations
preferred_retrieval_order:
  - hermes_wiki
  - knowledge_graph
  - hermes_sources
vault_paths:
  - 02_WIKI/sources/books/knowledge-graphs-and-llms-in-action.md
  - 02_WIKI/concepts/graph-rag.md
  - 02_WIKI/concepts/entity-resolution.md
topic_map: 02_WIKI/topic-maps/knowledge-and-memory-architecture.md
source_ids:
  - book-negro-futia-kus-montagna-knowledge-graphs-and-llms-in-action-2026
priority: high
sensitivity: personal
```

## 20. Source Quality and Rights

Hermes MUST apply `source-quality-policy.md`.

At minimum, record:

- Primary or secondary source.
- Author expertise.
- Publisher or organization.
- Publication date.
- Evidence type.
- Known bias or commercial interest.
- Whether the source cites primary evidence.
- Whether the source is outdated for the intended use.
- Whether the source is descriptive, prescriptive, academic, or promotional.

For licensed books and paid content:

- Preserve the original privately.
- Do not reproduce large passages into the wiki.
- Prefer paraphrase and short necessary quotations.
- Mark sharing restrictions.
- Do not place restricted full text in public or work-shared locations.

## 21. Privacy and Access

Every source and derived artifact MUST inherit a sensitivity classification.

A derived page MUST use the most restrictive classification of the material it contains.

Hermes MUST NOT send restricted, personal, family-private, health-sensitive, work-confidential, or credential-bearing content to an external model unless explicitly allowed by `privacy-and-access-policy.md`.

Generated summaries, embeddings, graph edges, and memory locators are also data and MUST follow the same access rules.

## 22. Quality Assurance

### 22.1 Required checks

Before marking a source complete, verify:

- The source ID is unique.
- The original file hash is recorded.
- The source is not a duplicate.
- The table of contents and major sections were covered.
- The executive synthesis reflects the full source, not only the introduction.
- Core ideas are deduplicated.
- Important claims have source locators.
- Claims are distinguished from facts and interpretations.
- Existing canonical pages were searched before new pages were created.
- Entity resolution was performed.
- Graph relationships use approved types.
- sensitivity metadata are present.
- Wiki and source indexes were updated.
- Memory OS received only a locator when justified.
- An ingestion report was written.

### 22.2 Retrieval acceptance tests

Test at least five questions appropriate to the source:

1. What is the source's central thesis?
2. What are its most important frameworks or methods?
3. What does it say about a specific important concept?
4. How does it apply to one of Mike's current domains or projects?
5. Where in the source is a selected claim supported?

For deep-mode sources, also test:

6. What claims are weak, anecdotal, or disputed?
7. Which existing Vault concepts does the source reinforce or contradict?
8. Can Hermes retrieve the original supporting section?
9. Can Hermes connect the source to more than one domain without inventing relationships?
10. Can Hermes explain what it does not know?

### 22.3 Confidence thresholds

- High-confidence, schema-compliant, non-consequential updates MAY be promoted automatically.
- Medium-confidence items SHOULD be included as proposed or unverified.
- Low-confidence items MUST go to `05_QUEUE`.
- Conflicting canonical knowledge MUST go to `05_QUEUE/conflicts`.

## 23. Failure Handling

Hermes MUST stop or downgrade processing when:

- The source is unreadable or incomplete.
- OCR or text extraction quality is poor.
- The source appears duplicated but the edition cannot be resolved.
- The source's rights or sensitivity are unclear.
- Entity resolution is too uncertain.
- The extraction output is unstable.
- The schema cannot represent essential information.
- The source is too low-value for the requested processing mode.

When processing fails:

1. Preserve the source and manifest.
2. Record the failure.
3. Set `processing_status: blocked`.
4. Write the reason and recommended resolution.
5. Do not create confident canonical knowledge from incomplete processing.

## 24. Idempotency and Reprocessing

The ingestion process MUST be safe to run more than once.

Hermes MUST use:

- Stable source IDs.
- Content hashes.
- Stable canonical page IDs.
- Extraction prompt versions.
- Policy versions.
- Upsert behavior rather than blind creation.
- Change logs.

When a new edition or corrected source is processed:

- Link it with `SUPERSEDES` or `EDITION_OF`.
- Preserve prior source records.
- Re-evaluate affected canonical claims.
- Update validity and provenance rather than silently overwriting history.

## 25. Ingestion Report

Create:

```text
06_GENERATED/source-analysis/<source-id>/ingestion-report.md
```

The report MUST include:

```markdown
# Ingestion Report

## Source
## Processing mode
## Status
## Files created
## Canonical pages created
## Canonical pages updated
## Graph relationships added
## Claims requiring review
## Entity-resolution issues
## Conflicts discovered
## Memory locator action
## Qdrant indexing action
## Retrieval tests and results
## Errors or limitations
## Recommended follow-up
```

Also append a one-line result to:

```text
04_SYSTEM/logs/ingestion/YYYY-MM-DD.md
```

## 26. Definition of Done

A standard- or deep-mode source is complete only when:

- The source is preserved and registered.
- The source synthesis exists.
- Important ideas are separated from supporting filler.
- Relevant canonical pages are updated.
- Important claims are source-grounded.
- Entities and relationships are normalized.
- The graph points back to source evidence.
- Retrieval indexes are updated.
- Memory OS has the correct locator behavior.
- Quality and retrieval tests pass.
- Open conflicts and uncertainties are queued.
- The ingestion report is complete.

## 27. Hermes Execution Checklist

When instructed to process a book or long-form article, Hermes MUST execute:

```text
1. Register source
2. Hash and deduplicate
3. Classify rights and sensitivity
4. Identify purpose and competency questions
5. Score processing depth
6. Survey source structure
7. Process chapters or sections
8. Extract candidate knowledge units
9. Score and deduplicate insights
10. Create source-level synthesis
11. Search and update canonical wiki pages
12. Resolve entities and aliases
13. Add typed graph relationships with provenance
14. Index source chunks in hermes_sources
15. Index wiki pages in hermes_wiki
16. Create or update a knowledge locator only if justified
17. Run QA and retrieval tests
18. Queue uncertainty and conflicts
19. Write ingestion report and log
20. Mark complete
```

## 28. Guiding Rule

When choosing between storing more text and building a better retrieval path, build the better retrieval path.

The source preserves detail.

The wiki preserves synthesized understanding.

The graph preserves relationships and provenance.

The vector index preserves semantic discoverability.

Memory OS preserves operating context and tells Hermes where durable knowledge can be retrieved.
