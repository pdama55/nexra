#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BASE_URL="http://127.0.0.1:8000"
STATE_FILE="$ROOT_DIR/test-results/live-demo/live-stack-state.json"
LOG_FILE="$ROOT_DIR/test-results/live-demo/live-stack.log"
WAIT_SECONDS=120

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)
      BASE_URL="$2"
      shift 2
      ;;
    --state-file)
      STATE_FILE="$2"
      shift 2
      ;;
    --log-file)
      LOG_FILE="$2"
      shift 2
      ;;
    --wait-seconds)
      WAIT_SECONDS="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

mkdir -p "$(dirname "$STATE_FILE")" "$(dirname "$LOG_FILE")"

if [[ -f "$STATE_FILE" ]]; then
  EXISTING_PID="$(python3 - <<'PY' "$STATE_FILE"
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
if not path.exists():
    print("")
    raise SystemExit(0)
try:
    obj = json.loads(path.read_text())
except Exception:
    print("")
    raise SystemExit(0)
print(obj.get("script_pid", ""))
PY
)"
  if [[ -n "$EXISTING_PID" ]] && kill -0 "$EXISTING_PID" >/dev/null 2>&1; then
    echo "Live stack already running (pid=$EXISTING_PID, state=$STATE_FILE)"
    exit 0
  fi
fi

export NEXRA_NO_AUTO_OPEN=1
export NEXRA_NO_TAIL=1
export NEXRA_SKIP_NGROK="${NEXRA_SKIP_NGROK:-1}"
export NEXRA_SKIP_DEMO_AGENTS="${NEXRA_SKIP_DEMO_AGENTS:-1}"
export NEXRA_SKIP_DASHBOARD="${NEXRA_SKIP_DASHBOARD:-1}"
export NEXRA_STATE_FILE="$STATE_FILE"
export NEXRA_API_BASE_URL="$BASE_URL"

"$ROOT_DIR/scripts/run_live_demo.sh" >"$LOG_FILE" 2>&1 &
LAUNCH_PID=$!

echo "Started live stack launcher pid=$LAUNCH_PID"
echo "State file: $STATE_FILE"
echo "Launcher log: $LOG_FILE"

START_TS="$(date +%s)"
while true; do
  if ! kill -0 "$LAUNCH_PID" >/dev/null 2>&1; then
    echo "Live stack launcher exited unexpectedly. Recent log:" >&2
    tail -n 80 "$LOG_FILE" >&2 || true
    exit 1
  fi

  if [[ -f "$STATE_FILE" ]] && curl -sf "$BASE_URL/health" >/dev/null 2>&1; then
    break
  fi

  if (( $(date +%s) - START_TS > WAIT_SECONDS )); then
    echo "Timed out waiting for live stack readiness" >&2
    tail -n 80 "$LOG_FILE" >&2 || true
    exit 1
  fi

  sleep 1
done

SCRIPT_PID="$(python3 - <<'PY' "$STATE_FILE"
import json, sys
from pathlib import Path
obj = json.loads(Path(sys.argv[1]).read_text())
print(obj.get("script_pid", ""))
PY
)"

echo "Live stack ready (supervisor pid=${SCRIPT_PID:-unknown})"
