---
title: Hermes Source Integrity Policy
id: policy-hermes-source-integrity
type: policy
version: 1.1.0
status: active
owner: Mike
applies_to:
  - Book and long-form ingestion
  - Hermes memory agent
  - Qdrant source indexing
  - Optional Neo4j graph layer
  - Book-ingestion cron jobs
related_policies:
  - book-and-longform-knowledge-ingestion-policy.md
  - HERMES_KNOWLEDGE_GRAPH_POLICY.md
  - claim-and-provenance-policy.md
last_updated: 2026-08-30
---

# Hermes Source Integrity Policy

## Purpose

This policy prevents incomplete, truncated, reordered, or unreadable source extracts from being represented as reliable knowledge. It applies before standard or deep processing, source-chunk indexing, canonical promotion, Qdrant crosswalk creation, and Neo4j graph writes.

This policy accepts Markdown, PDF, EPUB, and other licensed book formats as originals. Neo4j and Qdrant evidence work from a registered immutable UTF-8 text derivative (`.md` or `.txt`) with stable section, page, or character locators. It adds a deterministic preflight to prove that that derivative can support the locations claimed by its reviewed retrieval chunks.

## Required preflight

For each source proposed for standard or deep processing, Hermes MUST:

1. Preserve the registered original unchanged and verify its SHA-256 against `manifest.md`. For a PDF or EPUB, also register the derived UTF-8 text file, its hash, and the extraction method; a Markdown original may itself be the text source.
2. Capture expected structure from the licensed original, table of contents, reviewed retrieval metadata, or another recorded authoritative structure.
3. Verify that the raw extract is readable and that its recoverable headings, sections, or page markers cover the expected structure in order.
4. Write a source-integrity report under `06_GENERATED/source-analysis/<source-id>/` before generating or updating source chunks.
5. Record one of `ready_for_span_review`, `needs_human_review`, or `blocked`, plus each validation problem and the raw-source hash.

A validated character-span manifest additionally requires exact raw text at every declared offset. Section or page labels alone are insufficient for a Qdrant crosswalk.

### Embedding span capacity

For the current local `nomic-embed-text` configuration, each vector input MUST be at most 4,000 Unicode characters. Oversized logical chunks MUST become stable, exact-span child chunks; the embedded text MUST exactly equal each child's declared immutable source span. Never truncate an embedding input independently of its declared evidence span. The governing chunking and replacement-crosswalk procedure is `book-and-longform-knowledge-ingestion-policy.md`.

## Stop Conditions

Hermes MUST set `blocked` when any of the following is true:

- The raw-source hash differs from the registered manifest.
- Required sections, chapters, or pages are absent, truncated, or materially out of order.
- The source is unreadable or extraction quality prevents reliable locators.
- Reviewed retrieval chunks claim ranges that the raw extract cannot substantiate.
- Exact spans are required but cannot be verified.

A blocked source MAY be inventoried and diagnosed. It MUST NOT receive new Qdrant points, a Neo4j graph upsert, new source claims, or canonical wiki promotion. Existing derived artifacts are historical review material, not proof that the source passed this gate.

`needs_human_review` is a diagnostic status for a source that cannot yet be machine-verified. It is a deferred state, not a request for manual workflow approval and never authorizes Qdrant or Neo4j writes. A queued source proceeds autonomously once a complete machine-verifiable immutable derivative is registered and this preflight returns `ready_for_span_review`.

## Repair Procedure

Never overwrite or silently edit the registered raw extract. Preserve the original extraction and its manifest history.

When a complete licensed original or corrected extraction becomes available:

1. Register the corrected extract as a new immutable derivative and record its hash, acquisition path, extraction method, and relation to the prior extract.
2. Re-run this preflight and review its report.
3. Regenerate retrieval chunks and source synthesis only after the report is `ready_for_span_review`.
4. Create exact chunk spans, then perform the existing Qdrant dry-run, Qdrant upsert, Neo4j dry-run, and Neo4j upsert sequence.
5. Retain prior graph or retrieval artifacts for audit. A prior active crosswalk MAY be superseded automatically only after a complete replacement has passed all integrity, exact-span, Qdrant, and Neo4j write gates; it must not be deleted as part of supersession.

## Job Requirements

Book-ingestion jobs MUST invoke the preflight before any standard or deep processing step. A maintenance cron may report blocked or stale sources but MUST NOT repair, re-extract, rewrite vault content, create embeddings, or write graph records.

Failures are review items. Jobs MUST record source ID, raw hash, validation status, and failures without logging credentials or licensed source content.
