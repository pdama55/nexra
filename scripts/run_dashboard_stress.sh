#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MODE="bootstrap"
INTEGRATIONS="hybrid"
FAILURE_MODE="collect-all"
BASE_URL="http://127.0.0.1:8000"
DASHBOARD_URL="http://127.0.0.1:5173"
DURATION_MIN=90
PEAK_VUS=40
SWEEP_INTERVAL_SEC=120
ERROR_RATE_THRESHOLD="${NEXRA_STRESS_ERROR_RATE_THRESHOLD:-0.01}"
ROUTE_TIMEOUT_MS="${NEXRA_STRESS_ROUTE_TIMEOUT_MS:-15000}"
RESULTS_DIR="$ROOT_DIR/test-results/dashboard-stress/$(date +%Y%m%d-%H%M%S)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --integrations)
      INTEGRATIONS="$2"
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
    --duration-min)
      DURATION_MIN="$2"
      shift 2
      ;;
    --peak-vus)
      PEAK_VUS="$2"
      shift 2
      ;;
    --sweep-interval-sec)
      SWEEP_INTERVAL_SEC="$2"
      shift 2
      ;;
    --failure-mode)
      FAILURE_MODE="$2"
      shift 2
      ;;
    --results-dir)
      RESULTS_DIR="$2"
      shift 2
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
if [[ "$INTEGRATIONS" != "mock" && "$INTEGRATIONS" != "hybrid" && "$INTEGRATIONS" != "real" ]]; then
  echo "--integrations must be mock, hybrid, or real" >&2
  exit 1
fi
if [[ "$FAILURE_MODE" != "collect-all" && "$FAILURE_MODE" != "fail-fast" && "$FAILURE_MODE" != "warn-only-noncritical" ]]; then
  echo "--failure-mode must be collect-all, fail-fast, or warn-only-noncritical" >&2
  exit 1
fi

mkdir -p "$RESULTS_DIR"

echo "Dashboard stress results: $RESULTS_DIR"
echo "Mode: $MODE | Integrations: $INTEGRATIONS | Duration: ${DURATION_MIN}m | Peak VUs: $PEAK_VUS"

STACK_STATE_FILE="$RESULTS_DIR/live-stack-state.json"
STACK_LOG_FILE="$RESULTS_DIR/live-stack.log"
DASHBOARD_LOG_FILE="$RESULTS_DIR/dashboard.log"
MOCK_SINK_LOG="$RESULTS_DIR/mock-sink.log"
PREFLIGHT_OUT="$RESULTS_DIR/preflight.json"
ORG_PROFILE="$RESULTS_DIR/vc_org_profile.json"
VC_SUITE_DIR="$RESULTS_DIR/vc_suite"
STRESS_SUMMARY="$RESULTS_DIR/stress_summary.json"
STRESS_REPORT="$RESULTS_DIR/stress_report.md"

BOOTSTRAPPED=0
MOCK_SINK_STARTED=0
MOCK_SINK_PID=""
DASHBOARD_PID=""
LOAD_EXIT=0
PARITY_EXIT=0
SUITE_EXIT=0
FINAL_EXIT=0

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

MOCK_SINK_PORT="${NEXRA_MOCK_SINK_PORT:-8800}"
MOCK_SINK_BASE_URL="http://127.0.0.1:${MOCK_SINK_PORT}"

echo "[info] starting local mock sink: $MOCK_SINK_BASE_URL"
python3 "$ROOT_DIR/scripts/live_demo_mock_sink.py" \
  --port "$MOCK_SINK_PORT" \
  --out-dir "$RESULTS_DIR" >"$MOCK_SINK_LOG" 2>&1 &
MOCK_SINK_PID=$!
if ! wait_for_http_ok "$MOCK_SINK_BASE_URL/_health" 30; then
  echo "Mock sink failed to start. See $MOCK_SINK_LOG" >&2
  exit 1
