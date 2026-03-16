#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

pushd "$ROOT/nexra" >/dev/null
if command -v poetry >/dev/null 2>&1; then
  poetry run ruff check .
  poetry run mypy \
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
./venv/bin/python -m pytest -q tests/unit
./venv/bin/python -m pytest -q tests/contracts
popd >/dev/null

pushd "$ROOT/nexra/internal-dashboard" >/dev/null
npx tsc -b --pretty false
npm run build
popd >/dev/null

pushd "$ROOT/nexra/sdk/nexra-ts" >/dev/null
npm run build
popd >/dev/null

echo "Convergence validation checks passed"
