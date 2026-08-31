# Hermes Knowledge Graph Runbook

Optional Neo4j relationship layer on top of Memory OS. Vault remains canonical. Qdrant remains the vector layer. Memory OS remains the durable memory owner. Honcho is out of scope.

For a from-scratch, secrets-free deployment and recovery procedure, including the empty vault bootstrap, policy snapshot, Core-Agent job installation, and external database backup requirements, see [Reproducible Deployment](reproducibility.md).

## Enablement

Graph expansion is off by default.

```bash
export HERMES_GRAPH_ENABLED=true
export HERMES_GRAPH_CONFIG=/workspace/agent-dev/hermes-memory-os/config/hermes-graph.example.yml
# NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD stay in local environment only.
# Do not print or commit those values.
```

Restart the Hermes session after changing the flag so plugin schemas reload.

## Service endpoints

Spark 2 publishes durable Compose endpoints for local and LAN/Tailscale clients:

- Qdrant REST: `http://192.168.7.37:6333` (gRPC: `192.168.7.37:6334`)
- Memory HTTP: `http://192.168.7.37:8765`

Qdrant requires the `api-key` header. Its key is stored only in `agent-dev/hermes-memory-os/.env.http.local` as `QDRANT__SERVICE__API_KEY`; it is loaded by the Qdrant container and the graph promotion wrapper and must never be committed or printed. Memory HTTP requires its existing bearer token. Remote clients, including Alienware, should use Memory HTTP for ordinary retrieval; direct Qdrant access is for trusted maintenance clients that have the local Qdrant key.

For a local direct graph command, load the non-committed service environment first:

```bash
set -a
. /workspace/agent-dev/hermes-memory-os/.env.http.local
set +a
```
## Visual extraction

Spark 1 is the primary local visual-semantic provider. The validated dedicated ConnectX path is:

```bash
export HERMES_GRAPH_VLM_BASE_URL=http://192.168.100.11:8002/v1
export HERMES_GRAPH_VLM_MODEL=qwen36
```

This is an internal endpoint, not a credential. Keep it in the local service environment rather than a committed configuration file. The running server exposes `qwen36`; `qwen36-deep` is not currently registered. The adapter disables thinking so structured extraction has a usable completion budget.

The adapter renders the requested PDF pages locally, preserves each rendered image hash and page number, and writes derived records only beneath `graph/reports/multimodal/`. It does not rewrite raw books, vault pages, Qdrant, or Memory OS. Run dry-run first:

```bash
cd /workspace/agent-dev/hermes-memory-os
export PYTHONPATH=src
hermes-graph --config config/hermes-graph.local.yml extract-visual-evidence \
  --source-id <source-id> \
  --pdf /absolute/path/to/book.pdf \
  --first-page 1 --last-page 10 \
  --write-mode dry_run
```

An upsert adds only existing `Evidence`, `Claim`, `SUPPORTS`, and `ABOUT` graph records. It requires an immutable attachment hash, page-to-reviewed-chunk mapping, extractor provenance, and confidence at or above `0.75`. Records that fail a machine gate remain in the report with warnings. Visual claims attach to the existing source chunk, so current Qdrant-first retrieval can expand to them through Neo4j.

Queued promotion invokes this path automatically when the non-committed local environment sets `HERMES_GRAPH_VISUAL_ENABLED=true`, `HERMES_GRAPH_VLM_BASE_URL`, and `HERMES_GRAPH_VLM_MODEL`. It resolves only a manifest-declared immutable PDF (`original_path`, `companion_pdf`, or `pdf_path`); a source without one is reported as `not_applicable` and its text promotion continues unchanged.

Hermes tools (Memory OS provider boundary):

- `graph_retrieve` — Qdrant/Memory OS first, then optional graph expansion
- `graph_build_book` — diagnostic dry-run or direct graph plan for a source already authorized by the book-ingestion queue
- `graph_promote_book` — autonomous queue-authorized promotion: integrity, exact spans, Qdrant crosswalk, graph dry-run, Qdrant upsert, Neo4j upsert, and reports
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

