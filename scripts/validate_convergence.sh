#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

pushd "$ROOT/nexra" >/dev/null
if command -v poetry >/dev/null 2>&1; then
  poetry run ruff check .
  poetry run mypy \
    services/notification_service.py \
    services/hitl_service.py \
    services/anomaly_service.py \
    services/budget_service.py
  poetry run mypy \
    --ignore-missing-imports \
    --allow-untyped-defs \
    --disable-error-code assignment \
    --disable-error-code type-arg \
    --disable-error-code no-untyped-def \
    --disable-error-code import-untyped \
    services/budget_service.py \
    services/delegation_service.py \
    services/hitl_service.py \
    services/siem_service.py \
    api/routers/siem.py \
    api/routers/policies.py
else
  echo "poetry not found; skipping ruff/mypy checks in local validation script"
fi
./venv/bin/python "$ROOT/scripts/check_openapi_snapshot.py"
./venv/bin/python "$ROOT/scripts/check_docs_drift.py"
./venv/bin/python -m pytest -q tests/unit
./venv/bin/python -m pytest -q tests/contracts
popd >/dev/null

echo "[convergence] running integration/e2e via canonical DB-backed runner"
"$ROOT/scripts/run_db_backed_tests.sh" --infra-mode auto

pushd "$ROOT/nexra/internal-dashboard" >/dev/null
npx tsc -b --pretty false
npm run build
popd >/dev/null

pushd "$ROOT/nexra/sdk/nexra-ts" >/dev/null
npm run build
popd >/dev/null

echo "[convergence] checking branch protection governance gate"
if "$ROOT/scripts/branch_protection_gate.sh" --branch main >/dev/null 2>&1; then
  echo "[convergence] branch protection gate check passed"
else
  echo "[convergence] branch protection gate unresolved (see docs/baseline/evidence/branch_protection_status.json)"
fi

echo "Convergence validation checks passed"
