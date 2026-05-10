#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/nexra/docker/docker-compose.yml"
VENV_PYTHON="$ROOT_DIR/nexra/venv/bin/python"

WAIT_SECONDS=90
PREPARE_ONLY=0
INFRA_MODE="auto"

resolve_endpoints() {
  python3 - <<'PY' "$ROOT_DIR"
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

root = Path(sys.argv[1])
env_files = [
    root / ".env.local",
    root / ".env",
    root / "nexra" / ".env.local",
    root / "nexra" / ".env",
]

allowed_keys = {"TEST_DATABASE_URL", "DATABASE_URL", "REDIS_URL"}
file_values: dict[str, str] = {}

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
        if key not in allowed_keys:
            continue
        file_values.setdefault(key, value.strip().strip('"').strip("'"))

explicit_test_db = os.getenv("TEST_DATABASE_URL", "").strip()
explicit_db = os.getenv("DATABASE_URL", "").strip()
explicit_redis = os.getenv("REDIS_URL", "").strip()

test_database_url = (
    explicit_test_db
    or explicit_db
    or file_values.get("TEST_DATABASE_URL", "")
    or file_values.get("DATABASE_URL", "")
    or "postgresql+asyncpg://nexra:nexra@localhost:5432/nexra_test"
)
redis_url = (
    explicit_redis
    or file_values.get("REDIS_URL", "")
    or "redis://localhost:6379/1"
)
database_url = explicit_db or file_values.get("DATABASE_URL", "") or test_database_url

def _host(url: str, *, is_db: bool) -> str:
    normalized = url
    if is_db and normalized.startswith("postgresql+asyncpg://"):
        normalized = normalized.replace("postgresql+asyncpg://", "postgresql://", 1)
    return (urlparse(normalized).hostname or "").strip().lower()

def _is_nonlocal_host(host: str) -> bool:
    return bool(host) and host not in {"localhost", "127.0.0.1", "::1"}

external_target_configured = _is_nonlocal_host(_host(test_database_url, is_db=True)) or _is_nonlocal_host(_host(redis_url, is_db=False))

print(test_database_url)
print(redis_url)
print(database_url)
print("1" if external_target_configured else "0")
PY
}

PYTEST_ARGS=(
  -q
  tests/integration
  tests/e2e
)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prepare-only)
      PREPARE_ONLY=1
      shift
      ;;
    --wait-seconds)
      WAIT_SECONDS="$2"
      shift 2
      ;;
    --infra-mode)
      INFRA_MODE="$2"
      shift 2
      ;;
    --help|-h)
      cat <<'EOF'
Usage:
  ./scripts/run_db_backed_tests.sh [--prepare-only] [--wait-seconds N] [--infra-mode auto|external|docker] [-- <pytest args>]

Modes:
  auto      probe configured TEST_DATABASE_URL/REDIS_URL first; if unreachable, try Docker fallback
  external  only use configured external infra (Neon/Upstash/local managed services); never start Docker
  docker    always start postgres+redis via docker compose
EOF
      exit 0
      ;;
    --)
      shift
      PYTEST_ARGS+=("$@")
      break
      ;;
    *)
      PYTEST_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ "$INFRA_MODE" != "auto" && "$INFRA_MODE" != "external" && "$INFRA_MODE" != "docker" ]]; then
  echo "--infra-mode must be auto, external, or docker" >&2
  exit 1
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "missing virtualenv python at $VENV_PYTHON" >&2
  exit 1
fi

{
  IFS= read -r TEST_DATABASE_URL
  IFS= read -r REDIS_URL
  IFS= read -r DATABASE_URL
  IFS= read -r EXTERNAL_TARGET_CONFIGURED
} < <(resolve_endpoints)

TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql+asyncpg://nexra:nexra@localhost:5432/nexra_test}"
REDIS_URL="${REDIS_URL:-redis://localhost:6379/1}"
DATABASE_URL="${DATABASE_URL:-$TEST_DATABASE_URL}"
EXTERNAL_TARGET_CONFIGURED="${EXTERNAL_TARGET_CONFIGURED:-0}"

