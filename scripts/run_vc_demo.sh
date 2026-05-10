#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MODE="attach"
PROFILE="vc-12m"
INTEGRATIONS="mock"
FAILURE_POLICY="fail-fast"
BASE_URL="http://127.0.0.1:8000"
DASHBOARD_URL="http://127.0.0.1:5173"
RESULTS_DIR="$ROOT_DIR/test-results/vc-demo/$(date +%Y%m%d-%H%M%S)"
STRICT=0
HEADED=0
if [[ -t 1 ]]; then
  OPEN_DASHBOARD="${NEXRA_OPEN_DASHBOARD:-1}"
else
  OPEN_DASHBOARD="${NEXRA_OPEN_DASHBOARD:-0}"
fi
CHECKPOINT_MIN_COVERAGE="${NEXRA_CHECKPOINT_MIN_COVERAGE:-1.0}"

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

ensure_real_env_contract() {
  python3 - <<'PY' "$ROOT_DIR"
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
env_files = [
    root / ".env",
    root / ".env.local",
    root / "nexra" / ".env",
    root / "nexra" / ".env.local",
]

for env_path in env_files:
    if not env_path.exists():
        continue
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        if not key:
            continue
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))

required = [
    "SENDGRID_API_KEY",
    "ANOMALY_PAGERDUTY_ROUTING_KEY",
    "PAGERDUTY_EVENTS_BASE_URL",
]
missing = [key for key in required if not os.getenv(key, "").strip()]
if missing:
    print(
        "[runner] real integrations contract missing required env vars: "
        + ", ".join(missing)
    )
    raise SystemExit(1)
PY
}

if [[ "$INTEGRATIONS" == "real" ]]; then
  if ! ensure_real_env_contract; then
    echo "[runner] refusing to continue in --integrations real without full env contract." >&2
    exit 1
  fi
fi

mkdir -p "$RESULTS_DIR"

echo "VC demo results: $RESULTS_DIR"

echo "Mode: $MODE | Integrations: $INTEGRATIONS | Failure policy: $FAILURE_POLICY"

STACK_STATE_FILE="$RESULTS_DIR/live-stack-state.json"
STACK_LOG_FILE="$RESULTS_DIR/live-stack.log"
MOCK_SINK_LOG="$RESULTS_DIR/mock-sink.log"
DASHBOARD_LOG="$RESULTS_DIR/dashboard.log"
AUTOPLAY_DEPS_LOG="$RESULTS_DIR/autoplay-deps.log"
PHASE_STATUS_FILE="$RESULTS_DIR/phase_status.json"
EXIT_CODE_FILE="$RESULTS_DIR/exit_code.txt"
EVENTS_FILE="$RESULTS_DIR/integration_events.jsonl"
PREFLIGHT_OUT="$RESULTS_DIR/preflight.json"
CHECKPOINT_SUMMARY_FILE="$RESULTS_DIR/checkpoint_summary.json"
POLICY_FLIP_FILE="$RESULTS_DIR/prd_policy_flip.json"
GO_NO_GO_FILE="$RESULTS_DIR/go_no_go.json"

MOCK_SINK_PORT="${NEXRA_MOCK_SINK_PORT:-8800}"
MOCK_SINK_BASE_URL="http://127.0.0.1:${MOCK_SINK_PORT}"
INTERNAL_DASHBOARD_DIR="$ROOT_DIR/nexra/internal-dashboard"

BOOTSTRAPPED=0
MOCK_SINK_PID=""
DASHBOARD_PID=""
FINAL_EXIT_CODE=""
INTERRUPTED=0

python3 - <<'PY' "$PHASE_STATUS_FILE" "$BASE_URL" "$DASHBOARD_URL" "$MODE" "$PROFILE" "$INTEGRATIONS" "$FAILURE_POLICY"
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "base_url": sys.argv[2],
    "dashboard_url": sys.argv[3],
    "mode": sys.argv[4],
    "profile": sys.argv[5],
    "integrations": sys.argv[6],
    "failure_policy": sys.argv[7],
    "phases": {},
}
path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
PY

: > "$EVENTS_FILE"