A source in `05_QUEUE/book-ingestion/incoming`, `processing`, or `completed` is authorized for autonomous graph promotion. It still must pass source-integrity, reviewed-chunk, exact-span, Qdrant crosswalk, evidence, confidence, and dry-run gates.

A source must return `ready_for_span_review` from `validate-book-source` before crosswalk or Neo4j upsert. `book-finite-infinite-games-undated` is currently blocked by missing raw-source section markers; its dry-run is diagnostic only. Keep the original extract unchanged, register a complete corrected derivative, then regenerate reviewed chunks and rerun the preflight.

If an already-promoted source later fails source integrity, quarantine it before repair. Quarantine is reversible: it retains the Qdrant points, SQLite chunks, Neo4j records, and raw artifact for audit, but excludes the source from Memory OS retrieval and graph expansion.

```bash
hermes-graph --config config/hermes-graph.local.yml quarantine-book   --source-id <source-id>   --memory-config config/hermes-memory-os.docker.semantic.yml   --write-mode dry_run
# Repeat with --write-mode upsert only after the dry-run identifies the intended active crosswalk source.
```

Autonomous queued promotion applies the same quarantine when a previously active source fails its integrity gate, before it can regenerate derived artifacts.

Use `promote-queued-book` for an end-to-end promotion. It is idempotent and runs both dry validations before it creates Qdrant points or Neo4j records. The queue is authorization; a failed machine gate defers the source and writes a report. Only the checked-in crosswalk adapter may write graph crosswalk points or indexing state; embedding text must exactly equal its declared source span.

## Concept-overlap review

Run this after source synthesis and retrieval chunks exist, but before graph upsert:

```bash
hermes-graph --config config/hermes-graph.example.yml review-book-overlap \
  --source-id <source-id> \
  --memory-config <memory-os-config>
```

It reads Qdrant through the existing Memory OS semantic backend first, then Neo4j entity names/aliases and canonical vault concept pages/aliases. It writes `graph/reports/<source-id>-overlap-review.md` as evidence. Exact normalized identities reuse their deterministic entity ID; near matches remain distinct and are reported as possible associations. The review never merges or aliases concepts.

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

The create path must set `no_agent=true` and `script=graph_maintenance_cron.sh`. Do not attach an LLM prompt.

## Autonomous promotion sweep (template, disabled)

Hermes owns the schedule; Memory OS owns the versioned command. The sweep reads queue-authorized sources and promotes only sources that pass every machine gate.

- Template: `cron/graph-promotion-sweep.job.json`
- Schedule: `30 1 * * *` (daily UTC; safely after the M/W/F 22:30 book-ingest run)
- Script: `scripts/graph_promotion_sweep_cron.sh` (`no_agent=true`, deliver local)
- Reports: `graph/reports/promotions/queued-sweep.json` and source-specific evidence reports

Dry-run:

```bash
cd /workspace/agent-dev/hermes-memory-os
GRAPH_PROMOTION_DRY_RUN=1 bash scripts/graph_promotion_sweep_cron.sh
```

Enable through Hermes with `no_agent=true`, `script=graph_promotion_sweep_cron.sh`, `schedule=30 1 * * *`, `deliver=local`, and `workdir=/workspace/agent-dev/hermes-memory-os`. Do not attach an LLM prompt. The scheduler environment must contain the existing local `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD` values without logging them.

Verify:

```bash
hermes cron list --all
GRAPH_MAINTENANCE_DRY_RUN=1 bash /workspace/agent-dev/hermes-memory-os/scripts/graph_maintenance_cron.sh
GRAPH_PROMOTION_DRY_RUN=1 bash /workspace/agent-dev/hermes-memory-os/scripts/graph_promotion_sweep_cron.sh
```

Rollback:

```bash
hermes cron pause <job_id>
# or
hermes cron remove <job_id>
```

List first; never guess job IDs. Removing the job does not delete existing review reports under `graph/reports`.
