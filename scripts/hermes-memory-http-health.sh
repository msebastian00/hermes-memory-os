#!/usr/bin/env bash
set -euo pipefail

URL="${HERMES_MEMORY_HTTP_HEALTH_URL:-http://127.0.0.1:8765/health}"

response="$(curl -fsS --max-time "${HERMES_MEMORY_HTTP_HEALTH_TIMEOUT:-5}" "$URL")"

python3 - "$response" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
print(json.dumps(payload, indent=2, sort_keys=True))

if payload.get("ok") is not True or payload.get("degraded") is True:
    reasons = payload.get("degraded_reasons") or []
    print(f"Hermes Memory HTTP is unhealthy: {', '.join(reasons) or 'unknown'}", file=sys.stderr)
    sys.exit(1)

print("Hermes Memory HTTP is healthy.")
PY
