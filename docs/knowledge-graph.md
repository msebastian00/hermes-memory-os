# Hermes Knowledge Graph

## Purpose

This optional layer adds Neo4j relationship traversal to Memory OS. It does not replace the Obsidian vault, existing book ingestion, Qdrant, Hermes core, or policy files.

## Inputs and authority

- Canonical human-facing source: wiki-brain vault.
- Vector retrieval: Qdrant, queried before graph expansion.
- Graph source for the first slice: reviewed Finite and Infinite Games artifacts.
- Claim, provenance, entity-resolution, and book-ingestion policies remain authoritative.
- Generated source claims remain attributed to the author, use the author-framework claim basis, and are not treated as empirical facts.

## Configuration

Copy config/hermes-graph.example.yml to a local path and set the vault root if this repository moves. Keep the default write mode as dry_run.

Set these local environment variables only when Neo4j operations are needed:

    export NEO4J_URI=http://127.0.0.1:7474
    export NEO4J_USER=neo4j
    export NEO4J_PASSWORD=local-secret

## Neo4j baseline

The isolated Compose file does not affect the existing Hermes stack.

    cd deploy/neo4j
    cp .env.example .env
    docker compose up -d
    hermes-graph --config ../../config/hermes-graph.example.yml check
    hermes-graph --config ../../config/hermes-graph.example.yml init

Validation and rollback:

    docker compose config
    docker compose ps
    docker compose stop

Stopping the optional service preserves its named volume. Do not run a volume removal command unless the graph data is intentionally being discarded.

## One-book slice

## Source integrity gate

Run the deterministic source-integrity preflight before preparing a span manifest, Qdrant crosswalk, or Neo4j write:

    hermes-graph --config config/hermes-graph.example.yml validate-book-source --source-id book-finite-infinite-games-undated

`ready_for_span_review` permits human review of exact chunk spans. `blocked` permits diagnosis only: do not create Qdrant points, a crosswalk, Neo4j records, new source claims, or canonical wiki changes. A hash match alone is insufficient; retrieval ranges must also be supported by the raw extract. Correct an incomplete extraction as a new immutable derivative, retain the original for audit, then regenerate its reviewed chunks.

The selected source is book-finite-infinite-games-undated. It has generated retrieval metadata but no verified Qdrant points, so the dry run reports embedding_missing warnings and writes no vector data. It is currently blocked by source-integrity validation because 32 section markers referenced by its reviewed chunks are absent from the registered raw extract. Do not upsert it until a complete corrected extraction has passed the preflight.

    hermes-graph --config config/hermes-graph.example.yml discover --source-id book-finite-infinite-games-undated
hermes-graph --config config/hermes-graph.example.yml validate-book-source --source-id book-finite-infinite-games-undated
    hermes-graph --config config/hermes-graph.example.yml build-book --source-id book-finite-infinite-games-undated --write-mode dry_run --report-out graph/reports/finite-infinite-games-dry-run.json

After reviewing the report and initializing Neo4j, write the same stable plan with MERGE upserts:

    hermes-graph --config config/hermes-graph.example.yml build-book --source-id book-finite-infinite-games-undated --write-mode upsert

If an existing Qdrant point crosswalk becomes available, provide a JSON object from existing retrieval-chunk IDs to Qdrant point IDs. The builder never creates embeddings or Qdrant points.

## Concept-overlap review

Before a concept-bearing source is upserted, generate an overlap report using Qdrant-first candidate discovery and Neo4j entity/alias comparison:

    hermes-graph --config config/hermes-graph.example.yml review-book-overlap --source-id <source-id> --memory-config <memory-os-config>

The command writes only `graph/reports/<source-id>-overlap-review.md`. Restore both services and rerun if its frontmatter says `review_complete: false`. A human resolves candidate classifications in the report, then changes the frontmatter to `status: approved` and supplies `approved_by` and `approved_at`. The matching approved report is required for upsert:

    hermes-graph --config config/hermes-graph.example.yml build-book --source-id <source-id> --write-mode upsert --overlap-review graph/reports/<source-id>-overlap-review.md

This gate does not merge entities or create aliases. It blocks only graph promotion; normal raw-source preservation and non-graph ingestion remain unchanged.

## Retrieval and maintenance

GraphRetrievalAdapter calls the Memory OS semantic backend first, then expands matching graph chunks through Neo4j. It returns a compact context packet with evidence, chunk IDs, Qdrant point IDs, and warnings. Unsupported and low-confidence graph facts are excluded by default.

Graph retrieval expansion and graph upserts at the Memory OS provider boundary are gated by `HERMES_GRAPH_ENABLED=false` by default. The read-only `graph_review` tool may generate review artifacts while expansion is disabled. See docs/knowledge-graph-runbook.md for enablement, rollback, and health checks. `graph_policy_ingest` remains staged. `graph_review` is active, read-only, and requires human approval outside the tool before a graph upsert.

Maintenance is additive and read-only against graph data. It reports duplicate entities, claims without evidence, low-confidence relationships, policy conflicts, and missing Qdrant crosswalks.

    hermes-graph --config config/hermes-graph.example.yml maintenance --output graph/reports/graph-maintenance.md

Schedule that command beside the existing Chief-of-Staff workflow only after it is reviewed. It does not rewrite Memory OS or vault content; the report is generated under this package's graph/reports directory by default.
