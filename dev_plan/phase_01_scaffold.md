# Phase 01 — Project Scaffold

**Phase:** 01 / 12 | **TDD Sections:** §2 (Repo Structure), §19 (Config), §21.3 (Docker Compose) | **48h Block:** Block 1 (0–3h)

---

## Objective

Stand up an empty but fully runnable monorepo: directory structure, `pyproject.toml`, Docker Compose with Postgres 16 + pgvector + Redis 7, Alembic initialized, and a passing `/health` stub. No business logic yet. Goal is `docker compose up` healthy and `alembic upgrade head` running cleanly.

---

## Claude Code Prompt

```
You are building the Nexra backend — a Python 3.12 FastAPI control plane for AI agent networks.

TASK: Scaffold the full repository structure as defined in the TDD §2. Do NOT implement any business logic yet.

Requirements:
1. Create the full directory structure from TDD §2 (api/, services/, models/, db/, workers/, core/, sdk/, tests/, docker/, infra/)
2. Create pyproject.toml with Poetry. Dependencies:
   - fastapi==0.115.*
   - uvicorn[standard]
   - sqlalchemy[asyncio]==2.x
   - asyncpg
   - alembic
   - pydantic==2.*
   - pydantic-settings
   - redis[hiredis]
   - httpx
   - python-jose[cryptography]
   - passlib[bcrypt]
   - celery[redis]
   - openai
   - stripe
   - jsonschema
   - pyyaml
   - cryptography
   Dev deps: pytest, pytest-asyncio, httpx (for testing), pytest-cov
3. Create docker/docker-compose.yml exactly as in TDD §21.3:
   - api service (build from Dockerfile, hot reload with --reload)
   - worker service
   - postgres: pgvector/pgvector:pg16, POSTGRES_DB=nexra, POSTGRES_USER=nexra, POSTGRES_PASSWORD=nexra, healthcheck
   - redis: redis:7-alpine, healthcheck
4. Create docker/Dockerfile exactly as in TDD §21.1 (multi-stage: builder + runtime)
5. Create core/config.py with Pydantic Settings from TDD §19.2 — all required env vars
6. Create .env.example with all variables from TDD §19.1 (empty values)
7. Initialize Alembic: alembic init db/migrations. Set sqlalchemy.url in alembic.ini to read from env.
8. Create api/main.py — minimal FastAPI app factory. Register /health router only for now.
9. Create api/routers/health.py — GET /health returns {"status": "ok", "components": {"db": "ok", "redis": "ok"}}
10. Create all __init__.py files needed.

Do NOT create any models, services, or auth yet. Stub all missing module imports with `pass`.

AGENTS.md protocol applies: verify each file compiles before moving to next.
```

---

## Guardrails

- ✅ Use **Poetry** for dependency management (`pyproject.toml`)
- ✅ Python version: `python = "^3.12"`
- ✅ FastAPI version: `fastapi = "^0.115"`
- ✅ Pydantic v2 only — no v1 imports
- ✅ `docker-compose.yml` must use `pgvector/pgvector:pg16` image (not plain postgres)
- ✅ Postgres healthcheck: `pg_isready -U nexra`
- ✅ Redis healthcheck: `redis-cli ping`
- ❌ Do NOT hardcode credentials — read from environment via `core/config.py`
- ❌ Do NOT create any SQLAlchemy models yet (Phase 02)
- ❌ Do NOT implement any auth yet (Phase 03)
- ✅ `alembic.ini` `sqlalchemy.url` must read from `DATABASE_URL` env var

---

## Acceptance Criteria

```bash
# 1. Docker Compose starts healthy
docker compose -f docker/docker-compose.yml up -d
docker compose ps  # all services "healthy"

# 2. Postgres + pgvector reachable
docker exec -it nexra-postgres-1 psql -U nexra -c "CREATE EXTENSION IF NOT EXISTS vector;"
# → CREATE EXTENSION

# 3. Alembic runs (no migrations yet, just init check)
poetry run alembic upgrade head
# → No errors

# 4. Health endpoint responds
curl http://localhost:8000/health
# → {"status": "ok", "components": {"db": "ok", "redis": "ok"}}

# 5. App imports compile
poetry run python -c "from api.main import app; print('OK')"
poetry run python -c "from core.config import get_settings; print(get_settings())"
```

---

## Test Cases

```bash
# Unit: Pydantic settings validation
poetry run pytest tests/unit/test_config.py -v
# → Validates all required env vars raise ValidationError when missing

# Contract: health endpoint schema
poetry run pytest tests/contracts/test_health.py -v
# → GET /health returns 200 with {"status": "ok"}
```

**Write these test files as part of this phase:**
- `tests/unit/test_config.py` — test that missing `DATABASE_URL` raises `ValidationError`
- `tests/contracts/test_health.py` — test `/health` returns 200 with `status: "ok"`
