# Reproducible Deployment

This repository reproduces Memory OS and knowledge-graph software plus non-secret operational configuration. It intentionally excludes personal vault content, raw books, generated knowledge, credentials, and database data.

The live vault is authoritative. The committed policy snapshot is a recovery copy only.

## Contents And Exclusions

Git contains Memory OS and graph code, Neo4j Compose, non-secret examples, Core-Agent cron templates/scripts, an empty vault layout, and a hash-verified snapshot of operational policy files.

Git never contains raw books, PDFs, EPUBs, images, notes, queue entries, generated reports, `.env` files, local configuration, passwords, API keys, Neo4j volumes, Qdrant snapshots, SQLite databases, embeddings, or graph records. The repository ignores `backups/`, `runtime-backups/`, `*.snapshot`, and `*.dump`; keep backups outside the checkout.

## 1. Clone And Test

```bash
git clone git@github.com:msebastian00/hermes-memory-os.git
cd hermes-memory-os
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[http,qdrant,test]'
export PYTHONPATH="$PWD/src"
.venv/bin/python -m pytest tests/test_reproducibility.py tests/test_graph.py -q
```

## 2. Create An Empty Vault

The default creates directories only. It writes no content.

```bash
python3 scripts/bootstrap_vault.py --vault-root /srv/hermes-vault --dry-run
python3 scripts/bootstrap_vault.py --vault-root /srv/hermes-vault
```

To restore only the non-secret versioned policies into a new vault:

```bash
python3 scripts/bootstrap_vault.py --vault-root /srv/hermes-vault --install-policy-snapshot
python3 scripts/bootstrap_vault.py --verify-policy-snapshot
```

The utility refuses to overwrite a different live policy. Resolve any difference in the live vault deliberately.

## 3. Configure Local Services

Create ignored local configuration files from the tracked examples:

```bash
cp config/hermes-memory-os.example.yml config/hermes-memory-os.local.yml
cp config/hermes-graph.example.yml config/hermes-graph.local.yml
```

Set these values only in protected local environment/configuration:

```bash
HERMES_MEMORY_HOME=/absolute/path/to/hermes-memory-data
NEO4J_URI=http://neo4j:7474
NEO4J_USER=neo4j
NEO4J_PASSWORD=<local-secret>
QDRANT__SERVICE__API_KEY=<local-secret>
HERMES_MEMORY_HTTP_API_KEY=<local-secret>
HERMES_GRAPH_ENABLED=true
HERMES_GRAPH_VISUAL_ENABLED=true
HERMES_GRAPH_VLM_BASE_URL=<private-vlm-endpoint>
HERMES_GRAPH_VLM_MODEL=qwen36
```

For Dockerized Memory OS, use the Docker-network Neo4j URI. Set `paths.vault_root` in the local graph configuration to the private vault created above.

## 4. Start And Verify

Create the external network only if the platform does not already own it:

```bash
docker network inspect agent-platform_default >/dev/null 2>&1 || docker network create agent-platform_default
```

Start Neo4j with a locally supplied password:

```bash
set -a
. ./.env.http.local
set +a
docker compose -f deploy/neo4j/docker-compose.yml up -d neo4j
docker compose -f deploy/neo4j/docker-compose.yml ps
```

Start Qdrant and Memory HTTP through the platform Compose deployment, then verify:

```bash
bash scripts/hermes-memory-http-health.sh
hermes-graph --config config/hermes-graph.local.yml check
```

Memory HTTP must be healthy and the graph check must report `neo4j_reachable: true`. Qdrant remains the vector layer; Neo4j only expands Qdrant/Memory OS results.

## 5. Rebuild Graph Data

Data rebuilds from the private canonical vault, not Git. Validate and dry-run every queue-authorized source before upsert:

```bash
hermes-graph --config config/hermes-graph.local.yml validate-book-source --source-id <source-id>
hermes-graph --config config/hermes-graph.local.yml promote-queued-book --source-id <source-id> --memory-config config/hermes-memory-os.local.yml --write-mode dry_run
hermes-graph --config config/hermes-graph.local.yml promote-queued-book --source-id <source-id> --memory-config config/hermes-memory-os.local.yml --write-mode upsert
```

Run maintenance afterwards and verify ordinary retrieval through Memory OS. The versioned promotion-sweep job automates the same machine-gated process.

## 6. Install Core-Agent Skill And Jobs

Use [the Core-Agent installation prompt](hermes-core-install-prompt.md). It installs only the versioned skill and scripts into the Core Agent profile, creates or reconciles the two graph jobs, and runs dry checks. It must never target `hermes-memory-agent`.

Scheduler registration is local runtime state. Record job IDs in an operator-only system log, not Git.

## 7. Back Up Runtime Data Outside Git

Create a protected destination outside the checkout:

```bash
install -d -m 700 /srv/hermes-runtime-backups/$(date -u +%Y%m%dT%H%M%SZ)
```

SQLite supports a consistent online backup:

```bash
sqlite3 "$HERMES_MEMORY_HOME/db/memory.sqlite" ".backup '/srv/hermes-runtime-backups/<timestamp>/memory.sqlite'"
```

Use authenticated Qdrant collection snapshots for every configured collection; store snapshot names and SHA-256 checksums in that protected destination. Neo4j Community dumps require an approved maintenance window because `neo4j-admin database dump` requires the database stopped. Stop only Neo4j, dump the named graph volume with the matching `neo4j:5-community` image, restart Neo4j, and run the graph health check. Never delete or recreate volumes during backup.

Test restoration on empty test volumes before relying on a backup. Encrypt backups at rest and keep them out of GitHub.

## Rollback

```bash
export HERMES_GRAPH_ENABLED=false
```

Restart Core Agent. Memory OS retrieval remains available without Neo4j expansion.
