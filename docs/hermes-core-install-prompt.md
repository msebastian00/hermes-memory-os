# Hermes Core Installation Prompt

Give the following to Hermes after updating the versioned Memory OS repository.

```text
Install the Hermes knowledge-graph skill and two versioned graph cron jobs from /workspace/agent-dev/hermes-memory-os.

Scope and safety:
- Operate only on the Core Agent profile. Use docker exec hermes-core (or the hermes alias), never hermes-memory-agent.
- First inspect the checked-out repository, current Core-Agent skills, and existing cron jobs. Do not guess job IDs.
- Do not modify Dockerfiles, Compose files, vault content, policies, Qdrant collections, Neo4j data, SQLite data, or local .env files.
- Do not print secrets or dump environments.
- The repository is authoritative for this skill, scripts, and job templates. The live vault is authoritative for policies.

Install or update:
1. Verify skills/hermes-knowledge-graph/SKILL.md, scripts/graph_maintenance_cron.sh, scripts/graph_promotion_sweep_cron.sh, cron/graph-maintenance.job.json, and cron/graph-promotion-sweep.job.json are present.
2. Copy the skill into the Core Agent profile skill directory, replacing only this skill's prior copy.
3. Copy both scripts into the Core Agent profile scripts directory and make them executable.
4. Inspect hermes cron list --all. Reconcile only graph-maintenance-review and graph-promotion-sweep with the JSON templates. Create only a missing job.
5. graph-maintenance-review: 30 21 * * *, no_agent=true, deliver=local, graph_maintenance_cron.sh, workdir=/workspace/agent-dev/hermes-memory-os.
6. graph-promotion-sweep: 30 1 * * *, no_agent=true, deliver=local, graph_promotion_sweep_cron.sh, workdir=/workspace/agent-dev/hermes-memory-os.
7. Run documented print-only or dry-run checks. Do not perform a live promotion during installation.
8. Reload Core Agent only if needed for skill discovery. Report skill path, job IDs, schedules, enabled state, and dry-run results without secrets.

Success is exactly one configured job of each name and the versioned Core Agent skill. It is not a graph-data rewrite.
```
