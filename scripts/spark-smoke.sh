#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_PATH="${HERMES_CONFIG_PATH:-${ROOT_DIR}/config/hermes-memory-os.prod.yml}"
HERMES_MEMORY_HOME="${HERMES_MEMORY_HOME:-/home/mike/.hermes/memory}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

export HERMES_MEMORY_HOME
export PYTHONPATH="${ROOT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"

run_cli() {
  "${PYTHON_BIN}" -m hermes_memory_os.cli --config "${CONFIG_PATH}" "$@"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing required command: $1" >&2
    exit 1
  fi
}

assert_results() {
  local query="$1"
  shift
  local output_file
  output_file="$(mktemp)"
  run_cli search "$query" "$@" >"${output_file}"
  "${PYTHON_BIN}" - "${output_file}" <<'PYCHECK'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if not payload.get("results"):
    raise SystemExit("search returned no results")
PYCHECK
  rm -f "${output_file}"
}

require_command curl
require_command "${PYTHON_BIN}"

if command -v ollama >/dev/null 2>&1 && [[ "${HERMES_SKIP_OLLAMA_PULL:-0}" != "1" ]]; then
  ollama pull nomic-embed-text
fi

curl --fail --silent --show-error http://127.0.0.1:11434/api/tags >/dev/null
curl --fail --silent --show-error http://127.0.0.1:6333/ >/dev/null

run_cli init >/dev/null
run_cli doctor --strict >/dev/null
run_cli reindex-memories >/dev/null

run_cli add \
  --type fact \
  --scope system \
  --title "Semantic smoke" \
  --summary "Hermes Memory OS indexes durable memories into Qdrant." \
  --text "Hermes Memory OS indexes durable memories into Qdrant for semantic recall." >/dev/null

assert_results "vector recall substrate"

work_dir="$(mktemp -d)"
trap 'rm -rf "${work_dir}"' EXIT

cat >"${work_dir}/hermes-memory-book.txt" <<'BOOKEOF'
Chapter 1 Organizational Memory

Hermes should connect durable personal memory with external source libraries.
The memory substrate keeps books separate from Mike's own durable preferences.
BOOKEOF

cat >"${work_dir}/hermes-memory-transcript.srt" <<'SRTEOF'
1
00:00:01,000 --> 00:00:04,000
Mike: Hermes should cite transcript moments when recalling source material.
SRTEOF

run_cli ingest --path "${work_dir}/hermes-memory-book.txt" --source-type book --reindex >/dev/null
run_cli ingest --path "${work_dir}/hermes-memory-transcript.srt" --reindex >/dev/null

assert_results "external source libraries" --source-type book
assert_results "cite what Mike said" --source-type subtitle

run_cli provider-smoke >/dev/null
run_cli doctor --strict
