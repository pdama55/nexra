# Phase 1 — Project Scaffold, Docker, Database Schema, Alembic

> **TDD Sections**: §1 (Architecture Overview), §2 (Repository Structure), §3 (Database Schema), §19 (Environment Config — partial), §23 (Error Handling — NexraError class)
>
> **48-Hour Block**: Hours 0–6
>
> **Depends On**: Nothing — this is the first phase.

---

## 1. Prerequisites

- Python 3.12 installed locally
- Docker and Docker Compose installed
- Poetry 1.8+ installed (`pip install poetry==1.8.0`)
- Git initialized in the project root

---

## 2. Objective

Deliver a fully bootable local development environment:

- `docker compose up` starts PostgreSQL 16 (with pgvector), Redis 7, and the FastAPI API — all healthy
- `alembic upgrade head` creates all 7 tables with correct constraints, indexes, and the audit_log immutability trigger
- All SQLAlchemy ORM models are importable and mapped to the database
- The NexraError exception class and Pydantic Settings config are in place
- A minimal FastAPI app factory exists (no routes yet — those come in Phase 2+)

---

## 3. Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| ORM | SQLAlchemy 2.x async with asyncpg | TDD §1.2 mandates this. Async-first for FastAPI compatibility. |
| Migrations | Alembic 1.x | TDD §1.2. All schema changes versioned. No manual SQL in production. |
| UUID PKs | `gen_random_uuid()` via pgcrypto | TDD §3.1. No integer sequences. |
| Vector type | pgvector `VECTOR(1536)` | TDD §3.1. Required for semantic discovery. |
| Config | Pydantic Settings v2 | TDD §19.2. Reads `.env` file. Type-safe. |
| Docker base | `python:3.12-slim` | TDD §21.1. Multi-stage build. Non-root user. |
| Postgres image | `pgvector/pgvector:pg16` | Includes pgvector extension pre-installed. |

---

## 4. File-by-File Implementation Guide

### 4.1 `pyproject.toml`

**Path**: `nexra/pyproject.toml` (project root)

```toml
[tool.poetry]
name = "nexra"
version = "0.1.0"
description = "The control plane for AI agent networks"
authors = ["Parth"]
readme = "README.md"
packages = [
    { include = "api" },
    { include = "services" },
    { include = "models" },
    { include = "db" },
    { include = "core" },
    { include = "workers" },
]

[tool.poetry.dependencies]
python = "^3.12"
fastapi = "^0.115"
uvicorn = { extras = ["standard"], version = "^0.32" }
pydantic = { extras = ["email"], version = "^2.9" }
pydantic-settings = "^2.5"
sqlalchemy = { extras = ["asyncio"], version = "^2.0" }
asyncpg = "^0.30"
alembic = "^1.14"
pgvector = "^0.3"
redis = { extras = ["hiredis"], version = "^5.2" }
celery = { extras = ["redis"], version = "^5.4" }
httpx = "^0.28"
python-jose = { extras = ["cryptography"], version = "^3.3" }
passlib = { extras = ["bcrypt"], version = "^1.7" }
cryptography = "^43"
openai = "^1.55"
stripe = "^11"
pyyaml = "^6.0"
jsonschema = "^4.23"
sentry-sdk = { extras = ["fastapi"], version = "^2.18" }

[tool.poetry.group.dev.dependencies]
pytest = "^8.0"
pytest-asyncio = "^0.24"
httpx = "^0.28"
factory-boy = "^3.3"
ruff = "^0.8"
mypy = "^1.13"
pre-commit = "^4.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.ruff]
target-version = "py312"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM", "TCH"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### 4.2 `.env.example`

**Path**: `nexra/.env.example`

```env
# === REQUIRED ===
DATABASE_URL=postgresql+asyncpg://nexra:nexra@localhost:5432/nexra
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=sk-your-openai-key
STRIPE_SECRET_KEY=sk_test_your-stripe-key
STRIPE_WEBHOOK_SECRET=whsec_your-webhook-secret
STRIPE_DELEGATION_METER_ID=mtr_your-meter-id
SECRET_KEY_ENCRYPTION_KEY=0000000000000000000000000000000000000000000000000000000000000000

# === OPTIONAL ===
SENTRY_DSN=
ENVIRONMENT=development
LOG_LEVEL=DEBUG
RATE_LIMIT_GROWTH_RPM=1000
RATE_LIMIT_STARTER_RPM=100
MAX_DELEGATION_DEPTH_DEFAULT=5
WEBHOOK_TIMEOUT_DEFAULT_MS=30000
HIL_APPROVAL_TTL_HOURS=24
ANOMALY_SIGMA_THRESHOLD=3.0
CELERY_BROKER_URL=
```

### 4.3 `.gitignore`

**Path**: `nexra/.gitignore`

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.eggs/
*.egg
.env
.env.local
.venv/
venv/
.mypy_cache/
.ruff_cache/
.pytest_cache/
htmlcov/
.coverage
*.db
*.sqlite3
node_modules/
```