fi
MOCK_SINK_STARTED=1
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
fi

if ! wait_for_http_ok "$BASE_URL/health" 30; then
  echo "API health check failed: $BASE_URL/health" >&2
  exit 1
fi

(
  cd "$ROOT_DIR/nexra/internal-dashboard"
  npm run dev
) >"$DASHBOARD_LOG_FILE" 2>&1 &
DASHBOARD_PID=$!

if ! wait_for_http_ok "$DASHBOARD_URL" 90; then
  ALT_DASHBOARD_URL="$(alternate_loopback_url "$DASHBOARD_URL")"
  if [[ -n "$ALT_DASHBOARD_URL" ]] && wait_for_http_ok "$ALT_DASHBOARD_URL" 10; then
    DASHBOARD_URL="$ALT_DASHBOARD_URL"
    echo "[info] dashboard reachable via alternate loopback: $DASHBOARD_URL"
  else
    echo "Dashboard readiness failed: $DASHBOARD_URL" >&2
    echo "See $DASHBOARD_LOG_FILE" >&2
    exit 1
  fi
fi

echo "[info] preflight: vc_demo_preflight.py (hybrid fallback)"
PREFLIGHT_POLICY="fallback"
if [[ "$FAILURE_MODE" == "fail-fast" ]]; then
  PREFLIGHT_POLICY="fail-fast"
fi
if [[ "$FAILURE_MODE" == "warn-only-noncritical" ]]; then
  PREFLIGHT_POLICY="skip"
fi

set +e
"$ROOT_DIR/nexra/venv/bin/python" "$ROOT_DIR/scripts/vc_demo_preflight.py" \
  --base-url "$BASE_URL" \
  --integrations "$INTEGRATIONS" \
  --failure-policy "$PREFLIGHT_POLICY" \
  --mock-sink-base-url "${MOCK_SINK_BASE_URL:-}" \
  --results-dir "$RESULTS_DIR"
PREFLIGHT_EXIT=$?
set -e
if [[ "$PREFLIGHT_EXIT" -ne 0 && "$FAILURE_MODE" == "fail-fast" ]]; then
  echo "Preflight failed in fail-fast mode." >&2
  exit "$PREFLIGHT_EXIT"
fi
if [[ ! -f "$PREFLIGHT_OUT" ]]; then
  echo "Preflight artifact missing: $PREFLIGHT_OUT" >&2
  exit 1
fi

echo "[info] seeding enterprise demo data"
"$ROOT_DIR/nexra/venv/bin/python" "$ROOT_DIR/scripts/vc_seed_enterprise_data.py" \
  --base-url "$BASE_URL" \
  --results-dir "$RESULTS_DIR"

if [[ ! -f "$ORG_PROFILE" ]]; then
  echo "Seed artifact missing: $ORG_PROFILE" >&2
  exit 1
fi

BUYER_API_KEY="$(
python3 - <<'PY' "$ORG_PROFILE"
import json, sys
obj = json.load(open(sys.argv[1], 'r', encoding='utf-8'))
print((((obj.get('orgs') or {}).get('buyer') or {}).get('api_key')) or '')
PY
)"
if [[ -z "$BUYER_API_KEY" ]]; then
  echo "Buyer API key missing in $ORG_PROFILE" >&2
  exit 1
fi

echo "[info] generating VC baseline/capability artifacts"
mkdir -p "$VC_SUITE_DIR"
SUITE_CMD=(
  "$ROOT_DIR/nexra/venv/bin/python"
  "$ROOT_DIR/scripts/vc_demo_suite.py"
  --base-url "$BASE_URL"
  --dashboard-url "$DASHBOARD_URL"
  --org-profile "$ORG_PROFILE"
  --results-dir "$VC_SUITE_DIR"
  --capability-matrix "$ROOT_DIR/demo/prd_capability_matrix.yaml"
)
if [[ "$MOCK_SINK_STARTED" == "1" ]]; then
  SUITE_CMD+=(--mock-sink-base-url "$MOCK_SINK_BASE_URL")
