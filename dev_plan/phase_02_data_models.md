# Phase 02 — Data Models & Database Migrations

**Phase:** 02 / 12 | **TDD Sections:** §3 (DB Schema), §22 Block 2 | **48h Block:** Block 2 (3–6h)

> ⚠️ **Prerequisite:** Phase 01 acceptance criteria all GREEN before starting.

---

## Objective

Create all 7 SQLAlchemy ORM models, the Alembic migration with full DDL (matching TDD §3 exactly), and the **append-only trigger** on `audit_log`. Every table has working `__repr__`. Migration runs cleanly (`alembic upgrade head`). Trigger verified by attempting an UPDATE on `audit_log` (must raise exception).

---

## Claude Code Prompt

```
You are implementing the database layer for Nexra (Python 3.12, SQLAlchemy 2.x async, PostgreSQL 16 + pgvector).

TASK: Create all SQLAlchemy models and Alembic migration exactly as defined in TDD §3.

Requirements:

1. **db/session.py** — async SQLAlchemy session factory:
   - AsyncEngine via create_async_engine(DATABASE_URL)
   - AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
   - Base = DeclarativeBase()
   - get_db() async generator (FastAPI Depends)

2. **SQLAlchemy Models** — one file per model in models/:

   models/organization.py → organizations table:
   - id: UUID PK (server_default=gen_random_uuid())
   - name: VARCHAR(200) NOT NULL
   - api_key_hash: TEXT NOT NULL (bcrypt hash)
   - api_key_prefix: CHAR(16) NOT NULL UNIQUE (first 16 chars of raw key)
   - jwt_secret_enc: TEXT NOT NULL (AES-GCM encrypted 256-bit secret)
   - stripe_id: TEXT
   - stripe_connect_account_id: TEXT
   - max_delegation_depth: INT DEFAULT 5
   - plan: VARCHAR(20) DEFAULT 'starter' (starter|growth|enterprise)
   - created_at: TIMESTAMPTZ server_default=now()
   - updated_at: TIMESTAMPTZ server_default=now()

   models/agent.py → agents table:
   - id: UUID PK (gen_random_uuid())
   - org_id: UUID FK → organizations.id ON DELETE CASCADE NOT NULL
   - agent_id: VARCHAR(64) NOT NULL (regex: [a-z0-9-], max 64 chars)
   - name: VARCHAR(200) NOT NULL
   - description: TEXT NOT NULL
   - capability_type: VARCHAR(50) NOT NULL (research|analysis|generation|enrichment|validation|execution|other)
   - input_schema: JSONB NOT NULL
   - output_schema: JSONB NOT NULL
   - pricing: JSONB NOT NULL ({"per_call_usd": float})
   - sla: JSONB NOT NULL ({"p99_latency_ms": int, "availability": float})
   - webhook_url: TEXT NOT NULL
   - webhook_secret: TEXT NOT NULL
   - is_public: BOOLEAN DEFAULT FALSE
   - status: VARCHAR(20) DEFAULT 'probationary' (probationary|active|quarantined)
   - trust_score: DECIMAL(5,3) DEFAULT 0.500
   - delegation_count: INT DEFAULT 0
   - embedding: VECTOR(1536) (pgvector)
   - created_at: TIMESTAMPTZ server_default=now()
   - updated_at: TIMESTAMPTZ server_default=now()
   - UNIQUE(org_id, agent_id)

   models/policy.py → policies table:
   - id: UUID PK
   - org_id: UUID FK → organizations.id ON DELETE CASCADE
   - name: VARCHAR(200) NOT NULL
   - rule_yaml: TEXT NOT NULL
   - priority: INT DEFAULT 100
   - enabled: BOOLEAN DEFAULT TRUE
   - version: INT DEFAULT 1
   - created_at: TIMESTAMPTZ
   - updated_at: TIMESTAMPTZ

   models/delegation.py → delegations table:
   - id: UUID PK
   - caller_org_id: UUID FK → organizations.id
   - caller_agent_id: VARCHAR(64) NOT NULL
   - callee_org_id: UUID FK → organizations.id
   - callee_agent_id: VARCHAR(64) NOT NULL
   - task: JSONB NOT NULL
   - task_hash: VARCHAR(64) NOT NULL (SHA-256 hex)
   - context_scope: JSONB DEFAULT '[]'
   - status: VARCHAR(30) DEFAULT 'initiated' (initiated|in_flight|completed|failed|blocked|pending_approval|timeout)
   - policy_id: UUID FK → policies.id NULLABLE
   - policy_version: INT NULLABLE
   - policy_decision: VARCHAR(10) NULLABLE (allow|block|pause)
   - budget_cap_usd: DECIMAL(10,4) NOT NULL
   - estimated_cost_usd: DECIMAL(10,4)
   - actual_cost_usd: DECIMAL(10,4)
   - callback_url: TEXT NULLABLE
   - result: JSONB NULLABLE
   - delegation_depth: INT DEFAULT 0
   - parent_delegation_id: UUID FK → delegations.id NULLABLE
   - timeout_ms: INT DEFAULT 30000
   - created_at: TIMESTAMPTZ server_default=now()
   - completed_at: TIMESTAMPTZ NULLABLE

   models/audit_log.py → audit_log table:
   - id: UUID PK
   - org_id: UUID FK → organizations.id NOT NULL
   - delegation_id: UUID FK → delegations.id NULLABLE
   - event_type: VARCHAR(50) NOT NULL
   - actor_agent_id: VARCHAR(64) NULLABLE
   - target_agent_id: VARCHAR(64) NULLABLE
   - details: JSONB NOT NULL DEFAULT '{}'
   - cost_usd: DECIMAL(10,4) NULLABLE
   - created_at: TIMESTAMPTZ server_default=now() NOT NULL

   models/agent_budget.py → agent_budgets table:
   - id: UUID PK
   - agent_id: VARCHAR(64) NOT NULL
   - org_id: UUID FK → organizations.id NOT NULL
   - period: DATE NOT NULL
   - period_type: VARCHAR(10) NOT NULL (daily|monthly)
   - cap_usd: DECIMAL(10,4) DEFAULT 999999
   - spent_usd: DECIMAL(10,4) DEFAULT 0
   - updated_at: TIMESTAMPTZ server_default=now()
   - UNIQUE(agent_id, org_id, period, period_type)

   models/trust_score_event.py → trust_score_events table:
   - id: UUID PK
   - agent_id: VARCHAR(64) NOT NULL
   - org_id: UUID FK → organizations.id NOT NULL
   - delegation_id: UUID FK → delegations.id NOT NULL
   - score_before: DECIMAL(5,3) NOT NULL
   - score_after: DECIMAL(5,3) NOT NULL
   - components: JSONB NOT NULL  ({"success_rate":float, "sla_compliance":float, "cost_accuracy":float, "policy_violations_inverse":float})
   - created_at: TIMESTAMPTZ server_default=now()

3. **Alembic Migration** db/migrations/versions/0001_initial.py:
   - Run `alembic revision --autogenerate -m "initial"` then verify/fix the output
   - Must include: CREATE EXTENSION IF NOT EXISTS vector
   - Must include: IVFFlat index on agents.embedding — CREATE INDEX agents_embedding_idx ON agents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 32)
   - Must include: audit_log immutability trigger:
     CREATE OR REPLACE FUNCTION prevent_audit_log_mutation()
     RETURNS TRIGGER AS $$
     BEGIN RAISE EXCEPTION 'audit_log is append-only: % on row % is not permitted', TG_OP, OLD.id; END;
     $$ LANGUAGE plpgsql;
     CREATE TRIGGER trg_audit_log_immutable BEFORE UPDATE OR DELETE ON audit_log FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_mutation();

4. **models/__init__.py** — import all models so Alembic can see them.

5. All models must have __repr__ returning the key identifier (e.g., f"<Agent {self.agent_id}>").

AGENTS.md protocol: after creating each model, verify it imports without error.
```

