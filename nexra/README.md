# Nexra

The control plane for AI agent networks.

## Local Development Topology

Run API + worker + Postgres + Redis:

```bash
cd nexra
docker compose -f docker/docker-compose.yml up --build
```

Services:
- `api`: FastAPI/Uvicorn runtime (`/health` on port `8000`)
- `worker`: Celery worker queues (`webhooks,billing,anomaly,hitl,siem`)
- `postgres`: PostgreSQL + pgvector
- `redis`: Redis broker/cache

## One-Command MVP Demo (No Stress/Parity Sweep)

From repo root:

```bash
./scripts/run_product_demo.sh
```

What it does by default:
- Runs core verification checks:
  - `pytest -q tests/unit`
  - `pytest -q tests/contracts`
  - `python scripts/check_openapi_snapshot.py`
  - `npm run build` in `nexra/internal-dashboard`
- Chooses runtime mode automatically:
  - `attach` if API is already healthy at `http://127.0.0.1:8000/health`
  - `bootstrap` if API is not running
- Runs the VC demo suite with `real` integrations and `fail-fast` policy
- Auto-opens the dashboard in your browser
- In `bootstrap + real`, probes Neon + Upstash connectivity before startup

Common variants:

```bash
# Fastest path: skip checks and run demo flow immediately.
./scripts/run_product_demo.sh --verify none

# Include integration + e2e (Neon/Upstash/external infra).
./scripts/run_product_demo.sh --verify full

# Start local API/worker stack via bootstrap mode.
./scripts/run_product_demo.sh --mode bootstrap
```

## DB-Backed Test Bootstrap (Integration + E2E)

If you use managed infra (Neon + Upstash, no Docker), run:

```bash
./scripts/run_db_backed_tests.sh --infra-mode external --prepare-only
```

Then run suites against those endpoints:

```bash
./scripts/run_db_backed_tests.sh --infra-mode external
```

For local Docker-backed infra, use:

```bash
./scripts/run_db_backed_tests.sh
```

Optional: pass custom pytest args after `--`:

```bash
./scripts/run_db_backed_tests.sh -- -k delegation -x
```

Defaults (CI-aligned) can be overridden:
- `TEST_DATABASE_URL` (falls back to `DATABASE_URL`, then local default)
- `REDIS_URL` (default `redis://localhost:6379/1`)

## Railway Deployment Notes

MVP deployment uses Railway with at least:
- one API service using `docker/Dockerfile`
- one worker service using `docker/Dockerfile.worker`
- managed PostgreSQL and Redis services

Required environment variables (API + worker):
- `DATABASE_URL`
- `REDIS_URL`
- `CELERY_BROKER_URL` (optional; defaults to `REDIS_URL`)
- `OPENAI_API_KEY`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_DELEGATION_METER_ID`
- `SECRET_KEY_ENCRYPTION_KEY`

Optional alerting variables:
- `SENDGRID_API_KEY`
- `SENDGRID_BASE_URL`
- `NOTIFICATION_EMAIL_FROM`
- `ANOMALY_SLACK_WEBHOOK_URL`
- `ANOMALY_PAGERDUTY_ROUTING_KEY`
- `ANOMALY_EMAIL_RECIPIENTS`
