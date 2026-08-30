#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GRAPH_CONFIG="${HERMES_GRAPH_CONFIG:-$ROOT/config/hermes-graph.example.yml}"
MEMORY_CONFIG="${HERMES_MEMORY_CONFIG:-$ROOT/config/hermes-memory-os.semantic.local.yml}"
ENV_FILE="$ROOT/.env.http.local"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  . "$ENV_FILE"
  set +a
fi
WRITE_MODE="upsert"
if [[ "${GRAPH_PROMOTION_DRY_RUN:-0}" == "1" ]]; then
  WRITE_MODE="dry_run"
fi

if [[ "${GRAPH_PROMOTION_PRINT_ONLY:-0}" == "1" ]]; then
  printf "dry_run hermes-graph --config %s promote-queued --memory-config %s --write-mode dry_run\n" "$GRAPH_CONFIG" "$MEMORY_CONFIG"
  exit 0
fi

cd "$ROOT"
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}src"
exec python3 -m hermes_memory_os.graph.cli \
  --config "$GRAPH_CONFIG" \
  promote-queued \
  --memory-config "$MEMORY_CONFIG" \
  --write-mode "$WRITE_MODE"