### 4.4 `core/__init__.py`

**Path**: `nexra/core/__init__.py`

Empty file. Required for Python package.

### 4.5 `core/config.py`

**Path**: `nexra/core/config.py`

This file defines all environment configuration using Pydantic Settings. Every environment variable from TDD §19.1 is represented.

```python
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Required
    database_url: str
    redis_url: str
    openai_api_key: str
    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_delegation_meter_id: str
    secret_key_encryption_key: str  # 64 hex chars = 32 bytes for AES-256-GCM

    # Optional with defaults
    sentry_dsn: str | None = None
    environment: str = "development"
    log_level: str = "INFO"
    rate_limit_growth_rpm: int = 1000
    rate_limit_starter_rpm: int = 100
    max_delegation_depth_default: int = 5
    webhook_timeout_default_ms: int = 30000
    hil_approval_ttl_hours: int = 24
    anomaly_sigma_threshold: float = 3.0
    celery_broker_url: str | None = None

    @property
    def celery_broker(self) -> str:
        return self.celery_broker_url or self.redis_url

    model_config = {"env_file": ".env", "case_sensitive": False}


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**Guardrails**:
- `secret_key_encryption_key` MUST be validated as exactly 64 hex characters (32 bytes). Add a `@field_validator` for this.
- Do NOT import Settings at module level in other files — always use `get_settings()` to enable test overrides.

### 4.6 `core/errors.py`

**Path**: `nexra/core/errors.py`

The base exception class used across the entire application. From TDD §23.1.

```python
class NexraError(Exception):
    """Base exception for all Nexra application errors.

    Attributes:
        status_code: HTTP status code to return.
        code: Machine-readable error code string (e.g., 'POLICY_BLOCKED').
        message: Human-readable error message.
        details: Optional dict with additional context.
    """

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)
```

**Error codes to define as constants** (in the same file):

```python
# Auth errors
UNAUTHORIZED = "UNAUTHORIZED"
INVALID_DELEGATION_TOKEN = "INVALID_DELEGATION_TOKEN"
AGENT_QUARANTINED = "AGENT_QUARANTINED"

# Validation errors
INVALID_SCHEMA = "INVALID_SCHEMA"
INVALID_WEBHOOK_URL = "INVALID_WEBHOOK_URL"
INVALID_AGENT_ID = "INVALID_AGENT_ID"
INVALID_REQUEST = "INVALID_REQUEST"
MAX_DEPTH_EXCEEDED = "MAX_DEPTH_EXCEEDED"
SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"
OUTPUT_SCHEMA_FAILED = "OUTPUT_SCHEMA_FAILED"

# Policy errors
POLICY_BLOCKED = "POLICY_BLOCKED"

# Budget errors
BUDGET_EXCEEDED = "BUDGET_EXCEEDED"

# Delegation errors
AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
DELEGATION_NOT_FOUND = "DELEGATION_NOT_FOUND"
POLICY_NOT_FOUND = "POLICY_NOT_FOUND"
DELEGATION_TIMEOUT = "DELEGATION_TIMEOUT"
DELEGATION_ALREADY_COMPLETE = "DELEGATION_ALREADY_COMPLETE"

# External errors
CALLEE_WEBHOOK_FAILED = "CALLEE_WEBHOOK_FAILED"
WEBHOOK_SIGNATURE_REJECTED = "WEBHOOK_SIGNATURE_REJECTED"
EMBEDDING_SERVICE_UNAVAILABLE = "EMBEDDING_SERVICE_UNAVAILABLE"

# Rate limit
RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

# Internal
INTERNAL_ERROR = "INTERNAL_ERROR"
```

### 4.7 `models/base.py`

**Path**: `nexra/models/base.py`

Defines the SQLAlchemy declarative base and a UUID primary key mixin used by all models.

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UUIDMixin:
    """Mixin that adds a UUID primary key to any model."""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )


class TimestampMixin:
    """Mixin that adds created_at and updated_at columns."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
```

**Guardrails**:
- Always use `UUID(as_uuid=True)` — never store UUIDs as strings.
- Always use `DateTime(timezone=True)` — never use naive datetimes.
- The `server_default=func.gen_random_uuid()` requires the `pgcrypto` extension. The migration must create this extension.

### 4.8 `models/organization.py`

**Path**: `nexra/models/organization.py`

