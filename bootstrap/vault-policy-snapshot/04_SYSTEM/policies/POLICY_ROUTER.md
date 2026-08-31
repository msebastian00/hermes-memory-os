---
type: system
status: active
date: 2026-08-02
tags: [vault, policies, router, progressive-loading]
---

# Policy Router

Progressive policy loading for book and long-form ingestion (and compatible vault workflows).

Do not preload full policy files on every run. Use skill runtime rules first. Load only the matching policy section when a trigger fires. Read the full policy only for audits, policy conflicts, privacy incidents, architectural changes, or merge reversals.

| Trigger | Policy section |
|---|---|
| Register or deduplicate source | ingestion-policy: Intake Gate, Deduplication |
| Source completeness, extraction quality, span verification, or source repair | HERMES_SOURCE_INTEGRITY_POLICY.md |
| Figures, tables, charts, images, equations, OCR, or visual extraction | book-and-longform-knowledge-ingestion-policy.md: Visual and mathematical evidence; HERMES_KNOWLEDGE_GRAPH_POLICY.md: Visual and mathematical evidence |
| Choose catalog, standard, or deep | source-quality-policy: Processing Depth |
| Purchased or licensed source | privacy-and-access-policy: restricted-licensed |
| Sensitive or external-model processing | privacy-and-access-policy: Agent Access, Model Processing Zones |
| Important author assertion | claim-and-provenance-policy: First-Class Claims |
| Conflicting sources | claim-and-provenance-policy: Conflict Handling |
| Ambiguous entity, alias, author-specific terminology, or concept overlap | entity-resolution-policy.md: Autonomous overlap analysis |
| Model, version, edition, or deployment ambiguity | entity-resolution-policy.md: Autonomous overlap analysis |
| Memory locator decision | knowledge-and-memory-architecture: Memory Promotion Rules |
| Vault versus graph versus Qdrant versus Memory role | knowledge-and-memory-architecture: System Roles |
| Graph claim, relationship, book promotion, or span manifest | HERMES_KNOWLEDGE_GRAPH_POLICY.md |
| Graph maintenance report | HERMES_KNOWLEDGE_GRAPH_POLICY.md: Maintenance reports |
| Graph concept upsert or duplicate/near-duplicate review | entity-resolution-policy.md: Automation boundaries |

## Policy files (under `04_SYSTEM/policies/`)

| File | When loaded |
|---|---|
| `ingestion-policy.md` | Registration, deduplication, status, reprocessing |
| `source-quality-policy.md` | Authority, completeness, freshness, processing depth |
| `privacy-and-access-policy.md` | Sensitivity, licensed material, sharing, external models |
| `claim-and-provenance-policy.md` | Claims, evidence, contradictions, temporal facts, recommendations |
| `entity-resolution-policy.md` | Names, aliases, concept overlap, versions, and evidence-backed non-destructive merge decisions |
| `knowledge-and-memory-architecture.md` | Vault / graph / Qdrant / Memory OS roles and promotion |
| `HERMES_KNOWLEDGE_GRAPH_POLICY.md` | Optional Neo4j evidence, book promotion, span manifests, maintenance reports |
| `HERMES_SOURCE_INTEGRITY_POLICY.md` | Hash, structural completeness, source repair, Qdrant and Neo4j write gate |

Supporting policy files may still be planned or partial; missing files are not orientation blockers. Fall back to the active skill runtime rules and the book/long-form governing policy when needed.