update_phase() {
  local phase="$1"
  local status="$2"
  local details="${3:-}"

  python3 - <<'PY' "$PHASE_STATUS_FILE" "$phase" "$status" "$details"
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
phase = sys.argv[2]
status = sys.argv[3]
details = sys.argv[4]
obj = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"phases": {}}
phases = obj.setdefault("phases", {})
entry = phases.get(phase, {})
entry["status"] = status
entry["updated_at"] = datetime.now(timezone.utc).isoformat()
if details:
  entry["details"] = details
phases[phase] = entry
path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")
PY
}

emit_event() {
  local event_name="$1"
  local extra_json="${2:-{}}"

  python3 - <<'PY' "$EVENTS_FILE" "$event_name" "$extra_json"
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
event = sys.argv[2]
extra_raw = sys.argv[3]
try:
    extra = json.loads(extra_raw) if extra_raw else {}
except json.JSONDecodeError:
    extra = {"details": extra_raw}

payload = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event}
if isinstance(extra, dict):
    payload.update(extra)
else:
    payload["details"] = extra

with path.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(payload, sort_keys=True))
    fh.write("\n")
PY
}

wait_for_http_ok() {
  local url="$1"
  local timeout_s="${2:-60}"
  local started
  started="$(date +%s)"

  while true; do
    if curl -sf "$url" >/dev/null 2>&1; then
      return 0
    fi
    if (( $(date +%s) - started > timeout_s )); then
      return 1
    fi
    sleep 1
  done
}

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

build_dashboard_session_url() {
  local base_url="$1"
  local api_key="$2"
  local user_email="$3"
  python3 - <<'PY' "$base_url" "$api_key" "$user_email"
import sys
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

base_url, api_key, user_email = sys.argv[1], sys.argv[2], sys.argv[3]
parsed = urlparse(base_url)
pairs = [
    (key, value)
    for key, value in parse_qsl(parsed.query, keep_blank_values=True)
    if key not in {"nexra_api_key", "api_key", "nexra_user_email", "user_email"}
]
pairs.append(("nexra_api_key", api_key))
pairs.append(("nexra_user_email", user_email))
query = urlencode(pairs)
print(urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment)))
PY
}

