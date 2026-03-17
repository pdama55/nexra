#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/nexra"
LOG_DIR="${TMPDIR:-/tmp}/nexra-live-demo-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$LOG_DIR"

PIDS=()

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
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
  echo "[start] $name pid=$pid log=$logfile"
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
require_cmd ngrok
require_cmd npm

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

echo "[info] starting core services..."
start_bg "api" "cd '$APP_DIR' && ./venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"
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
start_bg "worker" "cd '$APP_DIR' && export REDIS_URL='$CELERY_REDIS_URL' CELERY_BROKER_URL='$CELERY_REDIS_URL' && ./venv/bin/celery -A workers.celery_app worker --loglevel=info -Q webhooks,billing,anomaly,hitl,siem -I workers.webhook_worker,workers.billing_worker,workers.anomaly_worker,workers.hitl_worker,workers.siem_worker"
start_bg "beat" "cd '$APP_DIR' && export REDIS_URL='$CELERY_REDIS_URL' CELERY_BROKER_URL='$CELERY_REDIS_URL' && ./venv/bin/celery -A workers.celery_app beat --loglevel=info"

if ! poll_http_ok "http://127.0.0.1:8000/health" 60; then
  echo "[error] API did not become healthy. Check $LOG_DIR/api.log" >&2
  exit 1
fi

echo "[info] launching ngrok for research-agent webhook (port 8001)..."
start_bg "ngrok" "ngrok http 8001"

NGROK_URL=""
for _ in {1..30}; do
  if NGROK_URL="$(get_ngrok_url 2>/dev/null)"; then
    break
  fi
  sleep 1
done

if [[ -z "$NGROK_URL" ]]; then
  echo "[error] could not resolve ngrok public URL. Check $LOG_DIR/ngrok.log" >&2
  exit 1
fi

echo "[info] ngrok url: $NGROK_URL"

echo "[info] creating demo org + api key..."
ORG_JSON="$(curl -sS -X POST http://127.0.0.1:8000/v1/orgs/register \
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
POLICY_JSON="$(curl -sS -X POST http://127.0.0.1:8000/v1/policies \
  -H "Authorization: Bearer $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"name":"demo-allow-all","description":"Auto-created by run_live_demo.sh for local demonstration","priority":1,"allow":{},"conditions":[],"on_violation":"block_and_alert"}')"
if ! printf '%s' "$POLICY_JSON" | python3 -c 'import json,sys; obj=json.load(sys.stdin); raise SystemExit(0 if "data" in obj else 1)' >/dev/null 2>&1; then
  echo "[error] failed to create demo policy" >&2
  echo "$POLICY_JSON" >&2
  exit 1
fi

echo "[info] starting demo agents..."
start_bg "research-agent" "cd '$APP_DIR' && export NEXRA_API_KEY='$API_KEY' NEXRA_BASE_URL='http://127.0.0.1:8000/v1' NEXRA_RESEARCH_WEBHOOK_URL='$NGROK_URL/webhook' && PYTHONPATH='./sdk/nexra-py' ./venv/bin/python demo/research_agent.py"

sleep 3

start_bg "sales-agent" "cd '$APP_DIR' && export NEXRA_API_KEY='$API_KEY' NEXRA_BASE_URL='http://127.0.0.1:8000/v1' && PYTHONPATH='./sdk/nexra-py' ./venv/bin/python demo/sales_agent.py"

echo "[info] starting internal dashboard..."
start_bg "dashboard" "cd '$APP_DIR/internal-dashboard' && npm run dev"

if poll_http_ok "http://127.0.0.1:5173" 60; then
  DASHBOARD_OPEN_URL="http://127.0.0.1:5173/?nexra_api_key=$API_KEY"
  echo "[info] opening dashboard in browser..."
  auto_open_url "$DASHBOARD_OPEN_URL"
else
  echo "[warn] dashboard did not become ready in time. Open manually: http://127.0.0.1:5173"
fi

echo

echo "========== Nexra Live Demo =========="
echo "API:        http://127.0.0.1:8000"
echo "Health:     http://127.0.0.1:8000/health"
echo "Dashboard:  http://127.0.0.1:5173"
echo "ngrok:      $NGROK_URL"
echo "Logs dir:   $LOG_DIR"
echo
echo "API key auto-injected into dashboard from launch URL."
echo "If needed manually in browser console:"
echo "localStorage.setItem('nexra_api_key', '$API_KEY'); location.reload();"
echo
echo "Press Ctrl+C to stop everything."
echo "====================================="
echo

tail -n +1 -F "$LOG_DIR"/*.log
