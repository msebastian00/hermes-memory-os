---
title: Entity Resolution Policy
id: policy-entity-resolution
type: policy
version: 1.0.0
status: active
owner: Mike
applies_to:
  - Hermes core agent
  - Hermes memory agent
  - Book and long-form ingestion
  - Optional Neo4j graph layer
related_policies:
  - POLICY_ROUTER.md
  - book-and-longform-knowledge-ingestion-policy.md
  - HERMES_KNOWLEDGE_GRAPH_POLICY.md
last_updated: 2026-08-30
---

# Entity Resolution Policy

This policy governs names, aliases, near-duplicates, author-specific terminology, and entity merge decisions. It preserves the vault as the human-facing canonical layer, Qdrant as the vector layer, Memory OS as durable-memory owner, and Neo4j as a rebuildable evidence-backed relationship index.

## Required overlap review

Before creating or upserting a concept, framework, person, organization, product, model, or other reusable entity:

1. Search exact canonical names and known aliases in the Vault and Neo4j.
2. Query Qdrant through the existing Memory OS boundary for semantically related canonical pages and source chunks.
3. Compare entity type, source context, claims, relationships, edition/version, and supporting evidence.
4. Produce a review artifact under `agent-dev/hermes-memory-os/graph/reports` when graph promotion is proposed.
5. Preserve the source's original wording, source ID, locator, evidence, and confidence in the candidate or alias record.

The Qdrant result is a candidate-discovery signal, not proof of identity. A semantic match alone MUST NOT create an alias, merge entities, or change a canonical page.

## Resolution labels

Every non-exact candidate match MUST be classified by Hermes from available evidence as exactly one of:

- `same_concept`: the same entity under a different valid name or spelling.
- `broader_or_narrower`: related at different abstraction levels; retain both with a typed relationship when evidence supports it.
- `related_but_distinct`: related but not interchangeable; retain separate entities.
- `uncertain`: insufficient evidence; keep as a candidate mention and revisit later.

For an exact normalized identity, Hermes may reuse the stable entity ID and retain author-specific wording as source evidence. A non-exact `same_concept` classification remains a reported candidate unless direct evidence establishes identity. Do not replace a source author's terminology or present a source-framework claim as universal fact.

## Automation boundaries

Hermes MAY deterministically reuse an existing stable entity ID for an exact normalized name. Hermes MUST NOT automatically merge near-duplicates, introduce aliases from semantic similarity alone, or rewrite canonical notes or policies. The overlap analyzer is read-only and its report must identify the candidate set by digest and remain under the graph reports directory. The graph promotion may continue after all source-integrity, exact-span, evidence, and confidence gates pass; non-exact matches remain distinct and are reported rather than merged.

## Tony Robbins and other overlapping author corpora

When an author uses familiar concepts under a branded or source-specific phrase, retain that phrase as a sourced candidate or, after review, an alias of the canonical concept. Do not create a new canonical concept solely because the author uses different wording. Keep distinct constructs separate when their mechanisms, scope, sequence, or evidentiary basis differ.

Examples of review outcomes:

- A spelling or naming variant with the same definition: `same_concept` after evidence review.
- An author's branded process that contains a known general principle: `broader_or_narrower` or `related_but_distinct`.
- A phrase that appears similar but has insufficient contextual support: `uncertain`.

## Evidence and auditability

Each automated identity reuse or relationship decision MUST record source ID, source locator, evidence quote or reviewed metadata span, extractor, timestamp, confidence, and rationale. Low-confidence matches remain review items. Merge reversal must preserve both historical IDs and prior evidence; it must never delete source provenance.

## Failure behavior

If Qdrant or Neo4j is unavailable, produce an incomplete report and defer graph promotion for retry. Do not fabricate a match, downgrade source-integrity checks, or block raw-source preservation and ordinary non-graph ingestion.