cleanup_processes() {
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

finalize() {
  local trap_exit="$?"
  local rc="$trap_exit"

  if [[ -n "$FINAL_EXIT_CODE" ]]; then
    rc="$FINAL_EXIT_CODE"
  fi
  if [[ "$INTERRUPTED" == "1" ]]; then
    rc=130
  fi

  echo "$rc" > "$EXIT_CODE_FILE"

  if [[ "$rc" == "0" ]]; then
    update_phase "terminal" "passed" "exit_code=$rc"
    emit_event "vc_bundle_written"
  else
    update_phase "terminal" "failed" "exit_code=$rc"
  fi

  cleanup_processes

  echo "Exit code:          $rc"
  echo "Phase status:       $PHASE_STATUS_FILE"
  echo "Integration events: $EVENTS_FILE"
  echo "Exit artifact:      $EXIT_CODE_FILE"
}

trap finalize EXIT
trap 'INTERRUPTED=1; FINAL_EXIT_CODE=130; exit 130' INT TERM

update_phase "runner" "in_progress" "bootstrapping vc runner"
emit_event "vc_runner_started" "{\"mode\": \"$MODE\", \"integrations\": \"$INTEGRATIONS\"}"

# Start sink for webhook/email/slack/pagerduty/siem captures.
update_phase "mock_sink" "in_progress" "starting local mock sink"
python3 "$ROOT_DIR/scripts/live_demo_mock_sink.py" \
  --port "$MOCK_SINK_PORT" \
  --out-dir "$RESULTS_DIR" >"$MOCK_SINK_LOG" 2>&1 &
MOCK_SINK_PID=$!

if ! wait_for_http_ok "$MOCK_SINK_BASE_URL/_health" 30; then
  update_phase "mock_sink" "failed" "mock sink failed to start (log: $MOCK_SINK_LOG)"
  echo "Mock sink failed to start. Check log: $MOCK_SINK_LOG" >&2
  FINAL_EXIT_CODE=1
  exit 1
fi
update_phase "mock_sink" "passed" "mock sink ready at $MOCK_SINK_BASE_URL"

export NEXRA_MOCK_SINK_BASE_URL="$MOCK_SINK_BASE_URL"
export NEXRA_INTEGRATIONS_MODE="$INTEGRATIONS"

update_phase "stack" "in_progress" "mode=$MODE"
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

  if ! "$ROOT_DIR/scripts/start_live_stack.sh" \
    --base-url "$BASE_URL" \
    --state-file "$STACK_STATE_FILE" \
    --log-file "$STACK_LOG_FILE"; then
    update_phase "stack" "failed" "start_live_stack failed (log: $STACK_LOG_FILE)"
    echo "Live stack bootstrap failed. Check: $STACK_LOG_FILE" >&2
    FINAL_EXIT_CODE=1
    exit 1
  fi

  if [[ ! -f "$STACK_STATE_FILE" ]]; then
    update_phase "stack" "failed" "state file missing after bootstrap"
    echo "Expected stack state file not found: $STACK_STATE_FILE" >&2
    FINAL_EXIT_CODE=1
    exit 1
  fi

  if ! wait_for_http_ok "$BASE_URL/health" 30; then
    update_phase "stack" "failed" "api not healthy at $BASE_URL/health"
    echo "API failed readiness check in bootstrap mode: $BASE_URL/health" >&2
    echo "Inspect stack log: $STACK_LOG_FILE" >&2
    FINAL_EXIT_CODE=1
    exit 1
  fi

  (
    cd "$ROOT_DIR/nexra/internal-dashboard"
    npm run dev
  ) >"$DASHBOARD_LOG" 2>&1 &
  DASHBOARD_PID=$!

  if ! wait_for_http_ok "$DASHBOARD_URL" 90; then
    ALT_DASHBOARD_URL="$(alternate_loopback_url "$DASHBOARD_URL")"
    if [[ -n "$ALT_DASHBOARD_URL" ]] && wait_for_http_ok "$ALT_DASHBOARD_URL" 8; then
      DASHBOARD_URL="$ALT_DASHBOARD_URL"
      echo "[info] dashboard reachable via alternate loopback URL: $DASHBOARD_URL"
    else
      update_phase "stack" "failed" "dashboard failed readiness in bootstrap mode"
      echo "Dashboard failed readiness in bootstrap mode: $DASHBOARD_URL" >&2
      echo "Inspect dashboard log: $DASHBOARD_LOG" >&2
      FINAL_EXIT_CODE=1
      exit 1
    fi
  fi

  if [[ "$OPEN_DASHBOARD" == "1" ]]; then
    if open_dashboard_url "$DASHBOARD_URL"; then
      echo "[info] opened dashboard in browser: $DASHBOARD_URL"
    else
      echo "[warn] could not auto-open dashboard; open manually: $DASHBOARD_URL" >&2
    fi
  else
    echo "[info] dashboard auto-open disabled; use --open-dashboard (or NEXRA_OPEN_DASHBOARD=1)"
  fi
else
  echo "Attach mode: validating stack at $BASE_URL and dashboard at $DASHBOARD_URL"
  if ! wait_for_http_ok "$BASE_URL/health" 15; then
    update_phase "stack" "failed" "attach mode api health failed"
    echo "Attach mode failed: API is not reachable at $BASE_URL/health" >&2
    echo "Start stack with: ./scripts/run_vc_demo.sh --mode bootstrap" >&2
    FINAL_EXIT_CODE=1
    exit 1
  fi

  if ! wait_for_http_ok "$DASHBOARD_URL" 15; then
    ALT_DASHBOARD_URL="$(alternate_loopback_url "$DASHBOARD_URL")"
    if [[ -n "$ALT_DASHBOARD_URL" ]] && wait_for_http_ok "$ALT_DASHBOARD_URL" 8; then
      DASHBOARD_URL="$ALT_DASHBOARD_URL"
      echo "[info] dashboard reachable via alternate loopback URL: $DASHBOARD_URL"
    else
      update_phase "stack" "failed" "attach mode dashboard readiness failed"
      echo "Attach mode failed: dashboard not reachable at $DASHBOARD_URL" >&2
      echo "Either run bootstrap mode or start dashboard manually (cd nexra/internal-dashboard && npm run dev)." >&2
      FINAL_EXIT_CODE=1
      exit 1
    fi
  fi
fi
update_phase "stack" "passed" "api+dashboard ready"

update_phase "preflight" "in_progress" "running vc_demo_preflight.py"
PREFLIGHT_CMD=(
  "$ROOT_DIR/nexra/venv/bin/python"
  "$ROOT_DIR/scripts/vc_demo_preflight.py"
  --base-url "$BASE_URL"
  --integrations "$INTEGRATIONS"
  --failure-policy "$FAILURE_POLICY"
  --mock-sink-base-url "$MOCK_SINK_BASE_URL"
  --results-dir "$RESULTS_DIR"
)
set +e
"${PREFLIGHT_CMD[@]}"
PREFLIGHT_EXIT=$?
set -e
if [[ "$PREFLIGHT_EXIT" -ne 0 ]]; then
  update_phase "preflight" "failed" "preflight exit=$PREFLIGHT_EXIT"
  FINAL_EXIT_CODE="$PREFLIGHT_EXIT"
  exit "$PREFLIGHT_EXIT"
fi
update_phase "preflight" "passed" "preflight completed"
emit_event "preflight_passed"

update_phase "seed" "in_progress" "running vc_seed_enterprise_data.py"
SEED_CMD=(
  "$ROOT_DIR/nexra/venv/bin/python"
  "$ROOT_DIR/scripts/vc_seed_enterprise_data.py"
  --base-url "$BASE_URL"
  --results-dir "$RESULTS_DIR"
)
if [[ "$PROFILE" == "full" ]]; then
  SEED_CMD+=(--days 30 --seed-per-day 20)
fi
set +e
"${SEED_CMD[@]}"
SEED_EXIT=$?
set -e
if [[ "$SEED_EXIT" -ne 0 ]]; then
  update_phase "seed" "failed" "seed exit=$SEED_EXIT"
  FINAL_EXIT_CODE="$SEED_EXIT"
  exit "$SEED_EXIT"
fi
update_phase "seed" "passed" "seed completed"

ORG_PROFILE="$RESULTS_DIR/vc_org_profile.json"
if [[ ! -f "$ORG_PROFILE" ]]; then
  update_phase "seed" "failed" "missing org profile artifact"
  echo "Missing org profile after seeding: $ORG_PROFILE" >&2
  FINAL_EXIT_CODE=1
  exit 1
fi

SEED_HISTORY_JSON="$(python3 - <<'PY' "$ORG_PROFILE"
import json
import sys
obj = json.load(open(sys.argv[1], 'r', encoding='utf-8'))
h = obj.get('history') or {}
print(json.dumps({
  'inserted_delegations': h.get('inserted_delegations', 0),
  'inserted_audit_events': h.get('inserted_audit_events', 0),
}))
PY
)"
emit_event "seeded_data_loaded" "$SEED_HISTORY_JSON"