```python
import uuid
from sqlalchemy import String, Text, Integer, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import Base, UUIDMixin, TimestampMixin


class Organization(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    api_key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    api_key_prefix: Mapped[str] = mapped_column(
        String(16), nullable=False, index=True
    )  # first 16 chars of raw key for O(1) lookup
    stripe_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="starter"
    )
    approval_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    jwt_secret_enc: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # AES-256-GCM encrypted 256-bit secret
    delegation_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    # Relationships
    agents = relationship("Agent", back_populates="organization", cascade="all, delete-orphan")
    policies = relationship("Policy", back_populates="organization", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "plan IN ('starter', 'growth', 'enterprise')",
            name="ck_organizations_plan",
        ),
    )
```

**Key fields not in PRD but in TDD**:
- `api_key_prefix`: First 16 chars of the raw API key, stored separately for O(1) lookup without full-table bcrypt scan (TDD §4.3 note).
- `jwt_secret_enc`: AES-256-GCM encrypted per-org secret for signing delegation JWTs (TDD §4.4).
- `delegation_count`: Running total for analytics (TDD §3.2).

### 4.9 `models/agent.py`

**Path**: `nexra/models/agent.py`

```python
import uuid
from decimal import Decimal
from sqlalchemy import (
    Text, Integer, Boolean, CheckConstraint, ForeignKey,
    UniqueConstraint, Index, Numeric,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from models.base import Base, UUIDMixin, TimestampMixin


class Agent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "agents"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    capability_type: Mapped[str] = mapped_column(Text, nullable=False)
    input_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    webhook_url: Mapped[str] = mapped_column(Text, nullable=False)
    webhook_secret: Mapped[str] = mapped_column(Text, nullable=False)
    pricing: Mapped[dict] = mapped_column(JSONB, nullable=False)
    sla: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    embedding = mapped_column(Vector(1536), nullable=True)
    trust_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False, server_default="1.000"
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="probationary"
    )
    delegation_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    # Relationships
    organization = relationship("Organization", back_populates="agents")

    __table_args__ = (
        UniqueConstraint("org_id", "agent_id", name="uq_agents_org_agent"),
        CheckConstraint(
            "capability_type IN ('research','analysis','generation','enrichment','validation','execution','other')",
            name="ck_agents_capability_type",
        ),
        CheckConstraint(
            "webhook_url LIKE 'https://%'",
            name="ck_agents_webhook_https",
        ),
        CheckConstraint(
            "trust_score >= 0.000 AND trust_score <= 1.000",
            name="ck_agents_trust_score_range",
        ),
        CheckConstraint(
            "status IN ('active','probationary','quarantined')",
            name="ck_agents_status",
        ),
        Index("ix_agents_embedding", "embedding", postgresql_using="ivfflat",
              postgresql_with={"lists": 100},
              postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("ix_agents_cap_type", "capability_type", "status"),
        Index("ix_agents_org_status", "org_id", "status"),
        Index("ix_agents_is_public", "is_public",
              postgresql_where="is_public = TRUE"),
    )
```

**Guardrails**:
- The `embedding` column uses `pgvector.sqlalchemy.Vector(1536)`. Import from `pgvector.sqlalchemy`, NOT from `sqlalchemy`.
- The IVFFlat index requires at least 100 rows to be effective. For MVP with fewer agents, the index still works but with lower recall. This is acceptable.
- `webhook_url` CHECK constraint enforces HTTPS at the database level as a defense-in-depth measure. Application-layer validation also checks this.

### 4.10 `models/policy.py`

**Path**: `nexra/models/policy.py`

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import Text, Integer, Boolean, ForeignKey, UniqueConstraint, Index, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import Base, UUIDMixin


class Policy(UUIDMixin, Base):
    __tablename__ = "policies"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="100"
    )
    rule_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    organization = relationship("Organization", back_populates="policies")

    __table_args__ = (
        UniqueConstraint("org_id", "name", "version", name="uq_policies_org_name_version"),
        Index(
            "ix_policies_org_priority",
            "org_id", "priority",
            postgresql_where="enabled = TRUE",
        ),
    )
