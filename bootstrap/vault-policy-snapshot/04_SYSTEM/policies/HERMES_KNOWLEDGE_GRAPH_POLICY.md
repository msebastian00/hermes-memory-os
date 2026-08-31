---
title: Hermes Knowledge Graph Policy
id: policy-hermes-knowledge-graph
type: policy
version: 1.0.0
status: active
owner: Mike
applies_to:
  - Hermes core agent
  - Hermes memory agent
  - Hermes chief-of-staff workflows
  - Optional Neo4j graph layer
  - Graph maintenance jobs
related_policies:
  - POLICY_ROUTER.md
  - book-and-longform-knowledge-ingestion-policy.md
  - claim-and-provenance-policy.md
  - knowledge-and-memory-architecture.md
  - HERMES_SOURCE_INTEGRITY_POLICY.md
last_updated: 2026-08-29
---

# Hermes Knowledge Graph Policy

This policy constrains the optional Neo4j relationship layer. It does not replace the Obsidian vault, Memory OS, Qdrant, book-ingestion scripts, or other policies. Honcho remains disabled.

The vault remains the human-facing source of truth. Qdrant remains the vector layer. Memory OS remains the durable memory owner. Neo4j is evidence-backed relationship storage only.

## Required provenance

Every graph claim and every graph relationship MUST include:

1. Evidence (quote or reviewed metadata span).
2. Provenance (source ID, document/chunk locator, extractor name).
3. Confidence (numeric; default exclusion below 0.75 unless a review task asks otherwise).
4. Source attribution (author, source page, or policy file). Generated source claims stay attributed to their author/source (`claim_basis: author-framework`) and MUST NOT be presented as verified universal facts.

Unsupported or low-confidence graph facts MUST NOT be treated as canon. Missing evidence means the edge is not writable as a fact.

## Book promotion to the graph

Graph promotion of a book REQUIRES reviewed retrieval chunks (`06_GENERATED/source-analysis/<source_id>/retrieval-chunks.md`) plus the canonical source synthesis page.

Do not promote a raw-book manifest that lacks reviewed retrieval-chunk metadata.

The source-integrity preflight in `HERMES_SOURCE_INTEGRITY_POLICY.md` MUST report `ready_for_span_review` before a graph upsert or Qdrant crosswalk. A dry-run MAY diagnose a blocked source, but it MUST NOT be used as authority to write it.

Placing a source in `05_QUEUE/book-ingestion/incoming`, `processing`, or `completed` is the authorization for autonomous graph processing. Queue authorization does not bypass provenance, source-integrity, reviewed-chunk, exact-span, Qdrant, or dry-run gates.

## Span manifests

A span manifest is required only when logical retrieval chunks lack an existing verified source-span/Qdrant crosswalk.

When required, the manifest MUST map:

- stable chunk IDs
- exact spans (section/page, and character offsets when verified)
- the raw-source SHA-256

Proposed manifests are review artifacts. They MUST NOT index Qdrant or upsert Neo4j.

### Embedding span budget

For the current local `nomic-embed-text` configuration, every vector input MUST be at most 4,000 Unicode characters. Oversized logical chunks MUST be split into stable exact-span children; vector text MUST equal the declared immutable raw-source span and MUST NOT be independently truncated. A future model or input-limit change requires dry validation and a complete replacement crosswalk before an active crosswalk may be superseded.

## Visual and mathematical evidence

PDF figures, tables, charts, images, and equations MAY produce derived graph evidence through the configured local visual extractor. They do not replace immutable PDF/EPUB/Markdown source files, OCR text, Vault notes, Qdrant, or Memory OS.

A graphable visual record MUST include the source ID, immutable attachment SHA-256, source page locator, extractor model/version, factual description, numeric confidence, and a mapping to an existing reviewed source chunk. For equations, retain visible notation and normalized LaTeX when confidence permits. The visual model MUST NOT infer absent facts.

Visual-derived claims and relationships MAY be upserted autonomously only when source-integrity passes, the page maps to a reviewed chunk, the attachment hash verifies, and confidence is at least 0.75. Blank pages, missing mappings, unsupported output, invalid hashes, and lower-confidence records MUST remain report warnings rather than graph facts.

Visual evidence attaches to the existing source chunk. Qdrant remains the retrieval entry point; Neo4j expands the matching chunk to its evidence-backed visual claims. Do not embed image bytes or silently rewrite canonical source text.

## Write order

Dry-run validation MUST precede Qdrant writes and Neo4j writes.

Default write mode is `dry_run`. A queue-authorized promotion MAY create Qdrant points and Neo4j records only after all machine gates pass. It MUST record the dry-run result, exact-span evidence, source integrity, provenance, and confidence in its report. No approval edit is required.

## Policies constrain graph jobs

This file and the other vault policies constrain graph extraction, naming, and retrieval.

Graph jobs MUST NEVER rewrite policy files or silently resolve policy conflicts. Conflicts become review items only. Policy-defined ontology names override extracted names.

## Concept-overlap review gate

Before a graph upsert that introduces reusable concepts, run the read-only overlap review described in `entity-resolution-policy.md`. It MUST query the existing Memory OS/Qdrant retrieval boundary first when available, then compare Neo4j canonical names and aliases. The report MUST remain under `hermes-memory-os/graph/reports`, retain the candidate digest and evidence provenance, and record any unavailable dependency. It is an evidence report, not a human gate. Exact normalized identities may be reused deterministically; lexical or semantic near-matches must remain separate and be reported as possible associations.

The review MAY identify exact names, aliases, lexical near-matches, and semantically related source material. It MUST NOT automatically merge entities, create aliases, rewrite canonical vault content, write Qdrant, or alter Memory OS. Qdrant similarity alone is not identity proof.

## Maintenance reports

Graph maintenance is read-only against Neo4j and source systems.

Reports MAY list duplicate entities, claims without evidence, low-confidence edges, policy conflicts, and missing Qdrant crosswalks.

Maintenance reports are review artifacts, never autonomous corrections. They MUST NOT merge entities, rewrite notes, rewrite policies, write Qdrant, upsert Neo4j, or modify Memory OS/vault content.

Report output MUST stay under the Memory OS graph reports directory (`hermes-memory-os/graph/reports`), not under vault canon.

## Logging and failure

Log tool/job action, source IDs, write mode, warnings, and result counts. Never log Neo4j passwords or other secrets.

If Neo4j, Qdrant, or an exact-span prerequisite is unavailable, defer the affected promotion, write a health-failure report under the reports directory, and retry on the next graph promotion sweep. Do not mutate unrelated systems.