BUYER_API_KEY="$(python3 - <<'PY' "$ORG_PROFILE"
import json, sys
obj = json.load(open(sys.argv[1], 'r', encoding='utf-8'))
print((((obj.get('orgs') or {}).get('buyer') or {}).get('api_key')) or '')
PY
)"

BUYER_USER_EMAIL="$(python3 - <<'PY' "$ORG_PROFILE"
import json, sys
obj = json.load(open(sys.argv[1], 'r', encoding='utf-8'))
print((((obj.get('orgs') or {}).get('buyer') or {}).get('owner_email')) or '')
PY
)"
if [[ -z "$BUYER_USER_EMAIL" ]]; then
  BUYER_USER_EMAIL="admin@nexra.local"
fi

if [[ -n "$BUYER_API_KEY" ]]; then
  DASHBOARD_SESSION_URL="$(build_dashboard_session_url "$DASHBOARD_URL" "$BUYER_API_KEY" "$BUYER_USER_EMAIL")"
  emit_event "dashboard_session_synced"
  echo "[info] dashboard session URL: $DASHBOARD_SESSION_URL"
  if [[ "$OPEN_DASHBOARD" == "1" ]]; then
    if open_dashboard_url "$DASHBOARD_SESSION_URL"; then
      echo "[info] reopened dashboard with seeded buyer session."
    else
      echo "[warn] could not auto-open seeded dashboard session; open manually: $DASHBOARD_SESSION_URL" >&2
    fi
  else
    echo "[info] dashboard auto-open disabled; use this URL to sync your browser session:"
    echo "       $DASHBOARD_SESSION_URL"
  fi
