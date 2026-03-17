#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MODE="attach"
PROFILE="vc-12m"
INTEGRATIONS="real"
FAILURE_POLICY="fail-fast"
BASE_URL="http://127.0.0.1:8000"
DASHBOARD_URL="http://127.0.0.1:5173"
RESULTS_DIR="$ROOT_DIR/test-results/vc-demo/$(date +%Y%m%d-%H%M%S)"
STRICT=0
HEADED=0
OPEN_DASHBOARD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --profile)
      PROFILE="$2"
      shift 2
      ;;
    --integrations)
      INTEGRATIONS="$2"
      shift 2
      ;;
    --failure-policy)
      FAILURE_POLICY="$2"
      shift 2
      ;;
    --base-url)
      BASE_URL="$2"
      shift 2
      ;;
    --dashboard-url)
      DASHBOARD_URL="$2"
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
    --headed)
      HEADED=1
      shift
      ;;
    --open-dashboard)
      OPEN_DASHBOARD=1
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
if [[ "$PROFILE" != "vc-12m" && "$PROFILE" != "full" ]]; then
  echo "--profile must be vc-12m or full" >&2
  exit 1
fi
if [[ "$INTEGRATIONS" != "real" && "$INTEGRATIONS" != "hybrid" && "$INTEGRATIONS" != "mock" ]]; then
  echo "--integrations must be real, hybrid, or mock" >&2
  exit 1
fi
if [[ "$FAILURE_POLICY" != "fail-fast" && "$FAILURE_POLICY" != "fallback" && "$FAILURE_POLICY" != "skip" ]]; then
  echo "--failure-policy must be fail-fast, fallback, or skip" >&2
  exit 1
fi

mkdir -p "$RESULTS_DIR"

echo "VC demo results: $RESULTS_DIR"

STACK_STATE_FILE="$RESULTS_DIR/live-stack-state.json"
STACK_LOG_FILE="$RESULTS_DIR/live-stack.log"
MOCK_SINK_LOG="$RESULTS_DIR/mock-sink.log"
DASHBOARD_LOG="$RESULTS_DIR/dashboard.log"
AUTOPLAY_DEPS_LOG="$RESULTS_DIR/autoplay-deps.log"
MOCK_SINK_PORT="${NEXRA_MOCK_SINK_PORT:-8800}"
MOCK_SINK_BASE_URL="http://127.0.0.1:${MOCK_SINK_PORT}"
INTERNAL_DASHBOARD_DIR="$ROOT_DIR/nexra/internal-dashboard"

BOOTSTRAPPED=0
MOCK_SINK_PID=""
DASHBOARD_PID=""

alternate_loopback_url() {
  local url="$1"
  if [[ "$url" == *"127.0.0.1"* ]]; then
    printf '%s\n' "${url/127.0.0.1/localhost}"
    return 0
  fi
  if [[ "$url" == *"localhost"* ]]; then
    printf '%s\n' "${url/localhost/127.0.0.1}"
    return 0
  fi
  printf '\n'
}

open_dashboard_url() {
  local url="$1"
  if command -v open >/dev/null 2>&1; then
    open "$url" >/dev/null 2>&1 || true
    return 0
  fi
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 || true
    return 0
  fi
  if command -v start >/dev/null 2>&1; then
    start "$url" >/dev/null 2>&1 || true
    return 0
  fi
  return 1
}

