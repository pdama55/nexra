#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/nexra"
LOG_DIR="${TMPDIR:-/tmp}/nexra-live-demo-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$LOG_DIR"

API_BASE_URL="${NEXRA_API_BASE_URL:-http://127.0.0.1:8000}"
DASHBOARD_BASE_URL="${NEXRA_DASHBOARD_BASE_URL:-http://localhost:5173}"
STATE_FILE="${NEXRA_STATE_FILE:-}"

SKIP_NGROK="${NEXRA_SKIP_NGROK:-0}"
SKIP_DEMO_AGENTS="${NEXRA_SKIP_DEMO_AGENTS:-0}"
SKIP_DASHBOARD="${NEXRA_SKIP_DASHBOARD:-0}"
NO_TAIL="${NEXRA_NO_TAIL:-0}"
API_RELOAD="${NEXRA_API_RELOAD:-0}"

SYSTEM_NAME="$(uname -s)"
CELERY_POOL="${NEXRA_CELERY_POOL:-}"
if [[ -z "$CELERY_POOL" ]]; then
  if [[ "$SYSTEM_NAME" == "Darwin" ]]; then
    CELERY_POOL="solo"
  else
    CELERY_POOL="prefork"
  fi
fi
CELERY_CONCURRENCY="${NEXRA_CELERY_CONCURRENCY:-1}"

PIDS=()
PID_NAMES=()

print_https_webhook_help() {
  cat >&2 <<'EOF'
[remediation] Research agent webhook must be HTTPS (ngrok or trusted local TLS).
[remediation] 1) Start tunnel: ngrok http 8001
[remediation] 2) Export URL: eval "$(./scripts/export_research_webhook_url.sh)"
[remediation] 3) Re-run the demo startup.
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

write_state_file() {
  if [[ -z "$STATE_FILE" ]]; then
    return 0
  fi

  local pairs=""
  local i
  for i in "${!PIDS[@]}"; do
    pairs+="${PID_NAMES[$i]}:${PIDS[$i]}"$'\n'
  done

  STATE_FILE="$STATE_FILE" \
  API_BASE_URL="$API_BASE_URL" \
  DASHBOARD_BASE_URL="$DASHBOARD_BASE_URL" \
  LOG_DIR="$LOG_DIR" \
  NGROK_URL="${NGROK_URL:-}" \
  API_KEY="${API_KEY:-}" \
  SCRIPT_PID="$$" \
  PID_PAIRS="$pairs" \
  python3 - <<'PY'
import json
import os
from pathlib import Path

pairs_raw = os.environ.get("PID_PAIRS", "")
processes = {}
for line in pairs_raw.splitlines():
    if not line.strip() or ":" not in line:
        continue
    name, pid = line.split(":", 1)
    if name:
        processes[name] = int(pid)

payload = {
    "script_pid": int(os.environ["SCRIPT_PID"]),
    "api_base_url": os.environ["API_BASE_URL"],
    "dashboard_base_url": os.environ["DASHBOARD_BASE_URL"],
    "log_dir": os.environ["LOG_DIR"],
    "ngrok_url": os.environ.get("NGROK_URL") or None,
    "api_key": os.environ.get("API_KEY") or None,
    "processes": processes,
}

path = Path(os.environ["STATE_FILE"])
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
PY
}

cleanup() {
  echo
  echo "[cleanup] stopping background processes..."
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
  sleep 1
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
  done
  write_state_file
  echo "[cleanup] logs saved at: $LOG_DIR"
}
trap cleanup EXIT INT TERM

start_bg() {
  local name="$1"
  local cmd="$2"
  local logfile="$LOG_DIR/${name}.log"

  echo "[start] $name"
  (
    cd "$ROOT_DIR"
    eval "$cmd"
  ) >"$logfile" 2>&1 &

  local pid=$!
  PIDS+=("$pid")
  PID_NAMES+=("$name")
  echo "[start] $name pid=$pid log=$logfile"
  write_state_file
}

