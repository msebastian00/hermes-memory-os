# graph_policy_ingest specification (staged, not activated)

Status: draft. Do not activate this tool until the policy adapter and tests exist and are reviewed.

## Purpose

Ingest authoritative vault policy files into Neo4j as evidence-backed `Policy`, `Claim`, and `Evidence` records. This is not a general vault rewrite and not a silent conflict resolver.

## Authority

- Authoritative files: `wiki-brain/vault/04_SYSTEM/policies/`
- Packaged copies under `agent-dev/skill-review/hermes-vault-foundation-policies/` are offline references only. The vault copy wins.
- Existing policy and ontology names override extracted names.
- Never change policy files.
- Never silently resolve policy conflicts. Conflicts become review items only.

## Allowed writes

When activated, the adapter may create only:

- `Policy` nodes (stable IDs from policy file path + title)
- `Claim` nodes with `claim_type: policy`
- `Evidence` nodes quoting the policy text span
- `APPLIES_TO` / `CONSTRAINS` relationships that include `evidence_id` and `confidence`

It must not write Qdrant points, SQLite memories, raw sources, vault notes, or policy files.

## Required provenance

Every policy claim must include:

- source path relative to the vault
- quote / span
- checksum of the policy file
- `claim_basis: policy`
- `verification_status: policy-authoritative` only for direct quotes; interpretations stay unverified and go to review

## Activation gate

Do not register `graph_policy_ingest` in Hermes tool schemas until:

1. A dedicated policy source adapter exists (separate from the book adapter).
2. Unit tests cover: vault-wins naming, conflict-to-review, no file mutation, idempotent upserts, and refusal to ingest paths outside `04_SYSTEM/policies`.
3. Human review of this spec is recorded.

Until then the dispatcher returns `status: not_activated`.

## Conflict handling

If two policies disagree:

1. Create a review item (see `graph-review-spec.md`).
2. Keep both claims.
3. Do not pick a winner.
4. Surface the conflict in maintenance reports.