```

**Note**: Policy does NOT use `TimestampMixin` because it only has `created_at` (no `updated_at`). Policies are versioned — updates create new rows with incremented version numbers. The `created_at` column is explicitly defined with `DateTime(timezone=True)`, `server_default=func.now()`, and a Python-side default matching the TimestampMixin pattern.

### 4.11 `models/delegation.py`

**Path**: `nexra/models/delegation.py`

```python
import uuid
from decimal import Decimal
from datetime import datetime
from sqlalchemy import (
    Text, Integer, ForeignKey, CheckConstraint, Index, Numeric,
    DateTime, ARRAY,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from models.base import Base, UUIDMixin


class Delegation(UUIDMixin, Base):
    __tablename__ = "delegations"

    caller_org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    caller_agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    callee_org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=True,
    )
    callee_agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    task: Mapped[dict] = mapped_column(JSONB, nullable=False)
    task_hash: Mapped[str] = mapped_column(Text, nullable=False)
    context_scope: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policies.id"),
        nullable=True,
    )
    policy_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    policy_decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    budget_cap_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    actual_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    callback_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    delegation_depth: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    parent_delegation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("delegations.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "policy_decision IN ('allow','block','pause')",
            name="ck_delegations_policy_decision",
        ),
        CheckConstraint(
            "status IN ('pending','in_flight','completed','failed','timeout','blocked','pending_approval')",
            name="ck_delegations_status",
        ),
        Index("ix_delegations_caller", "caller_org_id", "caller_agent_id", "created_at"),
        Index("ix_delegations_callee", "callee_agent_id", "created_at"),
        Index("ix_delegations_status", "status", "created_at"),
        Index(
            "ix_delegations_parent", "parent_delegation_id",
            postgresql_where="parent_delegation_id IS NOT NULL",
        ),
    )
```

### 4.12 `models/audit_log.py`

**Path**: `nexra/models/audit_log.py`

```python
import uuid
from decimal import Decimal
from datetime import datetime
from sqlalchemy import Text, ForeignKey, Index, Numeric, DateTime
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from models.base import Base, UUIDMixin


class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_log"

    delegation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("delegations.id"),
        nullable=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_agent_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_agent_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False)
    cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    # NO updated_at — this table is append-only

    __table_args__ = (
        # event_type CHECK enforced at DB level
        # The immutability trigger is created in the migration, not here
        Index("ix_audit_log_org", "org_id", "created_at"),
        Index("ix_audit_log_delegation", "delegation_id"),
        Index("ix_audit_log_event_type", "event_type", "created_at"),
        Index("ix_audit_log_agent", "actor_agent_id", "created_at"),
    )
```

**Critical**: The immutability trigger (BEFORE UPDATE OR DELETE) is NOT defined in the ORM model. It is created in the Alembic migration using raw SQL. The ORM model intentionally has no `updated_at` column.

### 4.13 `models/agent_budget.py`

**Path**: `nexra/models/agent_budget.py`

```python
import uuid
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy import Text, Date, ForeignKey, Numeric, DateTime, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from models.base import Base


class AgentBudget(Base):
    __tablename__ = "agent_budgets"

    # Composite primary key — no UUID mixin
    agent_id: Mapped[str] = mapped_column(Text, primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    period: Mapped[date] = mapped_column(Date, primary_key=True)
    period_type: Mapped[str] = mapped_column(Text, primary_key=True)
    cap_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    spent_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "period_type IN ('daily', 'monthly')",
            name="ck_agent_budgets_period_type",
        ),
        Index("ix_agent_budgets_agent", "agent_id", "org_id", "period"),
    )
```

**Note**: This model uses a composite primary key (agent_id, org_id, period, period_type) — it does NOT use the UUIDMixin.

### 4.14 `models/trust_score_event.py`

**Path**: `nexra/models/trust_score_event.py`

```python
import uuid
from decimal import Decimal
from datetime import datetime
from sqlalchemy import Text, ForeignKey, Numeric, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from models.base import Base, UUIDMixin


class TrustScoreEvent(UUIDMixin, Base):
    __tablename__ = "trust_score_events"

    agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    delegation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("delegations.id"),
        nullable=True,
    )
    score_before: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False
    )
    score_after: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False
    )
    components: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    __table_args__ = (
        Index("ix_tse_agent", "agent_id", "org_id", "created_at"),
    )
```

### 4.15 `models/__init__.py`

**Path**: `nexra/models/__init__.py`

```python
from models.base import Base
from models.organization import Organization
from models.agent import Agent
from models.policy import Policy
from models.delegation import Delegation
from models.audit_log import AuditLog
from models.agent_budget import AgentBudget
from models.trust_score_event import TrustScoreEvent

__all__ = [
    "Base",
    "Organization",
    "Agent",
    "Policy",
    "Delegation",
    "AuditLog",
    "AgentBudget",
    "TrustScoreEvent",
]
```

### 4.16 `db/__init__.py`

Empty file.

### 4.17 `db/session.py`

**Path**: `nexra/db/session.py`

```python
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from core.config import get_settings


def create_engine():
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=(settings.environment == "development"),
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
    )


engine = create_engine()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async DB session."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