poll_http_ok() {
  local url="$1"
  local timeout_s="${2:-60}"
  local start_ts
  start_ts="$(date +%s)"

  while true; do
    if curl -sf "$url" >/dev/null 2>&1; then
      return 0
    fi
    if (( $(date +%s) - start_ts > timeout_s )); then
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

get_ngrok_url() {
  curl -s http://127.0.0.1:4040/api/tunnels | python3 -c '
import json,sys
try:
    data=json.load(sys.stdin)
except Exception:
    raise SystemExit(1)
for t in data.get("tunnels", []):
    u=t.get("public_url","")
    if u.startswith("https://"):
        print(u)
        raise SystemExit(0)
raise SystemExit(1)
'
}

auto_open_url() {
  local url="$1"

  if [[ "${NEXRA_NO_AUTO_OPEN:-0}" == "1" ]]; then
    echo "[info] auto-open disabled (NEXRA_NO_AUTO_OPEN=1)"
    return 0
  fi

  if command -v open >/dev/null 2>&1; then
    open "$url" >/dev/null 2>&1 || true
    return 0
  fi

  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 || true
    return 0
  fi

  python3 -m webbrowser "$url" >/dev/null 2>&1 || true
}

require_cmd bash
require_cmd curl
require_cmd python3
if [[ "$SKIP_NGROK" != "1" ]]; then
  require_cmd ngrok
fi
if [[ "$SKIP_DASHBOARD" != "1" ]]; then
  require_cmd npm
fi

if [[ ! -d "$APP_DIR" ]]; then
  echo "App directory not found: $APP_DIR" >&2
  exit 1
fi

if [[ ! -x "$APP_DIR/venv/bin/python" ]]; then
  echo "Python venv not found at $APP_DIR/venv/bin/python" >&2
  exit 1
fi

if [[ ! -f "$APP_DIR/.env" ]]; then
  echo "Missing $APP_DIR/.env" >&2
  exit 1
fi

echo "[info] running migrations..."
(
  cd "$APP_DIR"
  ./venv/bin/alembic upgrade head
)

CELERY_REDIS_URL="$(grep '^REDIS_URL=' "$APP_DIR/.env" | cut -d= -f2- || true)"
if [[ -z "$CELERY_REDIS_URL" ]]; then
  echo "[error] REDIS_URL not found in $APP_DIR/.env" >&2
  exit 1
fi
if [[ "$CELERY_REDIS_URL" == rediss://* ]] && [[ "$CELERY_REDIS_URL" != *ssl_cert_reqs=* ]]; then
  if [[ "$CELERY_REDIS_URL" == *\?* ]]; then
    CELERY_REDIS_URL="${CELERY_REDIS_URL}&ssl_cert_reqs=CERT_NONE"
  else
    CELERY_REDIS_URL="${CELERY_REDIS_URL}?ssl_cert_reqs=CERT_NONE"
  fi
fi

echo "[info] starting core services..."
echo "[info] api reload: $API_RELOAD | celery pool: $CELERY_POOL | celery concurrency: $CELERY_CONCURRENCY"
if [[ "$API_RELOAD" == "1" ]]; then
  start_bg "api" "cd '$APP_DIR' && ./venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"
else
  start_bg "api" "cd '$APP_DIR' && ./venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000"
fi

if [[ "$SYSTEM_NAME" == "Darwin" && "$CELERY_POOL" != "solo" ]]; then
  export OBJC_DISABLE_INITIALIZE_FORK_SAFETY="${OBJC_DISABLE_INITIALIZE_FORK_SAFETY:-YES}"
fi

start_bg "worker" "cd '$APP_DIR' && export REDIS_URL='$CELERY_REDIS_URL' CELERY_BROKER_URL='$CELERY_REDIS_URL' && ./venv/bin/celery -A workers.celery_app worker --loglevel=info --pool '$CELERY_POOL' --concurrency '$CELERY_CONCURRENCY' -Q webhooks,billing,anomaly,hitl,siem -I workers.webhook_worker,workers.billing_worker,workers.anomaly_worker,workers.hitl_worker,workers.siem_worker"
start_bg "beat" "cd '$APP_DIR' && export REDIS_URL='$CELERY_REDIS_URL' CELERY_BROKER_URL='$CELERY_REDIS_URL' && ./venv/bin/celery -A workers.celery_app beat --loglevel=info"

if ! poll_http_ok "$API_BASE_URL/health" 60; then
  echo "[error] API did not become healthy. Check $LOG_DIR/api.log" >&2
  exit 1
fi

NGROK_URL=""
if [[ "$SKIP_NGROK" != "1" ]]; then
  echo "[info] launching ngrok for research-agent webhook (port 8001)..."
  start_bg "ngrok" "ngrok http 8001"

  for _ in {1..30}; do
    if NGROK_URL="$(get_ngrok_url 2>/dev/null)"; then
      break
    fi
    sleep 1
  done

  if [[ -z "$NGROK_URL" ]]; then
    echo "[error] could not resolve ngrok public URL. Check $LOG_DIR/ngrok.log" >&2
    print_https_webhook_help
    exit 1
  fi

  echo "[info] ngrok url: $NGROK_URL"
fi

echo "[info] creating demo org + api key..."
ORG_JSON="$(curl -sS -X POST "$API_BASE_URL/v1/orgs/register" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Demo Org Auto","plan":"growth"}')"

API_KEY="$(printf '%s' "$ORG_JSON" | python3 -c '
import json,sys
obj=json.load(sys.stdin)
key=((obj.get("data") or {}).get("api_key"))
if not key:
    raise SystemExit(1)
print(key)
')"

if [[ -z "$API_KEY" ]]; then
  echo "[error] failed to parse api key from org response" >&2
  echo "$ORG_JSON" >&2
  exit 1
fi

echo "[info] creating demo allow policy (avoids default-deny)..."
POLICY_JSON="$(curl -sS -X POST "$API_BASE_URL/v1/policies" \
  -H "Authorization: Bearer $API_KEY" \
  -H 'X-User-Email: admin@nexra.local' \
  -H 'Content-Type: application/json' \
  -d '{"name":"demo-allow-all","description":"Auto-created by run_live_demo.sh for local demonstration","priority":1,"allow":{},"conditions":[],"on_violation":"block_and_alert"}')"
if ! printf '%s' "$POLICY_JSON" | python3 -c 'import json,sys; obj=json.load(sys.stdin); raise SystemExit(0 if "data" in obj else 1)' >/dev/null 2>&1; then
  echo "[error] failed to create demo policy" >&2
  echo "$POLICY_JSON" >&2
  exit 1
fi

if [[ "$SKIP_DEMO_AGENTS" != "1" ]]; then
  if [[ "$SKIP_NGROK" == "1" ]]; then
    if [[ -z "${NEXRA_RESEARCH_WEBHOOK_URL_OVERRIDE:-}" ]]; then
      echo "[error] NEXRA_SKIP_NGROK=1 requires NEXRA_RESEARCH_WEBHOOK_URL_OVERRIDE when demo agents are enabled." >&2
      print_https_webhook_help
      exit 1
    fi
    NGROK_URL="$NEXRA_RESEARCH_WEBHOOK_URL_OVERRIDE"
  fi

  if [[ "$NGROK_URL" != https://* ]]; then
    echo "[error] research webhook base URL must use HTTPS: $NGROK_URL" >&2
    print_https_webhook_help
    exit 1
  fi

  RESEARCH_WEBHOOK_URL="$NGROK_URL"
  if [[ "$RESEARCH_WEBHOOK_URL" != */webhook ]]; then
    RESEARCH_WEBHOOK_URL="${RESEARCH_WEBHOOK_URL%/}/webhook"
  fi

  echo "[info] starting demo agents..."
  start_bg "research-agent" "cd '$APP_DIR' && export NEXRA_API_KEY='$API_KEY' NEXRA_BASE_URL='$API_BASE_URL/v1' NEXRA_RESEARCH_WEBHOOK_URL='$RESEARCH_WEBHOOK_URL' && PYTHONPATH='./sdk/nexra-py' ./venv/bin/python demo/research_agent.py"

  sleep 3

  start_bg "sales-agent" "cd '$APP_DIR' && export NEXRA_API_KEY='$API_KEY' NEXRA_BASE_URL='$API_BASE_URL/v1' && PYTHONPATH='./sdk/nexra-py' ./venv/bin/python demo/sales_agent.py"
else
  echo "[info] skipping demo agents (NEXRA_SKIP_DEMO_AGENTS=1)"
fi

if [[ "$SKIP_DASHBOARD" != "1" ]]; then
  echo "[info] starting internal dashboard..."
  start_bg "dashboard" "cd '$APP_DIR/internal-dashboard' && npm run dev"

  DASHBOARD_READY_URL=""
  if poll_http_ok "$DASHBOARD_BASE_URL" 60; then
    DASHBOARD_READY_URL="$DASHBOARD_BASE_URL"
  else
    ALT_DASHBOARD_URL="$(alternate_loopback_url "$DASHBOARD_BASE_URL")"
    if [[ -n "$ALT_DASHBOARD_URL" ]] && poll_http_ok "$ALT_DASHBOARD_URL" 5; then
      DASHBOARD_READY_URL="$ALT_DASHBOARD_URL"
      echo "[info] dashboard reachable via alternate loopback URL: $ALT_DASHBOARD_URL"
    fi
  fi

  if [[ -n "$DASHBOARD_READY_URL" ]]; then
    DASHBOARD_OPEN_URL="$DASHBOARD_READY_URL/?nexra_api_key=$API_KEY"
    echo "[info] opening dashboard in browser..."
    auto_open_url "$DASHBOARD_OPEN_URL"
  else
    echo "[warn] dashboard did not become ready in time. Open manually: $DASHBOARD_BASE_URL"
  fi
else
  echo "[info] skipping dashboard (NEXRA_SKIP_DASHBOARD=1)"
fi

write_state_file

echo
echo "========== Nexra Live Demo =========="
echo "API:        $API_BASE_URL"
echo "Health:     $API_BASE_URL/health"
if [[ "$SKIP_DASHBOARD" != "1" ]]; then
  echo "Dashboard:  $DASHBOARD_BASE_URL"
fi
if [[ -n "$NGROK_URL" ]]; then
  echo "ngrok:      $NGROK_URL"
fi
if [[ -n "${RESEARCH_WEBHOOK_URL:-}" ]]; then
  echo "Webhook:    $RESEARCH_WEBHOOK_URL"
fi
echo "Logs dir:   $LOG_DIR"
if [[ -n "$STATE_FILE" ]]; then
  echo "State file: $STATE_FILE"
fi
echo
echo "API key auto-injected into dashboard from launch URL."
echo "If needed manually in browser console:"
echo "localStorage.setItem('nexra_api_key', '$API_KEY'); location.reload();"
echo
echo "Press Ctrl+C to stop everything."
echo "====================================="
echo

if [[ "$NO_TAIL" == "1" ]]; then
  echo "[info] NEXRA_NO_TAIL=1 enabled; keeping supervisor process alive without log tail"
  while true; do
    sleep 3600
  done
fi

tail -n +1 -F "$LOG_DIR"/*.log
