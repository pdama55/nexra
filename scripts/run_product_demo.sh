#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MODE="${NEXRA_DEMO_MODE:-auto}"
PROFILE="${NEXRA_DEMO_PROFILE:-vc-12m}"
INTEGRATIONS="${NEXRA_DEMO_INTEGRATIONS:-real}"
FAILURE_POLICY="${NEXRA_DEMO_FAILURE_POLICY:-fail-fast}"
VERIFY_LEVEL="${NEXRA_DEMO_VERIFY:-standard}"
BASE_URL="${NEXRA_API_BASE_URL:-http://127.0.0.1:8000}"
DASHBOARD_URL="${NEXRA_DASHBOARD_BASE_URL:-http://127.0.0.1:5173}"
RESULTS_DIR="$ROOT_DIR/test-results/vc-demo/$(date +%Y%m%d-%H%M%S)"
STRICT=0
HEADED=0
OPEN_DASHBOARD=1
SKIP_INFRA_PROBE="${NEXRA_DEMO_SKIP_INFRA_PROBE:-0}"

print_usage() {
  cat <<'EOF'
Usage:
  ./scripts/run_product_demo.sh [options]

Default behavior:
  - Runs core verification checks (unit + contracts + OpenAPI snapshot + dashboard build)
  - Chooses mode automatically (attach if API is healthy, otherwise bootstrap)
  - Runs VC demo suite with real integrations and fail-fast policy
  - Auto-opens dashboard in the browser

Options:
  --mode auto|attach|bootstrap
  --profile vc-12m|full
  --integrations real|hybrid|mock
  --failure-policy fail-fast|fallback|skip
  --verify none|standard|full
  --base-url URL
  --dashboard-url URL
  --results-dir PATH
  --strict
  --headed
  --no-open-dashboard
  --help

Examples:
  ./scripts/run_product_demo.sh
  ./scripts/run_product_demo.sh --mode auto --verify none
  ./scripts/run_product_demo.sh --verify full
EOF
}

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
    --verify)
      VERIFY_LEVEL="$2"
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
    --no-open-dashboard)
      OPEN_DASHBOARD=0
      shift
      ;;
    --help|-h)
      print_usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      print_usage >&2
      exit 1
      ;;
  esac
done

if [[ "$MODE" != "auto" && "$MODE" != "attach" && "$MODE" != "bootstrap" ]]; then
  echo "--mode must be auto, attach, or bootstrap" >&2
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
if [[ "$VERIFY_LEVEL" != "none" && "$VERIFY_LEVEL" != "standard" && "$VERIFY_LEVEL" != "full" ]]; then
  echo "--verify must be none, standard, or full" >&2
  exit 1
fi

VENV_PYTHON="$ROOT_DIR/nexra/venv/bin/python"
if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Missing virtualenv python: $VENV_PYTHON" >&2
  exit 1
fi

run_standard_checks() {
  echo "[checks] running unit tests"
  (
    cd "$ROOT_DIR/nexra"
    "$VENV_PYTHON" -m pytest -q tests/unit
  )

  echo "[checks] running contract tests"
  (
    cd "$ROOT_DIR/nexra"
    "$VENV_PYTHON" -m pytest -q tests/contracts
  )

  echo "[checks] validating OpenAPI snapshot"
  (
    cd "$ROOT_DIR/nexra"
    "$VENV_PYTHON" "$ROOT_DIR/scripts/check_openapi_snapshot.py"
  )

  echo "[checks] building internal dashboard"
  (
    cd "$ROOT_DIR/nexra/internal-dashboard"
    npm run build
  )
}

run_full_checks() {
  run_standard_checks
  echo "[checks] running integration + e2e suites against external infra"
  "$ROOT_DIR/scripts/run_db_backed_tests.sh" --infra-mode external
}

