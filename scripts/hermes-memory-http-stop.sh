#!/usr/bin/env bash
set -euo pipefail

COMPOSE_DIR="${HERMES_AGENT_PLATFORM_DIR:-/home/mike/agent-platform}"
SERVICE="${HERMES_MEMORY_HTTP_SERVICE:-hermes-memory-http}"

cd "$COMPOSE_DIR"
docker compose stop "$SERVICE"