fi
set +e
"${SUITE_CMD[@]}"
SUITE_EXIT=$?
set -e
if [[ "$SUITE_EXIT" -ne 0 && "$FAILURE_MODE" == "fail-fast" ]]; then
  echo "vc_demo_suite failed in fail-fast mode." >&2
  exit "$SUITE_EXIT"
fi
if [[ ! -f "$VC_SUITE_DIR/baseline/summary.json" ]]; then
  echo "Baseline summary missing: $VC_SUITE_DIR/baseline/summary.json" >&2
  exit 1
fi

INTERNAL_DASHBOARD_DIR="$ROOT_DIR/nexra/internal-dashboard"
if [[ ! -x "$INTERNAL_DASHBOARD_DIR/node_modules/.bin/tsx" ]] || [[ ! -d "$INTERNAL_DASHBOARD_DIR/node_modules/playwright" ]]; then
  echo "[info] installing stress parity deps (tsx, playwright)..."
  (
    cd "$INTERNAL_DASHBOARD_DIR"
    npm install --no-save tsx playwright
  ) >"$RESULTS_DIR/parity-deps.log" 2>&1
fi
(
  cd "$INTERNAL_DASHBOARD_DIR"
  npx --yes playwright install chromium
) >>"$RESULTS_DIR/parity-deps.log" 2>&1 || true

echo "[info] starting API load + parity sweeps"
set +e
"$ROOT_DIR/nexra/venv/bin/python" "$ROOT_DIR/scripts/dashboard_api_load.py" \
  --base-url "$BASE_URL" \
  --api-key "$BUYER_API_KEY" \
  --user-email "admin@nexra.local" \
  --duration-min "$DURATION_MIN" \
  --peak-vus "$PEAK_VUS" \
  --error-rate-threshold "$ERROR_RATE_THRESHOLD" \
  --timeout-s 15 \
  --results-dir "$RESULTS_DIR" >"$RESULTS_DIR/load.log" 2>&1 &
LOAD_PID=$!

env "NEXRA_DASHBOARD_DIR=$INTERNAL_DASHBOARD_DIR" \
  "$INTERNAL_DASHBOARD_DIR/node_modules/.bin/tsx" \
  "$ROOT_DIR/scripts/dashboard_parity_sweep.ts" \
  --dashboard-url "$DASHBOARD_URL" \
  --api-base-url "$BASE_URL" \
  --api-key "$BUYER_API_KEY" \
  --user-email "admin@nexra.local" \
  --duration-min "$DURATION_MIN" \
  --sweep-interval-sec "$SWEEP_INTERVAL_SEC" \
  --route-timeout-ms "$ROUTE_TIMEOUT_MS" \
  --failure-mode "$([[ "$FAILURE_MODE" == "fail-fast" ]] && echo fail-fast || echo collect-all)" \
  --results-dir "$RESULTS_DIR" >"$RESULTS_DIR/parity.log" 2>&1 &
PARITY_PID=$!

if [[ "$FAILURE_MODE" == "fail-fast" ]]; then
  LOAD_EXIT=0
  PARITY_EXIT=0
  LOAD_DONE=0
  PARITY_DONE=0

  while [[ "$LOAD_DONE" == "0" || "$PARITY_DONE" == "0" ]]; do
    if [[ "$LOAD_DONE" == "0" ]] && ! kill -0 "$LOAD_PID" >/dev/null 2>&1; then
      wait "$LOAD_PID"
      LOAD_EXIT=$?
      LOAD_DONE=1
      if [[ "$LOAD_EXIT" -ne 0 && "$PARITY_DONE" == "0" ]] && kill -0 "$PARITY_PID" >/dev/null 2>&1; then
        echo "[warn] fail-fast: api load failed; terminating parity sweep"
        kill "$PARITY_PID" >/dev/null 2>&1 || true
      fi
    fi

    if [[ "$PARITY_DONE" == "0" ]] && ! kill -0 "$PARITY_PID" >/dev/null 2>&1; then
      wait "$PARITY_PID"
      PARITY_EXIT=$?
      PARITY_DONE=1
      if [[ "$PARITY_EXIT" -ne 0 && "$LOAD_DONE" == "0" ]] && kill -0 "$LOAD_PID" >/dev/null 2>&1; then
        echo "[warn] fail-fast: parity sweep failed; terminating api load"
        kill "$LOAD_PID" >/dev/null 2>&1 || true
      fi
    fi

    if [[ "$LOAD_DONE" == "0" || "$PARITY_DONE" == "0" ]]; then
      sleep 1
    fi
  done