fi

update_phase "suite" "in_progress" "running vc_demo_suite.py"
echo "[info] running vc_demo_suite.py (this may take a few minutes)"
echo "[info] baseline suite log: $RESULTS_DIR/baseline_run.log"
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
if [[ "$SUITE_EXIT" -ne 0 ]]; then
  update_phase "suite" "failed" "vc_demo_suite exit=$SUITE_EXIT"
else
  update_phase "suite" "passed" "vc_demo_suite passed"
fi

SUMMARY_PATH="$RESULTS_DIR/summary.json"
CAP_MATRIX_RESULT="$RESULTS_DIR/capability_matrix_result.json"
REPORT_PATH="$RESULTS_DIR/report.md"

if [[ -f "$SUMMARY_PATH" ]]; then
  python3 - <<'PY' "$SUMMARY_PATH" "$EVENTS_FILE"
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

summary = json.load(open(sys.argv[1], 'r', encoding='utf-8'))
out = Path(sys.argv[2])
scenarios = summary.get('scenario_results') or {}
for scenario_id, passed in scenarios.items():
    if passed is not True:
        continue
    event = f"{scenario_id}_passed"
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "scenario_id": scenario_id,
    }
    with out.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(payload, sort_keys=True))
        fh.write("\n")
PY
fi

if [[ -f "$CAP_MATRIX_RESULT" ]]; then
  REQUIRED_FAILED="$(python3 - <<'PY' "$CAP_MATRIX_RESULT"
import json, sys
obj = json.load(open(sys.argv[1], 'r', encoding='utf-8'))
print(int(obj.get('required_failed', 9999)))
PY
)"
  if [[ "$REQUIRED_FAILED" == "0" ]]; then
    emit_event "capability_matrix_passed"
  fi
fi

update_phase "prd_policy_flip" "in_progress" "running policy flip check"
POLICY_CMD=(
  "$ROOT_DIR/nexra/venv/bin/python"
  "$ROOT_DIR/scripts/vc_prd_policy_flip_check.py"
  --base-url "$BASE_URL"
  --org-profile "$ORG_PROFILE"
  --out "$POLICY_FLIP_FILE"
)
set +e
"${POLICY_CMD[@]}"
POLICY_EXIT=$?
set -e
if [[ "$POLICY_EXIT" -ne 0 ]]; then
  update_phase "prd_policy_flip" "failed" "policy flip check exit=$POLICY_EXIT"
else
  update_phase "prd_policy_flip" "passed" "policy flip check passed"
  emit_event "prd_policy_flip_passed"
fi

python3 - <<'PY' "$REPORT_PATH" "$POLICY_FLIP_FILE"
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
policy_path = Path(sys.argv[2])
if not report_path.exists() or not policy_path.exists():
    raise SystemExit(0)

report = report_path.read_text(encoding='utf-8').rstrip() + "\n\n## PRD 90s Policy Flip\n"
policy = json.load(policy_path.open('r', encoding='utf-8'))
status = "PASS" if policy.get('passed') else "FAIL"
report += f"- Status: {status}\n"
report += f"- Allow Status Code: {policy.get('allow_status_code')}\n"
report += f"- Block Status Code: {policy.get('block_status_code')}\n"
report += f"- Block Error Code: {policy.get('block_error_code')}\n"
report += f"- Flip Duration Seconds: {policy.get('flip_duration_seconds')}\n"
report_path.write_text(report + "\n", encoding='utf-8')
PY

if [[ "$SUITE_EXIT" -eq 0 && "$POLICY_EXIT" -eq 0 && -f "$SUMMARY_PATH" && -f "$REPORT_PATH" ]]; then
  emit_event "vc_bundle_written" '{"phase":"pre_autoplay","status":"prepared"}'
fi

