#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_FILE="$ROOT_DIR/test-results/live-demo/live-stack-state.json"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --state-file)
      STATE_FILE="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ ! -f "$STATE_FILE" ]]; then
  echo "State file not found; nothing to stop: $STATE_FILE"
  exit 0
fi

SCRIPT_PID="$(python3 - <<'PY' "$STATE_FILE"
import json, sys
from pathlib import Path
obj = json.loads(Path(sys.argv[1]).read_text())
print(obj.get("script_pid", ""))
PY
)"

if [[ -z "$SCRIPT_PID" ]]; then
  echo "No script_pid in state file; removing stale state file"
  rm -f "$STATE_FILE"
  exit 0
fi

if ! kill -0 "$SCRIPT_PID" >/dev/null 2>&1; then
  echo "Supervisor process already stopped (pid=$SCRIPT_PID)"
  rm -f "$STATE_FILE"
  exit 0
fi

echo "Stopping live stack supervisor pid=$SCRIPT_PID"
kill "$SCRIPT_PID" >/dev/null 2>&1 || true

for _ in {1..30}; do
  if ! kill -0 "$SCRIPT_PID" >/dev/null 2>&1; then
    rm -f "$STATE_FILE"
    echo "Live stack stopped"
    exit 0
  fi
  sleep 1
done

echo "Supervisor still running after grace period; forcing kill"
kill -9 "$SCRIPT_PID" >/dev/null 2>&1 || true
rm -f "$STATE_FILE"
