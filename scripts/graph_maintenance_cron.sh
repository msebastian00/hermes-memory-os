#!/usr/bin/env bash
# Read-only graph maintenance job.
# Writes only under hermes-memory-os/graph/reports.
# Never builds books, writes Qdrant, upserts Neo4j, or rewrites policies/vault/Memory OS.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${HERMES_GRAPH_CONFIG:-${ROOT}/config/hermes-graph.example.yml}"
REPORTS="${ROOT}/graph/reports"
OUTPUT="${GRAPH_MAINTENANCE_OUTPUT:-${REPORTS}/graph-maintenance.md}"
PYTHON="${HERMES_GRAPH_PYTHON:-${ROOT}/.venv/bin/python}"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

log() {
  # Never print env dumps, URIs with userinfo, or password-like values.
  printf '%s\n' "$*" >&2
}

refuse_forbidden() {
  case "${OUTPUT}" in
    *build-book*|*upsert*|*qdrant*)
      log "refusing forbidden output path"
      exit 2
      ;;
  esac
}

ensure_reports_dir() {
  mkdir -p "${REPORTS}"
  resolved_output="$(python3 -c 'import os,sys; from pathlib import Path; r=Path(sys.argv[1]).resolve(); o=Path(sys.argv[2]).resolve();
print(o);
raise SystemExit(0 if (o==r or r in o.parents) else 2)' "${REPORTS}" "${OUTPUT}")"
  OUTPUT="${resolved_output}"
}

write_degraded() {
  local reason="$1"
  cat > "${OUTPUT}" <<EOF
---
type: graph-maintenance-report
status: generated
health: degraded
---

# Graph Maintenance Review

- Count: 0
- Health: ${reason}
- This report is a review artifact, never an autonomous correction.
EOF
}

run_maintenance() {
  "${PYTHON}" -m hermes_memory_os.graph.cli --config "${CONFIG}" maintenance --output "${OUTPUT}"
}

main() {
  refuse_forbidden
  ensure_reports_dir

  if [[ "${GRAPH_MAINTENANCE_DRY_RUN:-0}" == "1" ]]; then
    printf '%s\n' "dry_run hermes-graph --config ${CONFIG} maintenance --output ${OUTPUT}"
    exit 0
  fi

  if [[ ! -f "${CONFIG}" ]]; then
    log "graph config missing"
    exit 2
  fi

  check_json="$("${PYTHON}" -m hermes_memory_os.graph.cli --config "${CONFIG}" check 2>/dev/null || true)"
  if ! printf '%s' "${check_json}" | grep -q '"neo4j_reachable": true'; then
    write_degraded "neo4j_unavailable"
    # Optional layer: stay silent to the user; report file is the artifact.
    exit 0
  fi

  run_maintenance
}

main "$@"
