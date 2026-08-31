---
type: system
status: active
date: 2026-08-01
tags: [vault, policies, index]
---

# Vault policies

Authoritative policies live in this folder. Skills may ship a packaged copy under `references/` for offline use; **the vault copy wins** when both exist.

## Present

| File | Status | Governs |
|------|--------|---------|
| `POLICY_ROUTER.md` | active | Progressive policy loading trigger map (read first; do not preload full policies every run) |
| `BOOKMARK_INGESTION_POLICY.md` | active | Browser/X bookmarks, short article URLs |
| `book-and-longform-knowledge-ingestion-policy.md` | active | Books, reports, long articles, long transcripts |
| `HERMES_KNOWLEDGE_GRAPH_POLICY.md` | active | Optional Neo4j evidence, book promotion, span manifests, maintenance reports |
| `HERMES_SOURCE_INTEGRITY_POLICY.md` | active | Structural source completeness, corrected-extract handling, Qdrant and Neo4j write gate |
| `entity-resolution-policy.md` | active | Entity aliases, duplicate and near-duplicate review, human-only merge decisions |

## Referenced by book-longform skill — not yet written

Create these here when ready. Until then, Hermes uses defaults in the book policy + this README and must not hard-fail orientation.

| Planned file | Purpose |
|--------------|---------|
| `knowledge-and-memory-architecture.md` | Four layers: raw source, canonical wiki, graph/retrieval, Memory OS locators; Qdrant collection roles |
| `ingestion-policy.md` | Cross-cutting intake rules shared by bookmarks, books, transcripts, captures |
| `source-quality-policy.md` | Authority, completeness, edition trust, when to catalog vs deep-process |
| `privacy-and-access-policy.md` | Sensitivity labels, sharing limits, what may enter Memory OS / cloud |
| `claim-and-provenance-policy.md` | Claim vs evidence vs interpretation; required locators; contradiction handling |

## Naming

- Prefer kebab-case for new policies: `book-and-longform-knowledge-ingestion-policy.md`
- Existing `BOOKMARK_INGESTION_POLICY.md` kept for backward compatibility

## Related system docs (not policies, but orientation)

- `04_SYSTEM/HERMES.md`
- `04_SYSTEM/CHIEF_OF_STAFF.md`
- `04_SYSTEM/MEMORY_POLICY.md`
- `03_RESOURCES/books/_README.md`