else
  wait "$LOAD_PID"
  LOAD_EXIT=$?
  wait "$PARITY_PID"
  PARITY_EXIT=$?
fi
set -e

set +e
python3 - <<'PY' \
"$RESULTS_DIR" \
"$STRESS_SUMMARY" \
"$STRESS_REPORT" \
"$ERROR_RATE_THRESHOLD" \
"$ROUTE_TIMEOUT_MS" \
"$LOAD_EXIT" \
"$PARITY_EXIT" \
"$SUITE_EXIT" \
"$FAILURE_MODE"
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

results_dir = Path(sys.argv[1])
summary_path = Path(sys.argv[2])
report_path = Path(sys.argv[3])
err_threshold = float(sys.argv[4])
route_timeout_ms = int(sys.argv[5])
load_exit = int(sys.argv[6])
parity_exit = int(sys.argv[7])
suite_exit = int(sys.argv[8])
failure_mode = str(sys.argv[9])

def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

endpoint_metrics = read_json(results_dir / "endpoint_metrics.json")
ui_parity = read_json(results_dir / "ui_parity_results.json")
capability = read_json(results_dir / "vc_suite" / "capability_matrix_result.json")

critical: list[str] = []
warnings: list[str] = []
load_terminated_for_fail_fast = failure_mode == "fail-fast" and parity_exit != 0 and load_exit in {130, 143}

if not (results_dir / "vc_org_profile.json").exists():
    critical.append("missing vc_org_profile.json")
if not (results_dir / "vc_suite" / "baseline" / "summary.json").exists():
    critical.append("missing vc baseline summary")
if not (results_dir / "endpoint_metrics.json").exists():
    if load_terminated_for_fail_fast:
        warnings.append("endpoint_metrics.json missing (api load terminated after parity fail-fast)")
    else:
        critical.append("missing endpoint_metrics.json")
if not (results_dir / "ui_parity_results.json").exists():
    critical.append("missing ui_parity_results.json")

required_failed = int(capability.get("required_failed", 9999)) if capability else 9999
if required_failed != 0:
    critical.append(f"capability matrix required_failed={required_failed}")

if load_exit != 0:
    if load_terminated_for_fail_fast:
        warnings.append(f"dashboard_api_load exit={load_exit} (terminated after parity fail-fast)")
    else:
        critical.append(f"dashboard_api_load exit={load_exit}")
if parity_exit != 0:
    critical.append(f"dashboard_parity_sweep exit={parity_exit}")
if suite_exit != 0:
    warnings.append(f"vc_demo_suite exit={suite_exit} (artifacts still evaluated)")

route_fail = int(ui_parity.get("route_render_failures", 0))
route_latency_breaches = int(ui_parity.get("route_latency_breaches", 0))
ui_mismatch = int(ui_parity.get("required_mismatches", 0))
frontend_err = int(ui_parity.get("frontend_uncaught_errors", 0))
frontend_console_err = int(ui_parity.get("frontend_console_errors", 0))
frontend_network_err = int(ui_parity.get("frontend_network_errors", 0))
sweeps_run = int(ui_parity.get("sweeps_run", 0))
if sweeps_run < 1:
    critical.append("no parity sweeps completed")