AUTOPLAY_EXIT=0
update_phase "autoplay" "in_progress" "running dashboard autoplay"
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
      update_phase "autoplay" "failed" "playwright install failed in strict mode"
      AUTOPLAY_EXIT=1
    fi
  fi

  if [[ "$AUTOPLAY_EXIT" -eq 0 ]]; then
    AUTOPLAY_CMD=(
      env
      "NEXRA_DASHBOARD_DIR=$INTERNAL_DASHBOARD_DIR"
      "$INTERNAL_DASHBOARD_DIR/node_modules/.bin/tsx"
      "$ROOT_DIR/scripts/vc_dashboard_autoplay.ts"
      --base-url "$DASHBOARD_URL"
      --api-key "$BUYER_API_KEY"
      --user-email "$BUYER_USER_EMAIL"
      --timeline "$ROOT_DIR/demo/vc_timeline.yaml"
      --events-path "$EVENTS_FILE"
      --out-dir "$RESULTS_DIR/screenshots"
      --summary-path "$CHECKPOINT_SUMMARY_FILE"
      --min-checkpoint-coverage "$CHECKPOINT_MIN_COVERAGE"
    )
    if [[ "$HEADED" == "1" ]]; then
      AUTOPLAY_CMD+=(--headed)
    fi
    if [[ "$STRICT" == "1" ]]; then
      AUTOPLAY_CMD+=(--strict-checkpoints)
    fi

    set +e
    "${AUTOPLAY_CMD[@]}"
    AUTOPLAY_EXIT=$?
    set -e

    if [[ "$AUTOPLAY_EXIT" -eq 0 ]]; then
      update_phase "autoplay" "passed" "autoplay completed"
    else
      update_phase "autoplay" "failed" "autoplay exit=$AUTOPLAY_EXIT"
      echo "[warn] dashboard autoplay failed; see artifacts in $RESULTS_DIR" >&2
    fi
  fi
else
  update_phase "autoplay" "failed" "buyer api key missing; skipped autoplay"
  AUTOPLAY_EXIT=1
fi

if [[ -f "$CHECKPOINT_SUMMARY_FILE" ]]; then
  python3 - <<'PY' "$CHECKPOINT_SUMMARY_FILE" "$REPORT_PATH"
import json
import sys
from pathlib import Path

summary = json.load(open(sys.argv[1], 'r', encoding='utf-8'))
report_path = Path(sys.argv[2])
if not report_path.exists():
    raise SystemExit(0)

report = report_path.read_text(encoding='utf-8').rstrip()
report += "\n\n## Timeline Checkpoints\n"
report += f"- Seen: {summary.get('checkpoints_seen')}/{summary.get('checkpoints_total')}\n"
report += f"- Coverage: {summary.get('coverage_ratio')}\n"
report += f"- Min Required: {summary.get('min_required_coverage')}\n"
report += f"- Strict Gate: {'PASS' if summary.get('strict_gate_passed') else 'FAIL'}\n"
report_path.write_text(report + "\n", encoding='utf-8')
PY
else
  if [[ "$STRICT" == "1" ]]; then
    echo "[warn] checkpoint summary missing in strict mode" >&2
    AUTOPLAY_EXIT=1
  fi
fi

OVERALL_EXIT=0
if [[ "$SUITE_EXIT" -ne 0 ]]; then
  OVERALL_EXIT="$SUITE_EXIT"
fi
if [[ "$POLICY_EXIT" -ne 0 && "$OVERALL_EXIT" -eq 0 ]]; then
  OVERALL_EXIT="$POLICY_EXIT"
fi
if [[ "$STRICT" == "1" && "$AUTOPLAY_EXIT" -ne 0 && "$OVERALL_EXIT" -eq 0 ]]; then
  OVERALL_EXIT=1
fi

update_phase "runner" "$([[ "$OVERALL_EXIT" -eq 0 ]] && echo passed || echo failed)" "suite_exit=$SUITE_EXIT autoplay_exit=$AUTOPLAY_EXIT policy_exit=$POLICY_EXIT"

python3 - <<'PY' \
"$GO_NO_GO_FILE" \
"$PREFLIGHT_OUT" \
"$SUMMARY_PATH" \
"$CAP_MATRIX_RESULT" \
"$CHECKPOINT_SUMMARY_FILE" \
"$POLICY_FLIP_FILE" \
"$PHASE_STATUS_FILE" \
"$OVERALL_EXIT" \
"$SUITE_EXIT" \
"$POLICY_EXIT" \
"$AUTOPLAY_EXIT" \
"$STRICT" \
"$FAILURE_POLICY" \
"$INTEGRATIONS" \
"$MODE" \
"$PROFILE"
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

