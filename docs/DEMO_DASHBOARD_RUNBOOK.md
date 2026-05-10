# Demo + Dashboard Runbook

This runbook is the canonical step-by-step guide to run the Nexra demo and load the internal dashboard with data.

## 1. Prerequisites

Run from repo root:

```bash
cd /Users/parthdama/Documents/Nexra
```

Ensure these are available:

1. `nexra/venv/bin/python`
2. Node modules for dashboard (`nexra/internal-dashboard/node_modules`)
3. API on `:8000` and dashboard on `:5173` (or run in bootstrap mode below)
4. Docker runtime available for DB-backed integration/e2e checks (`scripts/run_db_backed_tests.sh` now auto-attempts Docker Desktop/Colima/Rancher Desktop startup)

Optional bootstrap for local env file:

```bash
cp nexra/.env.example nexra/.env
```

## 2. Fastest Demo Run

Use the product wrapper:

```bash
./scripts/run_product_demo.sh --verify none
```

This auto-selects attach/bootstrap and writes artifacts to:

`test-results/vc-demo/<timestamp>/`

## 3. Direct VC Demo Run

Bootstrap mode (starts stack + dashboard):

```bash
NEXRA_OPEN_DASHBOARD=1 ./scripts/run_vc_demo.sh --mode bootstrap --open-dashboard
```

Attach mode (use existing running services):

```bash
./scripts/run_vc_demo.sh --mode attach
```

## 4. Integration Modes

Mock mode:

```bash
./scripts/run_vc_demo.sh --mode attach --integrations mock --failure-policy fail-fast
```

Hybrid mode:

```bash
./scripts/run_vc_demo.sh --mode attach --integrations hybrid --failure-policy fail-fast
```

Real mode (strict env contract required):

```bash
export SENDGRID_API_KEY="..."
export ANOMALY_PAGERDUTY_ROUTING_KEY="..."
export PAGERDUTY_EVENTS_BASE_URL="https://events.pagerduty.com"
./scripts/run_vc_demo.sh --mode attach --integrations real --failure-policy fail-fast --strict
```

Env lookup order used by demo scripts:

1. Process environment
2. `.env`
3. `.env.local`
4. `nexra/.env`
5. `nexra/.env.local`

## 5. Open Dashboard With Session

If dashboard opens but shows no data, bootstrap session via URL params.

Generate latest buyer API key from demo artifacts:

```bash
LATEST=$(ls -td test-results/vc-demo/* | head -n 1)
KEY=$(python3 - <<'PY' "$LATEST/vc_org_profile.json"
import json,sys
obj=json.load(open(sys.argv[1],'r',encoding='utf-8'))
print(((obj.get('orgs') or {}).get('buyer') or {}).get('api_key') or '')
PY
)
open "http://localhost:5173/?nexra_api_key=${KEY}&nexra_user_email=admin@nexra.local"
```

Important: use `localhost:5173` (not `127.0.0.1:5173`) if your Vite server is bound to IPv6 localhost.

## 6. Health Checks

API:

```bash
curl -sS http://127.0.0.1:8000/health
```

Dashboard:

```bash
curl -sS http://localhost:5173 | head
```

## 7. If Dashboard Is Empty

1. Verify `localStorage` has `nexra_api_key` and `nexra_user_email`.
2. Re-open with session URL params from section 5.
3. In browser devtools, clear stale keys:

```js
localStorage.removeItem('nexra_api_key');
localStorage.removeItem('nexra_user_email');
location.reload();
```

4. Confirm auth works:

```bash
curl -sS -i http://localhost:5173/v1/orgs/session -H "Authorization: Bearer $KEY" -H "X-User-Email: admin@nexra.local" | head -n 20
```

## 8. Key Artifacts to Inspect

From latest run directory (`test-results/vc-demo/<timestamp>/`):

1. `summary.json`
2. `capability_matrix_result.json`
3. `go_no_go.json`
4. `preflight.json`
5. `phase_status.json`
6. `report.md`

Command:
./scripts/run_product_demo.sh --verify none
