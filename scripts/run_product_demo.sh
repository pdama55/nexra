#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MODE="${NEXRA_DEMO_MODE:-attach}"
PROFILE="${NEXRA_DEMO_PROFILE:-vc-12m}"
INTEGRATIONS="${NEXRA_DEMO_INTEGRATIONS:-real}"
FAILURE_POLICY="${NEXRA_DEMO_FAILURE_POLICY:-fallback}"
VERIFY_LEVEL="${NEXRA_DEMO_VERIFY:-standard}"
BASE_URL="${NEXRA_API_BASE_URL:-http://127.0.0.1:8000}"
DASHBOARD_URL="${NEXRA_DASHBOARD_BASE_URL:-http://127.0.0.1:5173}"
RESULTS_DIR="$ROOT_DIR/test-results/vc-demo/$(date +%Y%m%d-%H%M%S)"
STRICT=0
HEADED=0
OPEN_DASHBOARD=1

print_usage() {
  cat <<'EOF'
Usage:
  ./scripts/run_product_demo.sh [options]

Default behavior:
  - Runs core verification checks (unit + contracts + OpenAPI snapshot + dashboard build)
  - Runs VC demo suite in attach mode with real integrations
  - Auto-opens dashboard in the browser

Options:
  --mode attach|bootstrap
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
  ./scripts/run_product_demo.sh --mode bootstrap --verify none
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

echo "[demo] verify=$VERIFY_LEVEL mode=$MODE integrations=$INTEGRATIONS failure_policy=$FAILURE_POLICY"

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
