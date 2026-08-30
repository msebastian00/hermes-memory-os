# Hermes Knowledge Graph Runbook

Optional Neo4j relationship layer on top of Memory OS. Vault remains canonical. Qdrant remains the vector layer. Memory OS remains the durable memory owner. Honcho is out of scope.

## Enablement

Graph expansion is off by default.

```bash
export HERMES_GRAPH_ENABLED=true
export HERMES_GRAPH_CONFIG=/workspace/agent-dev/hermes-memory-os/config/hermes-graph.example.yml
# NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD stay in local environment only.
# Do not print or commit those values.
```

Restart the Hermes session after changing the flag so plugin schemas reload.

Hermes tools (Memory OS provider boundary):

- `graph_retrieve` — Qdrant/Memory OS first, then optional graph expansion
- `graph_build_book` — dry-run by default; upsert needs `human_approved=true` and an approved matching overlap-review report
- `graph_review` — read-only Qdrant-first and Neo4j concept-overlap review; it writes only a report
- `graph_maintenance` — read-only report under the graph reports directory

`graph_policy_ingest` remains staged. `graph_review` is active and read-only.

## Operator CLI (same code path as the tools)

```bash
cd /workspace/agent-dev/hermes-memory-os
export PYTHONPATH=src
hermes-graph --config config/hermes-graph.example.yml check
hermes-graph --config config/hermes-graph.example.yml discover --source-id book-finite-infinite-games-undated
hermes-graph --config config/hermes-graph.example.yml validate-book-source --source-id book-finite-infinite-games-undated
hermes-graph --config config/hermes-graph.example.yml build-book --source-id book-finite-infinite-games-undated --write-mode dry_run --report-out graph/reports/finite-infinite-games-dry-run.json
hermes-graph --config config/hermes-graph.example.yml maintenance --output graph/reports/graph-maintenance.md
```

Allowed book sources are an explicit `graph.allowed_book_source_ids` list in the local graph configuration. Adding a source to that list does not bypass source-integrity, reviewed-chunk, Qdrant, dry-run, or approval gates.

A source must return `ready_for_span_review` from `validate-book-source` before crosswalk or Neo4j upsert. `book-finite-infinite-games-undated` is currently blocked by missing raw-source section markers; its dry-run is diagnostic only. Keep the original extract unchanged, register a complete corrected derivative, then regenerate reviewed chunks and rerun the preflight.

Do not run upsert from Hermes without an explicit `human_approved` tool parameter. Do not start Neo4j or schedule cron from the agent tools.

## Concept-overlap review

Run this after source synthesis and retrieval chunks exist, but before graph upsert:

```bash
hermes-graph --config config/hermes-graph.example.yml review-book-overlap \
  --source-id <source-id> \
  --memory-config <memory-os-config>
```

It reads Qdrant through the existing Memory OS semantic backend first, then Neo4j entity names/aliases and canonical vault concept pages/aliases. It writes only `graph/reports/<source-id>-overlap-review.md`. If `review_complete: false`, restore the unavailable service and rerun. A human must resolve candidates, set `status: approved`, and populate `approved_by` and `approved_at`; pass that report to `build-book --write-mode upsert --overlap-review <report>`. The review cannot merge or alias concepts.

## Health check

```bash
hermes-graph --config config/hermes-graph.example.yml check
```

Expected JSON: `{"neo4j_reachable": true}` when the optional service is up. If Neo4j is down, Hermes `graph_retrieve` still returns Memory OS hits and a `graph_unavailable:*` warning.

## Rollback

```bash
export HERMES_GRAPH_ENABLED=false
# or unset HERMES_GRAPH_ENABLED
```

Restart Hermes. `graph_retrieve` keeps working as Memory OS retrieval. Upserts are refused. Existing Compose stacks, Dockerfiles, Qdrant collections, vault files, and Honcho are untouched.

Stopping an optional Neo4j Compose service is an operator action outside these tools. Do not remove its named volume unless graph data is intentionally discarded.

## Logging

Tools log action, source IDs, write mode, warnings, and result counts. They must never log Neo4j passwords or other secrets.

## Chief-of-Staff maintenance job (template, disabled)

Active CoS window: Daily Brief `30 6 * * *`, Evening Processing `30 20 * * *`. Place graph maintenance after evening reporting:

- Template: `cron/graph-maintenance.job.json`
- Schedule: `30 21 * * *` (daily, after 20:30 UTC)
- Script: `scripts/graph_maintenance_cron.sh` (`no_agent=true`, deliver local)
- Output: `graph/reports/graph-maintenance.md`

Dry-run (no Neo4j, no writes beyond printing the command):

```bash
cd /workspace/agent-dev/hermes-memory-os
GRAPH_MAINTENANCE_DRY_RUN=1 bash scripts/graph_maintenance_cron.sh
```

Enable:

```bash
cp /workspace/agent-dev/hermes-memory-os/scripts/graph_maintenance_cron.sh /root/.hermes/profiles/core-agent/scripts/graph_maintenance_cron.sh
chmod +x /root/.hermes/profiles/core-agent/scripts/graph_maintenance_cron.sh
hermes cron create "30 21 * * *" --name graph-maintenance-review --deliver local
# Then attach the script as no_agent via cronjob update, or:
# cronjob action=create schedule='30 21 * * *' name='graph-maintenance-review' no_agent=true script='graph_maintenance_cron.sh' deliver='local' workdir='/workspace/agent-dev/hermes-memory-os'
```

The create path must set `no_agent=true` and `script=graph_maintenance_cron.sh`. Do not attach an LLM prompt. Do not enable book-build or upsert jobs.

Verify:

```bash
hermes cron list --all
GRAPH_MAINTENANCE_DRY_RUN=1 bash /workspace/agent-dev/hermes-memory-os/scripts/graph_maintenance_cron.sh
```

Rollback:

```bash
hermes cron pause <job_id>
# or
hermes cron remove <job_id>
```

List first; never guess job IDs. Removing the job does not delete existing review reports under `graph/reports`.