cleanup() {
  if [[ -n "$DASHBOARD_PID" ]] && kill -0 "$DASHBOARD_PID" >/dev/null 2>&1; then
    kill "$DASHBOARD_PID" >/dev/null 2>&1 || true
    wait "$DASHBOARD_PID" 2>/dev/null || true
  fi

  if [[ "$BOOTSTRAPPED" == "1" ]]; then
    "$ROOT_DIR/scripts/stop_live_stack.sh" --state-file "$STACK_STATE_FILE" >/dev/null 2>&1 || true
  fi

  if [[ -n "$MOCK_SINK_PID" ]] && kill -0 "$MOCK_SINK_PID" >/dev/null 2>&1; then
    kill "$MOCK_SINK_PID" >/dev/null 2>&1 || true
    wait "$MOCK_SINK_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# Start sink for webhook/email/slack/pagerduty/siem captures.
python3 "$ROOT_DIR/scripts/live_demo_mock_sink.py" \
  --port "$MOCK_SINK_PORT" \
  --out-dir "$RESULTS_DIR" >"$MOCK_SINK_LOG" 2>&1 &
MOCK_SINK_PID=$!

for _ in {1..30}; do
  if curl -sf "$MOCK_SINK_BASE_URL/_health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! curl -sf "$MOCK_SINK_BASE_URL/_health" >/dev/null 2>&1; then
  echo "Mock sink failed to start. Log: $MOCK_SINK_LOG" >&2
  exit 1
fi

export NEXRA_MOCK_SINK_BASE_URL="$MOCK_SINK_BASE_URL"

if [[ "$MODE" == "bootstrap" ]]; then
  BOOTSTRAPPED=1
  export NEXRA_SKIP_NGROK=1
  export NEXRA_SKIP_DEMO_AGENTS=1
  export NEXRA_SKIP_DASHBOARD=1

  if [[ "$INTEGRATIONS" != "real" ]]; then
    export SENDGRID_API_KEY="${SENDGRID_API_KEY:-sg-local-test}"
    export SENDGRID_BASE_URL="${SENDGRID_BASE_URL:-$MOCK_SINK_BASE_URL}"
    export NOTIFICATION_EMAIL_FROM="${NOTIFICATION_EMAIL_FROM:-noreply@nexra.local}"
    export ANOMALY_SLACK_WEBHOOK_URL="${ANOMALY_SLACK_WEBHOOK_URL:-$MOCK_SINK_BASE_URL/mock/slack}"
    export PAGERDUTY_EVENTS_BASE_URL="${PAGERDUTY_EVENTS_BASE_URL:-$MOCK_SINK_BASE_URL/mock/pagerduty}"
    export ANOMALY_PAGERDUTY_ROUTING_KEY="${ANOMALY_PAGERDUTY_ROUTING_KEY:-local-routing-key}"
    export ANOMALY_EMAIL_RECIPIENTS="${ANOMALY_EMAIL_RECIPIENTS:-admin@nexra.local}"
  fi

  "$ROOT_DIR/scripts/start_live_stack.sh" \
    --base-url "$BASE_URL" \
    --state-file "$STACK_STATE_FILE" \
    --log-file "$STACK_LOG_FILE"

  (
    cd "$ROOT_DIR/nexra/internal-dashboard"
    npm run dev
  ) >"$DASHBOARD_LOG" 2>&1 &
  DASHBOARD_PID=$!

  for _ in {1..90}; do
    if curl -sf "$DASHBOARD_URL" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  if ! curl -sf "$DASHBOARD_URL" >/dev/null 2>&1; then
    ALT_DASHBOARD_URL="$(alternate_loopback_url "$DASHBOARD_URL")"
    if [[ -n "$ALT_DASHBOARD_URL" ]] && curl -sf "$ALT_DASHBOARD_URL" >/dev/null 2>&1; then
      DASHBOARD_URL="$ALT_DASHBOARD_URL"
      echo "[info] dashboard reachable via alternate loopback URL: $DASHBOARD_URL"
    else
      echo "Dashboard failed to start in bootstrap mode. Log: $DASHBOARD_LOG" >&2
      exit 1
    fi
  fi

  if [[ "$OPEN_DASHBOARD" == "1" ]]; then
    if open_dashboard_url "$DASHBOARD_URL"; then
      echo "[info] opened dashboard in browser: $DASHBOARD_URL"
    else
      echo "[warn] could not auto-open dashboard; open manually: $DASHBOARD_URL" >&2
    fi
  fi
else
  echo "Attach mode: expecting stack at $BASE_URL and dashboard at $DASHBOARD_URL"
fi

PREFLIGHT_CMD=(
  "$ROOT_DIR/nexra/venv/bin/python"
  "$ROOT_DIR/scripts/vc_demo_preflight.py"
  --base-url "$BASE_URL"
  --integrations "$INTEGRATIONS"
  --failure-policy "$FAILURE_POLICY"
  --mock-sink-base-url "$MOCK_SINK_BASE_URL"
  --results-dir "$RESULTS_DIR"
)
"${PREFLIGHT_CMD[@]}"

SEED_CMD=(
  "$ROOT_DIR/nexra/venv/bin/python"
  "$ROOT_DIR/scripts/vc_seed_enterprise_data.py"
  --base-url "$BASE_URL"
  --results-dir "$RESULTS_DIR"
)
if [[ "$PROFILE" == "full" ]]; then
  SEED_CMD+=(--days 30 --seed-per-day 20)
fi
"${SEED_CMD[@]}"

ORG_PROFILE="$RESULTS_DIR/vc_org_profile.json"
if [[ ! -f "$ORG_PROFILE" ]]; then
  echo "Missing org profile after seeding: $ORG_PROFILE" >&2
  exit 1
fi

SUITE_CMD=(
  "$ROOT_DIR/nexra/venv/bin/python"
  "$ROOT_DIR/scripts/vc_demo_suite.py"
  --base-url "$BASE_URL"
  --dashboard-url "$DASHBOARD_URL"
  --org-profile "$ORG_PROFILE"
  --results-dir "$RESULTS_DIR"
  --capability-matrix "$ROOT_DIR/demo/prd_capability_matrix.yaml"
  --mock-sink-base-url "$MOCK_SINK_BASE_URL"
)
if [[ "$STRICT" == "1" ]]; then
  SUITE_CMD+=(--strict)
fi
if [[ "${NEXRA_ENABLE_STRIPE_ONBOARD_TEST:-0}" == "1" ]]; then
  SUITE_CMD+=(--enable-stripe-onboard)
fi

set +e
"${SUITE_CMD[@]}"
SUITE_EXIT=$?
set -e

BUYER_API_KEY="$(python3 - <<'PY' "$ORG_PROFILE"
import json, sys
obj = json.load(open(sys.argv[1], 'r', encoding='utf-8'))
print((((obj.get('orgs') or {}).get('buyer') or {}).get('api_key')) or '')
PY
)"

