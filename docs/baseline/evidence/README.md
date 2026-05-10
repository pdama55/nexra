# Convergence Evidence Pack

Generated: 2026-04-07
Branch: `main`

## Commands Executed

1. `./scripts/validate_convergence.sh`
2. `./scripts/run_db_backed_tests.sh --infra-mode auto`
3. `cd nexra && ./venv/bin/python ../scripts/check_openapi_snapshot.py`
4. `cd nexra && npm --prefix internal-dashboard run build`
5. `cd nexra && npm --prefix sdk/nexra-ts run build`
6. `cd nexra/sdk/nexra-ts && npm pack --dry-run`
7. `./scripts/run_vc_demo.sh --mode attach --integrations real --failure-policy fail-fast --strict`
8. `./scripts/branch_protection_gate.sh --branch main`

## Output Logs

- `validate_convergence.log`
- `integration_e2e.log`
- `openapi_snapshot_check.log`
- `dashboard_build.log`
- `sdk_build.log`
- `sdk_pack_dry_run.log`
- `vc_real_run.log`
- `branch_protection_status.json`

## Operational Docs

- `POST_RELEASE_VERIFICATION_RUNBOOK.md`

## Result Summary

- Convergence validation script: pass (unit/contracts/openapi/docs drift, DB-backed integration/e2e, dashboard build, TS SDK build)
- Integration + E2E suites: pass (`48 passed`)
- OpenAPI snapshot gate: passed
- Dashboard build: passed
- TS SDK build: passed
- TS SDK pack dry-run: passed (LICENSE + README + dist artifacts present)
- VC real-run precondition gate: failed early as expected when required real-integration env contract is missing (`SENDGRID_API_KEY`, `ANOMALY_PAGERDUTY_ROUTING_KEY`, `PAGERDUTY_EVENTS_BASE_URL`)
- Branch protection governance gate: currently `blocked_by_plan` for this repository (`branch_protection_status.json`) due GitHub plan restriction on private-repo branch protection
