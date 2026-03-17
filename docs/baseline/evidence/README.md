# Convergence Evidence Pack

Generated: 2026-03-17
Branch: `main`

## Commands Executed

1. `./scripts/validate_convergence.sh`
2. `cd nexra && ./venv/bin/python -m pytest -q tests/integration tests/e2e`
3. `cd nexra && ./venv/bin/python ../scripts/check_openapi_snapshot.py`
4. `cd nexra && npm --prefix internal-dashboard run build`
5. `cd nexra && npm --prefix sdk/nexra-ts run build`
6. `cd nexra/sdk/nexra-ts && npm pack --dry-run`

## Output Logs

- `validate_convergence.log`
- `integration_e2e.log`
- `openapi_snapshot_check.log`
- `dashboard_build.log`
- `sdk_build.log`
- `sdk_pack_dry_run.log`

## Operational Docs

- `POST_RELEASE_VERIFICATION_RUNBOOK.md`

## Result Summary

- Convergence validation script: passed
- Integration + E2E suites: passed (`42 passed`)
- OpenAPI snapshot gate: passed
- Dashboard build: passed
- TS SDK build: passed
- TS SDK pack dry-run: passed (LICENSE + README + dist artifacts present)