**Guardrails**:
- `expire_on_commit=False` is required so that objects remain usable after commit without re-querying.
- `pool_pre_ping=True` detects stale connections before use — critical for Railway/ECS where connections can drop.
- Do NOT create the engine at import time in production — use a startup event. For MVP, module-level is acceptable.

### 4.18 `api/__init__.py`

Empty file.

### 4.19 `api/main.py`

**Path**: `nexra/api/main.py`

Minimal app factory. Routes are added in later phases. This phase only sets up the exception handler and ASGI app.

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from core.errors import NexraError
from core.config import get_settings
import uuid


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Nexra API",
        description="The control plane for AI agent networks",
        version="0.1.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )

    # Request ID middleware
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # NexraError handler
    @app.exception_handler(NexraError)
    async def nexra_error_handler(request: Request, exc: NexraError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "request_id": getattr(request.state, "request_id", None),
                }
            },
        )

    # Sentry init (if configured)
    if settings.sentry_dsn:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=0.1 if settings.environment == "production" else 1.0,
            environment=settings.environment,
        )

    return app


app = create_app()
```

**Guardrails**:
- Disable `/docs` in production (security).
- Every response includes `X-Request-ID` header for tracing.
- Sentry is optional — only initialized if `SENTRY_DSN` is set.

### 4.20 Alembic Setup

**Directory**: `nexra/db/migrations/`

**Step 1**: Initialize Alembic (run in project root):
```bash
cd nexra && alembic init db/migrations
```

**Step 2**: Edit `db/migrations/env.py` to use async engine and import all models:

```python
# db/migrations/env.py
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from core.config import get_settings
from models import Base  # imports all models via __init__.py

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**Step 3**: Edit `alembic.ini` — set `script_location = db/migrations`.

**Step 4**: Create the initial migration file.

### 4.21 Initial Migration — `001_initial_schema.py`

**Path**: `nexra/db/migrations/versions/001_initial_schema.py`

This migration must:
1. Create the `pgcrypto` and `vector` extensions
2. Create all 7 tables with all constraints and indexes
3. Create the `audit_log_immutable()` trigger function
4. Create the `enforce_audit_immutability` trigger

The migration should use `op.execute()` for raw SQL where Alembic's ORM doesn't support pgvector or triggers.

