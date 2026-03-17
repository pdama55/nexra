#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MODE="attach"
BASE_URL="http://127.0.0.1:8000"
RESULTS_DIR="$ROOT_DIR/test-results/live-demo/$(date +%Y%m%d-%H%M%S)"
STRICT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --base-url)
      BASE_URL="$2"
      shift 2
      ;;
    --results-dir)
      RESULTS_DIR="$2"
      shift 2
      ;;
    --strict)
      STRICT=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ "$MODE" != "attach" && "$MODE" != "bootstrap" ]]; then
  echo "--mode must be attach or bootstrap" >&2
  exit 1
fi

mkdir -p "$RESULTS_DIR"

MOCK_SINK_PORT="${NEXRA_MOCK_SINK_PORT:-8800}"
MOCK_SINK_BASE_URL="http://127.0.0.1:${MOCK_SINK_PORT}"
STACK_STATE_FILE="$RESULTS_DIR/live-stack-state.json"
STACK_LOG_FILE="$RESULTS_DIR/live-stack.log"
MOCK_SINK_LOG="$RESULTS_DIR/mock-sink.log"

MOCK_SINK_PID=""
SUITE_EXIT=0
BOOTSTRAPPED=0

cleanup() {
  if [[ "$BOOTSTRAPPED" == "1" ]]; then
    "$ROOT_DIR/scripts/stop_live_stack.sh" --state-file "$STACK_STATE_FILE" >/dev/null 2>&1 || true
  fi

  if [[ -n "$MOCK_SINK_PID" ]] && kill -0 "$MOCK_SINK_PID" >/dev/null 2>&1; then
    kill "$MOCK_SINK_PID" >/dev/null 2>&1 || true
    wait "$MOCK_SINK_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "Results directory: $RESULTS_DIR"

echo "Starting local mock sink on port $MOCK_SINK_PORT"
python3 "$ROOT_DIR/scripts/live_demo_mock_sink.py" \
  --port "$MOCK_SINK_PORT" \
  --out-dir "$RESULTS_DIR" \
  --fail-endpoint slack >"$MOCK_SINK_LOG" 2>&1 &
MOCK_SINK_PID=$!

for _ in {1..30}; do
  if curl -sf "$MOCK_SINK_BASE_URL/_health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! curl -sf "$MOCK_SINK_BASE_URL/_health" >/dev/null 2>&1; then
  echo "Mock sink failed to start. Log:" >&2
  cat "$MOCK_SINK_LOG" >&2 || true
  exit 1
fi

if [[ "$MODE" == "bootstrap" ]]; then
  echo "Starting live stack in bootstrap mode"
  BOOTSTRAPPED=1

  export SENDGRID_API_KEY="sg-local-test"
  export SENDGRID_BASE_URL="$MOCK_SINK_BASE_URL"
  export NOTIFICATION_EMAIL_FROM="noreply@nexra.local"
  export ANOMALY_SLACK_WEBHOOK_URL="$MOCK_SINK_BASE_URL/mock/slack"
  export PAGERDUTY_EVENTS_BASE_URL="$MOCK_SINK_BASE_URL/mock/pagerduty"
  export ANOMALY_PAGERDUTY_ROUTING_KEY="local-routing-key"
  export ANOMALY_EMAIL_RECIPIENTS="admin@nexra.local"

  "$ROOT_DIR/scripts/start_live_stack.sh" \
    --base-url "$BASE_URL" \
    --state-file "$STACK_STATE_FILE" \
    --log-file "$STACK_LOG_FILE"
else
  echo "Attach mode selected: expecting stack already running at $BASE_URL"
fi

SUITE_CMD=(
  "$ROOT_DIR/nexra/venv/bin/python"
  "$ROOT_DIR/scripts/live_demo_full_suite.py"
  --base-url "$BASE_URL"
  --owner-email "admin@nexra.local"
  --results-dir "$RESULTS_DIR"
  --mock-sink-base-url "$MOCK_SINK_BASE_URL"
)

if [[ "$STRICT" == "1" ]]; then
  SUITE_CMD+=(--strict)
fi

if [[ "${NEXRA_ENABLE_STRIPE_ONBOARD_TEST:-0}" == "1" ]]; then
  SUITE_CMD+=(--enable-stripe-onboard)
fi

echo "Running full live demo suite"
set +e
"${SUITE_CMD[@]}"
SUITE_EXIT=$?
set -e

echo "Suite exit code: $SUITE_EXIT"
echo "Summary: $RESULTS_DIR/summary.json"
echo "Report:  $RESULTS_DIR/report.txt"

echo "$SUITE_EXIT" > "$RESULTS_DIR/exit_code.txt"
exit "$SUITE_EXIT"
