# Knowledge Graph Discovery Report

## Scope

This report records the inspected integration boundaries before the Neo4j graph layer was added. Jordan Peterson artifacts and Honcho are explicitly excluded.

## Located systems

- Hermes runtime: hermes/hermes-agent. Existing containers expose Hermes on 9000 and the memory agent on 9002.
- Memory OS implementation: agent-dev/hermes-memory-os.
- Active Memory OS data: memory/hermes-memory-data/db/memory.sqlite.
- Active Memory OS HTTP service: port 8765.
- Human-facing knowledge layer: wiki-brain/vault.
- Canonical book pages: wiki-brain/vault/02_WIKI/sources/books.
- Raw book sources and manifests: wiki-brain/vault/03_RESOURCES/books/raw.
- Existing book-analysis outputs: wiki-brain/vault/06_GENERATED/source-analysis.
- Qdrant configuration: agent-dev/hermes-memory-os/config/hermes-memory-os.semantic.local.yml.
- Qdrant collections: hermes_memories, hermes_wiki, hermes_captures, hermes_sources, and hermes_agent_learning.
- Chief-of-Staff instructions and workflows: wiki-brain/vault/04_SYSTEM.
- Policies: wiki-brain/vault/04_SYSTEM/policies and the reviewed policy package under agent-dev/skill-review/hermes-vault-foundation-policies.

## Authority and constraints

Vault paths, frontmatter, canonical source pages, and policy-defined identity/provenance rules are authoritative. Obsidian remains the human-facing layer. Qdrant remains the vector layer. Memory OS remains the durable memory owner. No Hermes Dockerfile, Docker Compose stack, source artifact, policy file, vault content, ingestion script, or Honcho configuration is changed by this graph layer.

## First vertical slice

The selected already-ingested source is book-finite-infinite-games-undated, Finite and Infinite Games by James P. Carse.

Existing artifacts include:

- Immutable raw source with recorded SHA-256.
- Canonical source synthesis with human-reviewed concepts, claims, limits, and links.
- Four generated retrieval chunks with section and page metadata.
- An ingestion report recording source quality and caveats.

The existing artifacts report that this book has no verified Qdrant points. The graph builder therefore preserves null crosswalks, emits embedding-missing review warnings, and never creates Qdrant data.

## Risk assessment

The optional Neo4j Compose service binds only localhost ports 7474 and 7687 and uses a separate named volume. The builder defaults to dry_run. A graph write requires explicit upsert mode plus Neo4j credentials. Existing raw-book manifests include some legacy or inaccessible entries; discovery skips only those unrelated entries and reads the requested source through its existing metadata.