if ui_mismatch > 0:
    critical.append(f"ui required mismatches={ui_mismatch}")
if route_fail > 0:
    critical.append(f"route render failures={route_fail}")
if frontend_err > 0:
    critical.append(f"frontend uncaught errors={frontend_err}")
if frontend_console_err > 0:
    warnings.append(f"frontend console errors={frontend_console_err}")
if frontend_network_err > 0:
    warnings.append(f"frontend network errors={frontend_network_err}")
if route_latency_breaches > 0:
    warnings.append(f"route latency breaches={route_latency_breaches} (threshold_ms={route_timeout_ms})")

required_endpoints = [
    "analytics_usage",
    "agents_registry",
    "delegations_list",
    "audit_log",
    "spend_summary",
    "policies_list",
    "org_me",
    "org_session",
    "org_api_keys",
    "org_members",
    "org_webhooks",
    "siem_config",
    "marketplace_connect_status",
]
endpoints = endpoint_metrics.get("endpoints", {}) if isinstance(endpoint_metrics, dict) else {}
if isinstance(endpoints, dict) and endpoints:
    for ep in required_endpoints:
        row = endpoints.get(ep)
        if not isinstance(row, dict):
            critical.append(f"required endpoint missing metrics: {ep}")
            continue
        rate = float(row.get("non_2xx_4xx_rate", 1.0))
        total = int(row.get("total_requests", 0))
        if total < 1:
            critical.append(f"required endpoint unexercised: {ep}")
        if rate > err_threshold:
            critical.append(f"{ep} non_2xx_4xx_rate={rate:.4f} > {err_threshold:.4f}")
elif not load_terminated_for_fail_fast:
    for ep in required_endpoints:
        critical.append(f"required endpoint missing metrics: {ep}")

status = "passed" if not critical else "failed"
payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "results_dir": str(results_dir),
    "status": status,
    "critical_failures": critical,
    "warnings": warnings,
    "thresholds": {
        "endpoint_non_2xx_4xx_rate": err_threshold,
        "route_timeout_ms": route_timeout_ms,
    },
    "artifacts": {
        "stress_summary": str(summary_path),
        "endpoint_metrics": str(results_dir / "endpoint_metrics.json"),
        "ui_parity_results": str(results_dir / "ui_parity_results.json"),
        "frontend_errors": str(results_dir / "frontend_errors.jsonl"),
        "api_failures": str(results_dir / "api_failures.jsonl"),
        "vc_capability_matrix": str(results_dir / "vc_suite" / "capability_matrix_result.json"),
    },
}
summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

report_lines = [
    "# Dashboard Stress Validation Report",
    f"- Generated: {payload['generated_at']}",
    f"- Status: **{status.upper()}**",
    f"- Results Directory: `{results_dir}`",
    "",
    "## Critical Failures",
]
if critical:
    report_lines.extend([f"- {item}" for item in critical])
else:
    report_lines.append("- None")

report_lines.append("")
report_lines.append("## Warnings")
if warnings:
    report_lines.extend([f"- {item}" for item in warnings])
else:
    report_lines.append("- None")

report_lines.append("")
report_lines.append("## Key Artifacts")
for name, path_value in payload["artifacts"].items():
    report_lines.append(f"- {name}: `{path_value}`")

report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
print(json.dumps({"status": status, "critical_failures": len(critical), "summary": str(summary_path), "report": str(report_path)}, indent=2))
sys.exit(0 if status == "passed" else 1)
PY
FINAL_EXIT=$?
set -e

echo "Load exit:      $LOAD_EXIT"
echo "Parity exit:    $PARITY_EXIT"
echo "VC suite exit:  $SUITE_EXIT"
echo "Summary:        $STRESS_SUMMARY"
echo "Report:         $STRESS_REPORT"

exit "$FINAL_EXIT"