probe_external_services() {
  "$VENV_PYTHON" - <<'PY' "$TEST_DATABASE_URL" "$REDIS_URL" "$WAIT_SECONDS"
import asyncio
import sys
import time

import asyncpg
import redis.asyncio as redis

db_url = sys.argv[1]
redis_url = sys.argv[2]
timeout_s = int(sys.argv[3])

def asyncpg_dsn(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url

async def probe_db(url: str) -> tuple[bool, str]:
    conn = None
    try:
        conn = await asyncpg.connect(asyncpg_dsn(url), timeout=5)
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    finally:
        if conn is not None:
            await conn.close()

async def probe_redis(url: str) -> tuple[bool, str]:
    client = redis.from_url(url, decode_responses=True)
    try:
        pong = await asyncio.wait_for(client.ping(), timeout=5)
        if pong is True:
            return True, "ok"
        return False, f"unexpected ping result: {pong}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    finally:
        await client.aclose()

async def main() -> int:
    deadline = time.monotonic() + timeout_s
    last_db = "not checked"
    last_redis = "not checked"

    while time.monotonic() < deadline:
        db_ok, db_msg = await probe_db(db_url)
        redis_ok, redis_msg = await probe_redis(redis_url)
        last_db = db_msg
        last_redis = redis_msg
        if db_ok and redis_ok:
            print("external_infra_ready")
            return 0
        await asyncio.sleep(2)

    def classify_error(message: str) -> str:
        lowered = message.lower()
        credential_markers = [
            "password",
            "authentication",
            "auth",
            "invalid dsn",
            "database",
            "does not exist",
            "unknown database",
            "no such host",
            "name or service not known",
        ]
        if any(marker in lowered for marker in credential_markers):
            return "credential_or_config_failure"
        return "unreachable"

    db_class = classify_error(last_db)
    redis_class = classify_error(last_redis)
    print(f"db_precheck=failed classification={db_class} detail={last_db}")
    print(f"redis_precheck=failed classification={redis_class} detail={last_redis}")
    return 1

raise SystemExit(asyncio.run(main()))
PY
}

docker_available() {
  command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1
}

wait_for_docker_daemon() {
  local timeout_s="${1:-60}"
  local started
  started="$(date +%s)"
  while true; do
    if docker_available; then
      return 0
    fi
    if (( $(date +%s) - started > timeout_s )); then
      return 1
    fi
    sleep 2
  done
}

ensure_docker_daemon() {
  if docker_available; then
    return 0
  fi

  local attempts=()

  if [[ "${OSTYPE:-}" == darwin* ]] && command -v open >/dev/null 2>&1; then
    if [[ -d "/Applications/Docker.app" || -d "$HOME/Applications/Docker.app" ]]; then
      echo "[db-tests] docker daemon unavailable; attempting Docker Desktop startup"
      open -ga Docker >/dev/null 2>&1 || true
      attempts+=("docker_desktop")
      if wait_for_docker_daemon 75; then
        echo "[db-tests] docker daemon ready after Docker Desktop startup"
        return 0
      fi
    fi
  fi

  if command -v colima >/dev/null 2>&1; then
    echo "[db-tests] docker daemon unavailable; attempting Colima startup"
    colima start >/dev/null 2>&1 || true
    attempts+=("colima")
    if wait_for_docker_daemon 60; then
      echo "[db-tests] docker daemon ready after Colima startup"
      return 0
    fi
  fi

  if command -v rdctl >/dev/null 2>&1; then
    echo "[db-tests] docker daemon unavailable; attempting Rancher Desktop startup"
    rdctl start >/dev/null 2>&1 || true
    attempts+=("rancher_desktop")
    if wait_for_docker_daemon 60; then
      echo "[db-tests] docker daemon ready after Rancher Desktop startup"
      return 0
    fi
  fi

  local detail
  if [[ ${#attempts[@]} -eq 0 ]]; then
    detail="docker daemon unavailable; no local runtime launcher detected"
  else
    detail="docker daemon unavailable after startup attempts: ${attempts[*]}"
  fi
  echo "docker_precheck=failed classification=docker_daemon_unavailable detail='${detail}'" >&2
  return 1
}

start_docker_infra() {
  if ! ensure_docker_daemon; then
    return 1
  fi

  echo "[db-tests] starting postgres + redis from $COMPOSE_FILE"
  docker compose -f "$COMPOSE_FILE" up -d postgres redis >/dev/null

  local started
  started="$(date +%s)"
  while true; do
    if docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U nexra -d postgres >/dev/null 2>&1 &&
      docker compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping >/dev/null 2>&1; then
      break
    fi
    if (( $(date +%s) - started > WAIT_SECONDS )); then
      echo "docker postgres/redis did not become ready within ${WAIT_SECONDS}s" >&2
      return 1
    fi
    sleep 1
  done

  local db_name
  db_name="$(python3 - <<'PY' "$TEST_DATABASE_URL"
import sys
from urllib.parse import urlparse

url = sys.argv[1]
path = urlparse(url).path or ""
print(path.lstrip("/") or "nexra_test")
PY
)"
  local db_exists
  db_exists="$(docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U nexra -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${db_name}'" | tr -d '[:space:]')"
  if [[ "$db_exists" != "1" ]]; then
    echo "[db-tests] creating database: $db_name"
    docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U nexra -d postgres -c "CREATE DATABASE ${db_name};" >/dev/null
  fi
}

mask_secret_in_url() {
  local raw="${1:-}"
  if [[ -z "$raw" ]]; then
    printf '%s\n' ""
    return 0
  fi
  printf '%s\n' "$raw" | sed -E 's#://[^/@]*@#://***@#'
}

echo "[db-tests] infra_mode=$INFRA_MODE"
echo "[db-tests] TEST_DATABASE_URL=$(mask_secret_in_url "$TEST_DATABASE_URL")"
echo "[db-tests] REDIS_URL=$(mask_secret_in_url "$REDIS_URL")"
echo "[db-tests] external_target_configured=$EXTERNAL_TARGET_CONFIGURED"

if [[ "$INFRA_MODE" == "external" ]]; then
  echo "[db-tests] probing external DB/Redis endpoints"
  probe_external_services
elif [[ "$INFRA_MODE" == "docker" ]]; then
  start_docker_infra
  probe_external_services
else
  echo "[db-tests] probing configured DB/Redis endpoints"
  if probe_external_services; then
    echo "[db-tests] external infra probe succeeded; skipping docker startup"
  else
    if [[ "$EXTERNAL_TARGET_CONFIGURED" == "1" ]]; then
      echo "[db-tests] external endpoints are configured; skipping docker fallback in auto mode (use --infra-mode docker to force local containers)" >&2
      exit 1
    fi
    echo "[db-tests] external infra probe failed; attempting docker fallback"
    start_docker_infra
    probe_external_services
  fi
fi

echo "[db-tests] ready"

if [[ "$PREPARE_ONLY" == "1" ]]; then
  echo "[db-tests] prepare-only complete"
  exit 0
fi

cd "$ROOT_DIR/nexra"
export TEST_DATABASE_URL
export DATABASE_URL
export REDIS_URL
export OPENAI_API_KEY="${OPENAI_API_KEY:-test-openai-key}"
export STRIPE_SECRET_KEY="${STRIPE_SECRET_KEY:-test-stripe-key}"
export STRIPE_WEBHOOK_SECRET="${STRIPE_WEBHOOK_SECRET:-test-webhook-secret}"
export STRIPE_DELEGATION_METER_ID="${STRIPE_DELEGATION_METER_ID:-meter_test}"
export SECRET_KEY_ENCRYPTION_KEY="${SECRET_KEY_ENCRYPTION_KEY:-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa}"

echo "[db-tests] running pytest ${PYTEST_ARGS[*]}"
"$VENV_PYTHON" -m pytest "${PYTEST_ARGS[@]}"
