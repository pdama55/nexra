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