if [[ -n "$BUYER_API_KEY" ]]; then
  if [[ ! -x "$INTERNAL_DASHBOARD_DIR/node_modules/.bin/tsx" ]] || [[ ! -d "$INTERNAL_DASHBOARD_DIR/node_modules/playwright" ]] || [[ ! -d "$INTERNAL_DASHBOARD_DIR/node_modules/yaml" ]]; then
    echo "[info] installing dashboard autoplay dependencies (tsx, playwright, yaml)..."
    (
      cd "$INTERNAL_DASHBOARD_DIR"
      npm install --no-save tsx playwright yaml
    ) >"$AUTOPLAY_DEPS_LOG" 2>&1
  fi

  if ! (
    cd "$INTERNAL_DASHBOARD_DIR"
    npx --yes playwright install chromium
  ) >>"$AUTOPLAY_DEPS_LOG" 2>&1; then
    echo "[warn] playwright chromium install failed; see $AUTOPLAY_DEPS_LOG" >&2
    if [[ "$STRICT" == "1" ]]; then
      exit 1
    fi
  fi

  AUTOPLAY_CMD=(
    env
    "NEXRA_DASHBOARD_DIR=$INTERNAL_DASHBOARD_DIR"
    "$INTERNAL_DASHBOARD_DIR/node_modules/.bin/tsx"
    "$ROOT_DIR/scripts/vc_dashboard_autoplay.ts"
    --base-url "$DASHBOARD_URL"
    --api-key "$BUYER_API_KEY"
    --user-email "admin@nexra.local"
    --timeline "$ROOT_DIR/demo/vc_timeline.yaml"
    --events-path "$RESULTS_DIR/integration_events.jsonl"
    --out-dir "$RESULTS_DIR/screenshots"
  )
  if [[ "$HEADED" == "1" ]]; then
    AUTOPLAY_CMD+=(--headed)
  fi
  if ! "${AUTOPLAY_CMD[@]}"; then
    echo "[warn] dashboard autoplay failed; see logs/artifacts in $RESULTS_DIR" >&2
    if [[ "$STRICT" == "1" ]]; then
      exit 1
    fi
  fi
fi

echo "VC suite exit code: $SUITE_EXIT"
echo "Summary:            $RESULTS_DIR/summary.json"
echo "Capability result:  $RESULTS_DIR/capability_matrix_result.json"
echo "Report:             $RESULTS_DIR/report.md"
echo "$SUITE_EXIT" > "$RESULTS_DIR/exit_code.txt"

exit "$SUITE_EXIT"