probe_external_infra() {
  local env_file="$ROOT_DIR/nexra/.env"
  local db_url="${TEST_DATABASE_URL:-${DATABASE_URL:-}}"
  local redis_url="${REDIS_URL:-}"

  if [[ -z "$db_url" && -f "$env_file" ]]; then
    db_url="$(grep '^DATABASE_URL=' "$env_file" | tail -n 1 | cut -d= -f2- || true)"
  fi
  if [[ -z "$redis_url" && -f "$env_file" ]]; then
    redis_url="$(grep '^REDIS_URL=' "$env_file" | tail -n 1 | cut -d= -f2- || true)"
  fi

  if [[ -z "$db_url" || -z "$redis_url" ]]; then
    echo "[infra] missing DATABASE_URL/REDIS_URL (env or nexra/.env) for real bootstrap mode" >&2
    return 1
  fi

  echo "[infra] probing external Postgres/Redis reachability"
  "$VENV_PYTHON" - <<'PY' "$db_url" "$redis_url"
import asyncio
import sys
from urllib.parse import urlparse

import asyncpg
import redis.asyncio as redis

db_url = sys.argv[1]
redis_url = sys.argv[2]

def _mask_db(url: str) -> str:
    u = urlparse(url.replace("postgresql+asyncpg://", "postgresql://", 1))
    return f"postgresql://***@{u.hostname}:{u.port or 5432}/{u.path.lstrip('/')}"

def _mask_redis(url: str) -> str:
    u = urlparse(url)
    return f"{u.scheme}://***@{u.hostname}:{u.port or 6379}"

def _asyncpg_dsn(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url

async def main() -> int:
    print(f"[infra] postgres_target={_mask_db(db_url)}")
    print(f"[infra] redis_target={_mask_redis(redis_url)}")

    db_err = None
    redis_err = None

    try:
        conn = await asyncpg.connect(_asyncpg_dsn(db_url), timeout=8)
        await conn.fetchval("select 1")
        await conn.close()
    except Exception as exc:  # noqa: BLE001
        db_err = exc

    try:
        client = redis.from_url(redis_url, decode_responses=True)
        pong = await asyncio.wait_for(client.ping(), timeout=8)
        await client.aclose()
        if pong is not True:
            redis_err = RuntimeError(f"unexpected ping response: {pong!r}")
    except Exception as exc:  # noqa: BLE001
        redis_err = exc

    if db_err is None and redis_err is None:
        print("[infra] external dependencies reachable")
        return 0

    if db_err is not None:
        print(f"[infra] postgres_probe_failed={db_err!r}")
    if redis_err is not None:
        print(f"[infra] redis_probe_failed={redis_err!r}")
    return 1

raise SystemExit(asyncio.run(main()))
PY
}

echo "[demo] verify=$VERIFY_LEVEL mode=$MODE integrations=$INTEGRATIONS failure_policy=$FAILURE_POLICY"

if [[ "$MODE" == "auto" ]]; then
  if curl -sf "${BASE_URL%/}/health" >/dev/null 2>&1; then
    MODE="attach"
    echo "[demo] auto mode selected attach (API healthy at ${BASE_URL%/}/health)"
  else
    MODE="bootstrap"
    echo "[demo] auto mode selected bootstrap (API not reachable at ${BASE_URL%/}/health)"
  fi
fi

if [[ "$SKIP_INFRA_PROBE" != "1" && "$MODE" == "bootstrap" && "$INTEGRATIONS" == "real" ]]; then
  if ! probe_external_infra; then
    echo "[infra] probe failed before bootstrap. Verify Neon/Upstash network access and credentials." >&2
    exit 1
  fi
fi

if [[ "$VERIFY_LEVEL" == "standard" ]]; then
  run_standard_checks
elif [[ "$VERIFY_LEVEL" == "full" ]]; then
  run_full_checks
else
  echo "[checks] skipped (verify=none)"
fi

RUN_CMD=(
  "$ROOT_DIR/scripts/run_vc_demo.sh"
  --mode "$MODE"
  --profile "$PROFILE"
  --integrations "$INTEGRATIONS"
  --failure-policy "$FAILURE_POLICY"
  --base-url "$BASE_URL"
  --dashboard-url "$DASHBOARD_URL"
  --results-dir "$RESULTS_DIR"
)

if [[ "$STRICT" == "1" ]]; then
  RUN_CMD+=(--strict)
fi
if [[ "$HEADED" == "1" ]]; then
  RUN_CMD+=(--headed)
fi
if [[ "$OPEN_DASHBOARD" == "1" ]]; then
  RUN_CMD+=(--open-dashboard)
fi

echo "[demo] running VC demo pipeline"
"${RUN_CMD[@]}"