(
    out_path,
    preflight_path,
    suite_summary_path,
    capability_path,
    checkpoint_path,
    policy_path,
    phase_path,
    overall_exit,
    suite_exit,
    policy_exit,
    autoplay_exit,
    strict_mode,
    failure_policy,
    integrations,
    mode,
    profile,
) = sys.argv[1:]

def _read_json(path: str) -> dict:
    file = Path(path)
    if not file.exists():
        return {}
    try:
        return json.loads(file.read_text(encoding="utf-8"))
    except Exception:
        return {}

preflight = _read_json(preflight_path)
suite_summary = _read_json(suite_summary_path)
capability = _read_json(capability_path)
checkpoint = _read_json(checkpoint_path)
policy = _read_json(policy_path)
phase = _read_json(phase_path)

required_failed = int(capability.get("required_failed", 9999)) if capability else 9999
preflight_required_failed = int(preflight.get("required_failed", 9999)) if preflight else 9999
checkpoints_ok = bool(checkpoint.get("strict_gate_passed")) if checkpoint else False
policy_ok = bool(policy.get("passed")) if policy else False
suite_ok = bool(suite_summary) and int(suite_exit) == 0
strict_enabled = int(strict_mode) == 1

reasons: list[str] = []
if int(overall_exit) != 0:
    reasons.append(f"overall_exit={overall_exit}")
if preflight_required_failed != 0:
    reasons.append(f"preflight.required_failed={preflight_required_failed}")
if required_failed != 0:
    reasons.append(f"capability.required_failed={required_failed}")
if not policy_ok:
    reasons.append("prd_policy_flip_failed")
if strict_enabled and not checkpoints_ok:
    reasons.append("checkpoint_strict_gate_failed")
if strict_enabled and int(autoplay_exit) != 0:
    reasons.append(f"autoplay_exit={autoplay_exit}")
if not suite_ok:
    reasons.append(f"suite_exit={suite_exit}")
if int(policy_exit) != 0:
    reasons.append(f"policy_exit={policy_exit}")

status = "go" if not reasons else "no-go"
payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "status": status,
    "mode": mode,
    "profile": profile,
    "integrations": integrations,
    "failure_policy": failure_policy,
    "strict": strict_enabled,
    "gates": {
        "preflight_required_failed": preflight_required_failed,
        "capability_required_failed": required_failed,
        "policy_flip_passed": policy_ok,
        "checkpoint_strict_gate_passed": checkpoints_ok if checkpoint else None,
        "suite_exit": int(suite_exit),
        "policy_exit": int(policy_exit),
        "autoplay_exit": int(autoplay_exit),
        "overall_exit": int(overall_exit),
    },
    "artifacts": {
        "preflight": preflight_path,
        "suite_summary": suite_summary_path,
        "capability_matrix_result": capability_path,
        "checkpoint_summary": checkpoint_path,
        "policy_flip": policy_path,
        "phase_status": phase_path,
    },
    "reasons": reasons,
    "phase_snapshot": phase.get("phases", {}),
}

Path(out_path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
print(json.dumps({"go_no_go": status, "reasons": reasons, "artifact": out_path}, indent=2, sort_keys=True))
PY
emit_event "go_no_go_written" "{\"status\": \"$(python3 - <<'PY' "$GO_NO_GO_FILE"
import json, sys
obj = json.load(open(sys.argv[1], 'r', encoding='utf-8'))
print(obj.get('status', 'unknown'))
PY
)\"}"

echo "VC suite exit code: $SUITE_EXIT"
echo "Policy flip exit:   $POLICY_EXIT"
echo "Autoplay exit:      $AUTOPLAY_EXIT"
echo "Summary:            $SUMMARY_PATH"
echo "Capability result:  $CAP_MATRIX_RESULT"
echo "Report:             $REPORT_PATH"
echo "Go/No-Go:           $GO_NO_GO_FILE"

FINAL_EXIT_CODE="$OVERALL_EXIT"
exit "$OVERALL_EXIT"