```python
"""Initial schema - all tables, indexes, triggers

Revision ID: 001
Create Date: 2026-03-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')

    # organizations
    op.create_table(
        "organizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("api_key_hash", sa.Text, nullable=False, unique=True),
        sa.Column("api_key_prefix", sa.String(16), nullable=False, index=True),
        sa.Column("stripe_id", sa.Text, nullable=True),
        sa.Column("plan", sa.Text, nullable=False, server_default="starter"),
        sa.Column("approval_url", sa.Text, nullable=True),
        sa.Column("jwt_secret_enc", sa.Text, nullable=False),
        sa.Column("delegation_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("plan IN ('starter','growth','enterprise')", name="ck_organizations_plan"),
    )

    # agents
    op.create_table(
        "agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("capability_type", sa.Text, nullable=False),
        sa.Column("input_schema", JSONB, nullable=False),
        sa.Column("output_schema", JSONB, nullable=False),
        sa.Column("webhook_url", sa.Text, nullable=False),
        sa.Column("webhook_secret", sa.Text, nullable=False),
        sa.Column("pricing", JSONB, nullable=False),
        sa.Column("sla", JSONB, nullable=False),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("trust_score", sa.Numeric(4, 3), nullable=False, server_default="1.000"),
        sa.Column("status", sa.Text, nullable=False, server_default="probationary"),
        sa.Column("delegation_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "agent_id", name="uq_agents_org_agent"),
        sa.CheckConstraint(
            "capability_type IN ('research','analysis','generation','enrichment','validation','execution','other')",
            name="ck_agents_capability_type",
        ),
        sa.CheckConstraint("webhook_url LIKE 'https://%'", name="ck_agents_webhook_https"),
        sa.CheckConstraint("trust_score >= 0.000 AND trust_score <= 1.000", name="ck_agents_trust_score_range"),
        sa.CheckConstraint("status IN ('active','probationary','quarantined')", name="ck_agents_status"),
    )

    # pgvector embedding column (raw SQL — Alembic doesn't natively support VECTOR type)
    op.execute("ALTER TABLE agents ADD COLUMN embedding VECTOR(1536)")

    # agents indexes
    op.execute(
        "CREATE INDEX ix_agents_embedding ON agents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
    op.create_index("ix_agents_cap_type", "agents", ["capability_type", "status"])
    op.create_index("ix_agents_org_status", "agents", ["org_id", "status"])
    op.execute("CREATE INDEX ix_agents_is_public ON agents (is_public) WHERE is_public = TRUE")

    # policies
    op.create_table(
        "policies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("priority", sa.Integer, nullable=False, server_default="100"),
        sa.Column("rule_yaml", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "name", "version", name="uq_policies_org_name_version"),
    )
    op.execute("CREATE INDEX ix_policies_org_priority ON policies (org_id, priority ASC) WHERE enabled = TRUE")

    # delegations
    op.create_table(
        "delegations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("caller_org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("caller_agent_id", sa.Text, nullable=False),
        sa.Column("callee_org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("callee_agent_id", sa.Text, nullable=False),
        sa.Column("task", JSONB, nullable=False),
        sa.Column("task_hash", sa.Text, nullable=False),
        sa.Column("context_scope", sa.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("policy_id", UUID(as_uuid=True), sa.ForeignKey("policies.id"), nullable=True),
        sa.Column("policy_version", sa.Integer, nullable=True),
        sa.Column("policy_decision", sa.Text, nullable=True),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("budget_cap_usd", sa.Numeric(10, 4), nullable=True),
        sa.Column("estimated_cost_usd", sa.Numeric(10, 4), nullable=True),
        sa.Column("actual_cost_usd", sa.Numeric(10, 4), nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("llm_tokens", sa.Integer, nullable=True),
        sa.Column("callback_url", sa.Text, nullable=True),
        sa.Column("delegation_depth", sa.Integer, nullable=False, server_default="0"),
        sa.Column("parent_delegation_id", UUID(as_uuid=True), sa.ForeignKey("delegations.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("policy_decision IN ('allow','block','pause')", name="ck_delegations_policy_decision"),
        sa.CheckConstraint(
            "status IN ('pending','in_flight','completed','failed','timeout','blocked','pending_approval')",
            name="ck_delegations_status",
        ),
    )
    op.create_index("ix_delegations_caller", "delegations", ["caller_org_id", "caller_agent_id", "created_at"])
    op.create_index("ix_delegations_callee", "delegations", ["callee_agent_id", "created_at"])
    op.create_index("ix_delegations_status", "delegations", ["status", "created_at"])
    op.execute(
        "CREATE INDEX ix_delegations_parent ON delegations (parent_delegation_id) "
        "WHERE parent_delegation_id IS NOT NULL"
    )

    # audit_log
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("delegation_id", UUID(as_uuid=True), sa.ForeignKey("delegations.id"), nullable=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("actor_agent_id", sa.Text, nullable=True),
        sa.Column("target_agent_id", sa.Text, nullable=True),
        sa.Column("details", JSONB, nullable=False),
        sa.Column("cost_usd", sa.Numeric(10, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "event_type IN ("
            "'policy_evaluated','delegation_initiated','delegation_completed',"
            "'delegation_failed','delegation_blocked','delegation_timeout',"
            "'agent_quarantined','agent_activated','budget_exceeded',"
            "'hil_triggered','hil_approved','hil_expired',"
            "'anomaly_detected','circuit_breaker_tripped'"
            ")",
            name="ck_audit_log_event_type",
        ),
    )
    op.create_index("ix_audit_log_org", "audit_log", ["org_id", "created_at"])
    op.create_index("ix_audit_log_delegation", "audit_log", ["delegation_id"])
    op.create_index("ix_audit_log_event_type", "audit_log", ["event_type", "created_at"])
    op.create_index("ix_audit_log_agent", "audit_log", ["actor_agent_id", "created_at"])

    # audit_log immutability trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_log_immutable() RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log rows are immutable - no UPDATE or DELETE permitted';
        END; $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER enforce_audit_immutability
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();
    """)

    # agent_budgets
    op.create_table(
        "agent_budgets",
        sa.Column("agent_id", sa.Text, primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("period", sa.Date, primary_key=True),
        sa.Column("period_type", sa.Text, primary_key=True),
        sa.Column("cap_usd", sa.Numeric(10, 4), nullable=False),
        sa.Column("spent_usd", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("period_type IN ('daily','monthly')", name="ck_agent_budgets_period_type"),
    )
    op.create_index("ix_agent_budgets_agent", "agent_budgets", ["agent_id", "org_id", "period"])

    # trust_score_events
    op.create_table(
        "trust_score_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_id", sa.Text, nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("delegation_id", UUID(as_uuid=True), sa.ForeignKey("delegations.id"), nullable=True),
        sa.Column("score_before", sa.Numeric(4, 3), nullable=False),
        sa.Column("score_after", sa.Numeric(4, 3), nullable=False),
        sa.Column("components", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_tse_agent", "trust_score_events", ["agent_id", "org_id", "created_at"])


def downgrade() -> None:
    op.drop_table("trust_score_events")
    op.drop_table("agent_budgets")
    op.execute("DROP TRIGGER IF EXISTS enforce_audit_immutability ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS audit_log_immutable()")
    op.drop_table("audit_log")
    op.drop_table("delegations")
    op.drop_table("policies")
    op.drop_table("agents")
    op.drop_table("organizations")
    op.execute('DROP EXTENSION IF EXISTS "vector"')
    op.execute('DROP EXTENSION IF EXISTS "pgcrypto"')
```