---

## Guardrails

- ✅ All PKs are `UUID` with `gen_random_uuid()` server default
- ✅ All timestamps are `TIMESTAMPTZ` (never `TIMESTAMP` without timezone)
- ✅ `agents.embedding` must be `VECTOR(1536)` from pgvector — import `from pgvector.sqlalchemy import Vector`
- ✅ `audit_log` trigger must be in the migration — it is the primary enforcement mechanism
- ✅ `UNIQUE(org_id, agent_id)` on `agents` table — prevents duplicate agent slugs per org
- ✅ `UNIQUE(agent_id, org_id, period, period_type)` on `agent_budgets` — needed for upsert
- ✅ `agents.trust_score` is `DECIMAL(5,3)` (not FLOAT) — precision matters for financial safety
- ❌ Do NOT use `SERIAL` or `BIGINT` for any PK
- ❌ Do NOT use naive `datetime` — always `timezone.utc` aware
- ❌ Do NOT add `updated_at` to `audit_log` — it is append-only
- ✅ `alembic upgrade head` must run clean with zero errors

---

## Acceptance Criteria

```bash
# 1. Migration runs cleanly
poetry run alembic upgrade head
# → Running upgrade ... -> 0001_initial, initial

# 2. All models importable
poetry run python -c "from models.organization import Organization; from models.agent import Agent; from models.delegation import Delegation; print('OK')"

# 3. pgvector extension enabled
docker exec nexra-postgres-1 psql -U nexra -d nexra -c "\dx" | grep vector
# → vector | pgvector extension

# 4. CRITICAL: Audit log trigger blocks mutation
docker exec nexra-postgres-1 psql -U nexra -d nexra -c "
  INSERT INTO audit_log (org_id, event_type, details) VALUES (gen_random_uuid(), 'test', '{}');
  UPDATE audit_log SET event_type = 'hacked' WHERE event_type = 'test';
"
# → ERROR: audit_log is append-only: UPDATE on row ... is not permitted

# 5. IVFFlat index exists
docker exec nexra-postgres-1 psql -U nexra -d nexra -c "\di agents_embedding_idx"
# → agents_embedding_idx | agents | ivfflat
```

---

## Test Cases

```bash
# Unit: model __repr__ works
poetry run pytest tests/unit/test_models.py -v

# Integration: DB round-trip — create Organization, Agent, verify FK constraint
poetry run pytest tests/integration/test_models.py -v

# Integration: audit_log trigger
poetry run pytest tests/integration/test_audit_trigger.py -v
# T-013: INSERT succeeds; UPDATE raises exception
# T-014: DELETE raises exception
```

**Write these test files as part of this phase:**
- `tests/unit/test_models.py` — instantiate models in memory, check `__repr__`
- `tests/integration/test_models.py` — DB create/read round-trips, FK cascade
- `tests/integration/test_audit_trigger.py` — Tests T-013 and T-014 from TDD §20.2