### 4.22 Docker Compose

**Path**: `nexra/docker/docker-compose.yml`

```yaml
version: "3.9"

services:
  api:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    env_file: ../.env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ..:/app
    command: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: nexra
      POSTGRES_USER: nexra
      POSTGRES_PASSWORD: nexra
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U nexra"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

### 4.23 Dockerfile

**Path**: `nexra/docker/Dockerfile`

```dockerfile
# Stage 1: Builder
FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install poetry==1.8.0
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.in-project true \
    && poetry install --no-interaction --no-ansi --no-root

# Stage 2: Runtime
FROM python:3.12-slim AS runtime
RUN adduser --disabled-password --gecos '' appuser
WORKDIR /app
COPY --from=builder /app/.venv ./.venv
COPY . .
USER appuser
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

**Critical fixes vs naive approach**:
- `--no-root` on `poetry install` avoids installing the project itself in the builder stage (only deps).
- `PYTHONPATH="/app"` ensures `from models import ...`, `from core import ...` etc. resolve correctly. Without this, Python cannot find the top-level packages.
- The `HEALTHCHECK` uses Python's `urllib` instead of `curl` because `python:3.12-slim` does NOT include `curl`. Installing `curl` would bloat the image.

### 4.24 Dockerfile.worker

**Path**: `nexra/docker/Dockerfile.worker`

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install poetry==1.8.0
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.in-project true \
    && poetry install --no-interaction --no-ansi

FROM python:3.12-slim AS runtime
RUN adduser --disabled-password --gecos '' appuser
WORKDIR /app
COPY --from=builder /app/.venv ./.venv
COPY . .
USER appuser
ENV PATH="/app/.venv/bin:$PATH"
CMD ["celery", "-A", "workers.celery_app", "worker", "--loglevel=info", "-Q", "webhooks,billing,anomaly"]
```

### 4.25 Test Fixtures

**Path**: `nexra/tests/__init__.py` — empty

**Path**: `nexra/tests/conftest.py`

```python
import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from models import Base

TEST_DATABASE_URL = "postgresql+asyncpg://nexra:nexra@localhost:5432/nexra_test"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncSession:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
```

**Path**: `nexra/tests/fixtures/__init__.py` — empty

**Path**: `nexra/tests/fixtures/db.py` — placeholder (expanded in Phase 2+)

**Path**: `nexra/tests/fixtures/factories.py` — placeholder (expanded in Phase 3+)

### 4.26 `railway.toml`

**Path**: `nexra/railway.toml`

```toml
[build]
builder = "dockerfile"
dockerfilePath = "docker/Dockerfile"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

### 4.27 Empty `__init__.py` files

Create empty `__init__.py` in:
- `nexra/services/__init__.py`
- `nexra/workers/__init__.py`
- `nexra/api/middleware/__init__.py`
- `nexra/api/routers/__init__.py`
- `nexra/api/schemas/__init__.py`

---

## 5. Database Changes

This phase creates the entire database schema. See section 4.21 for the complete migration.

**Tables created**: organizations, agents, policies, delegations, audit_log, agent_budgets, trust_score_events

**Extensions created**: pgcrypto, vector

**Triggers created**: audit_log_immutable (prevents UPDATE/DELETE on audit_log)

**Indexes created**: 14 indexes total (see migration for full list)

---

## 6. Environment Variables

All variables from TDD §19.1 are defined in `.env.example` (section 4.2). For local development, copy `.env.example` to `.env` and fill in:

- `OPENAI_API_KEY` — required for embedding generation (Phase 3)
- `STRIPE_SECRET_KEY` — required for billing (Phase 8)
- `SECRET_KEY_ENCRYPTION_KEY` — generate with `python -c "import secrets; print(secrets.token_hex(32))"`

All other values have working defaults for local development.

---

## 7. Guardrails

1. **DO NOT** use integer primary keys anywhere. All PKs are UUID via `gen_random_uuid()`.
2. **DO NOT** use naive datetimes. All timestamps must be `DateTime(timezone=True)` and use `timezone.utc`.
3. **DO NOT** add any UPDATE or DELETE operations on the `audit_log` table at any abstraction layer. The trigger is defense-in-depth.
4. **DO NOT** store API keys in plaintext. The `api_key_hash` column stores bcrypt hashes only.
5. **DO NOT** use `from sqlalchemy import Vector` — use `from pgvector.sqlalchemy import Vector`.
6. **DO NOT** create the pgvector IVFFlat index using Alembic's `op.create_index()` — use `op.execute()` with raw SQL because Alembic doesn't support the `USING ivfflat` clause natively.
7. **DO NOT** skip the `pgcrypto` extension — `gen_random_uuid()` requires it.
8. **DO NOT** import `Settings()` directly — always use `get_settings()` for testability.
9. **DO NOT** add routes in this phase. The app factory creates the FastAPI app but mounts no routers yet.

---

## 8. Verification Checklist

Run these commands in order. Every one must succeed.

```bash
# 1. Install dependencies
cd nexra && poetry install

# 2. Copy env file
cp .env.example .env
# (edit .env to set SECRET_KEY_ENCRYPTION_KEY to a valid 64-char hex string)

# 3. Start infrastructure
cd docker && docker compose up -d postgres redis
# Wait for healthy status:
docker compose ps  # both should show "healthy"

# 4. Create test database
docker compose exec postgres psql -U nexra -c "CREATE DATABASE nexra_test;"

# 5. Run migrations
cd .. && alembic upgrade head
# Expected: no errors, "001" migration applied

# 6. Verify tables exist
docker compose exec postgres psql -U nexra -d nexra -c "\dt"
# Expected: 7 tables listed

# 7. Verify pgvector extension
docker compose exec postgres psql -U nexra -d nexra -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
# Expected: one row

# 8. Verify audit_log trigger
docker compose exec postgres psql -U nexra -d nexra -c "
INSERT INTO organizations (name, api_key_hash, api_key_prefix, jwt_secret_enc) 
VALUES ('test', 'hash', 'prefix', 'enc');
INSERT INTO audit_log (org_id, event_type, details) 
VALUES ((SELECT id FROM organizations LIMIT 1), 'policy_evaluated', '{}');
UPDATE audit_log SET event_type = 'delegation_initiated' WHERE TRUE;
"
# Expected: ERROR: audit_log rows are immutable

# 9. Verify models import
python -c "from models import Organization, Agent, Policy, Delegation, AuditLog, AgentBudget, TrustScoreEvent; print('All models imported successfully')"

# 10. Verify config loads
python -c "from core.config import get_settings; s = get_settings(); print(f'Environment: {s.environment}')"

# 11. Start the API
uvicorn api.main:app --host 0.0.0.0 --port 8000
# Expected: Uvicorn running, no import errors
# (No routes yet — 404 on all paths is expected)
```

---

## 9. Test Cases

| Test ID | Category | Description | Assertion |
|---------|----------|-------------|-----------|
| T-SCAFFOLD-001 | Config | Settings loads from .env with all required fields | `get_settings()` returns Settings with database_url, redis_url, etc. |
| T-SCAFFOLD-002 | Config | Missing required env var raises ValidationError | Remove DATABASE_URL from env → pydantic ValidationError |
| T-SCAFFOLD-003 | Config | secret_key_encryption_key must be 64 hex chars | Set to "abc" → validation error |
| T-SCAFFOLD-004 | Models | All 7 models importable from models package | `from models import *` succeeds |
| T-SCAFFOLD-005 | Models | Organization model has all expected columns | Inspect `Organization.__table__.columns` — 10 columns present |
| T-SCAFFOLD-006 | Models | Agent model embedding column is VECTOR(1536) | Column type check |
| T-SCAFFOLD-007 | DB | Migration creates all tables | `alembic upgrade head` + `\dt` shows 7 tables |
| T-SCAFFOLD-008 | DB | audit_log UPDATE raises exception | INSERT then UPDATE → exception with "immutable" message |
| T-SCAFFOLD-009 | DB | audit_log DELETE raises exception | INSERT then DELETE → exception with "immutable" message |
| T-SCAFFOLD-010 | DB | agents unique constraint on (org_id, agent_id) | Insert duplicate → IntegrityError |
| T-SCAFFOLD-011 | DB | agents webhook_url CHECK enforces HTTPS | Insert with http:// → CHECK violation |
| T-SCAFFOLD-012 | DB | agents trust_score CHECK enforces 0-1 range | Insert with 1.5 → CHECK violation |
| T-SCAFFOLD-013 | Errors | NexraError stores status_code, code, message, details | Construct and assert all fields |
| T-SCAFFOLD-014 | App | FastAPI app creates without error | `create_app()` returns FastAPI instance |
| T-SCAFFOLD-015 | App | NexraError handler returns correct JSON envelope | Raise NexraError in test → response matches `{ error: { code, message, details } }` |
