**NEXRA**

Technical Design Document

_The Control Plane for AI Agent Networks_

| **Document Type** | Technical Design Document (TDD) |
| ----------------- | ------------------------------- |
| **Version**       | 1.0 - MVP through Production    |
| **Date**          | March 2026                      |
| **Author**        | Parth                           |
| **Based On**      | Nexra PRD v_final               |
| **Status**        | Ready for Development           |
| **Website**       | usenexra.com                    |
| **API Base URL**  | <https://api.usenexra.com/v1>   |

# **Table of Contents**

§1 - Architecture Overview & Technology Stack

§2 - Repository Structure & Project Setup

§3 - Database Schema - PostgreSQL 16 + pgvector

§4 - Authentication & Security Model

§5 - Core Services - Internal Module Design

§6 - API Layer - Endpoint Specifications

§7 - Policy Engine - Design & Implementation

§8 - Delegation Flow - 13-Step Technical Walkthrough

§9 - Discovery Engine - Semantic Search & Ranking

§10 - Trust Score System

§11 - Spend Metering & Budget Enforcement

§12 - Webhook Delivery & HMAC Signing

§13 - Audit Log - Immutability & Structure

§14 - Circuit Breakers & Anomaly Detection

§15 - Human-in-the-Loop (HiTL) Gate

§16 - Stripe Billing Integration

§17 - SDK Design - nexra-py & nexra-ts

§18 - Framework Adapters - LangGraph, CrewAI, Bedrock, A2A

§19 - Environment Configuration & Secrets

§20 - Testing Strategy - Unit, Integration, E2E

§21 - Deployment - Railway MVP → AWS ECS Production

§22 - 48-Hour MVP Build Execution Plan

§23 - Error Handling & Status Codes

§24 - Performance Targets & SLAs

§25 - Future Architecture - v2 & v3 Considerations

# **§1 - Architecture Overview & Technology Stack**

## **1.1 System Layers**

Nexra is a five-layer system. Each layer has a strict responsibility boundary. No layer bypasses another.

| **Layer**     | **Technology**                  | **Responsibility**                                        | **Deployment Unit**        |
| ------------- | ------------------------------- | --------------------------------------------------------- | -------------------------- |
| API Layer     | FastAPI + Uvicorn               | HTTP request validation, auth middleware, route handlers  | ECS Task / Railway Service |
| Service Layer | Python modules                  | Business logic: delegation, policy eval, scoring, billing | Same process as API        |
| Data Layer    | PostgreSQL 16 + pgvector, Redis | Persistence, vector similarity, caching, token store      | RDS Multi-AZ + ElastiCache |
| Worker Layer  | Celery + Redis broker           | Async webhook delivery, billing events, anomaly checks    | Separate ECS Task          |
| External APIs | OpenAI, Stripe, SIEM webhooks   | Embeddings, billing, compliance export                    | Third-party SaaS           |

## **1.2 Technology Stack - Complete Reference**

| **Language**                 | Python 3.12 (API + workers). TypeScript 5.x (SDK only).                                                                         |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **Web Framework**            | FastAPI 0.115+. ASGI via Uvicorn. Pydantic v2 for all request/response models.                                                  |
| **Database**                 | PostgreSQL 16 with pgvector 0.7+ extension. ORM: SQLAlchemy 2.x async (asyncpg driver).                                         |
| **Cache / Token Store**      | Redis 7.x via redis-py async. Used for: JWT single-use enforcement, rate limit counters, policy cache (TTL 60s), session state. |
| **Task Queue**               | Celery 5.x with Redis broker. Used for: async webhook delivery, Stripe billing events, anomaly detection jobs.                  |
| **Embeddings**               | OpenAI text-embedding-3-small. 1536 dimensions. Stored as VECTOR(1536) in pgvector. Cosine similarity.                          |
| **Auth - API Keys**          | bcrypt (passlib). 12 rounds. Keys never stored in plaintext. Never returned after initial creation response.                    |
| **Auth - Delegation Tokens** | python-jose (JOSE/JWT). HS256 signed. Per-org 256-bit secret stored AES-256-GCM encrypted at rest.                              |
| **Webhook Signing**          | HMAC-SHA256 via Python hmac module. Signature in X-Nexra-Signature header as sha256=&lt;hex&gt;.                                |
| **HTTP Client**              | HTTPX async. Used for outbound webhook delivery.                                                                                |
| **Schema Validation (I/O)**  | jsonschema 4.x. Validates delegation task payloads against registered input_schema / output_schema.                             |
| **Policy Engine**            | PyYAML + custom Python rule evaluator. Zero external dependencies in evaluation hot path.                                       |
| **Billing**                  | Stripe Python SDK 10.x. Metering API for usage records. Stripe Connect for cross-org payouts.                                   |
| **Migrations**               | Alembic 1.x. All schema changes versioned. No manual SQL in production.                                                         |
| **Testing**                  | pytest + pytest-asyncio + httpx (async test client). Factory Boy for fixtures. 80%+ line coverage target.                       |
| **Linting / Formatting**     | ruff (linting + formatting). mypy (static type checking). pre-commit hooks.                                                     |
| **Containerization**         | Docker. Multi-stage builds. Non-root user. Health check at /health.                                                             |
| **CI/CD**                    | GitHub Actions. On PR: lint + type-check + unit tests. On merge to main: integration tests + Railway/ECS deploy.                |
| **Monitoring (MVP)**         | Railway built-in logs + Sentry (sentry-sdk). Error grouping, performance tracing.                                               |
| **Monitoring (Prod)**        | Datadog APM + CloudWatch metrics + PagerDuty alerts.                                                                            |
| **IaC**                      | Terraform (production). Railway config.toml (MVP). Docker Compose (local dev).                                                  |

## **1.3 Request Lifecycle Diagram (Text Representation)**

Every API request flows through the following layers in order. No shortcuts.

Client Request (HTTPS)

↓

\[1\] TLS Termination (Railway/ALB)

↓

\[2\] Rate Limit Check (Redis counter per org - 1000 req/min Growth)

↓

\[3\] Auth Middleware (bcrypt API key verify + X-Agent-ID ownership check)

↓

\[4\] Pydantic Request Validation (type check, required fields, enum values)

↓

\[5\] Route Handler (FastAPI endpoint function)

↓

\[6\] Service Layer (business logic - PolicyEngine, DelegationService, etc.)

↓

\[7\] Data Layer (SQLAlchemy async queries to Postgres / Redis)

↓

\[8\] Response Serialization (Pydantic response models → JSON)

↓

Client Response

# **§2 - Repository Structure & Project Setup**

## **2.1 Monorepo Layout**

nexra/

├── api/ # FastAPI application

│ ├── main.py # App factory, middleware registration, router mounting

│ ├── dependencies.py # FastAPI Depends() - auth, db session, redis

│ ├── middleware/

│ │ ├── auth.py # API key extraction + bcrypt verify

│ │ ├── rate_limit.py # Redis sliding window counter

│ │ └── logging.py # Structured JSON request logging

│ ├── routers/

│ │ ├── agents.py # /agents/register, /agents/registry, /agents/{id}/\*

│ │ ├── capabilities.py # /capabilities/discover

│ │ ├── delegations.py # /delegate, /delegations/{id}, /delegations/{id}/complete

│ │ ├── policies.py # /policies CRUD

│ │ ├── audit.py # /audit/log

│ │ ├── analytics.py # /analytics/usage, /spend/summary

│ │ └── health.py # /health

│ └── schemas/ # Pydantic v2 request/response models

│ ├── agents.py

│ ├── delegations.py

│ ├── policies.py

│ └── common.py # Pagination, error envelope

├── services/ # Business logic - no FastAPI imports

│ ├── agent_service.py # Registration, embedding, status management

│ ├── delegation_service.py # Orchestrates the 13-step delegation flow

│ ├── discovery_service.py # Semantic search + composite scoring

│ ├── policy_engine.py # YAML policy evaluation

│ ├── trust_service.py # Trust score calculation and update

│ ├── budget_service.py # Spend tracking + cap enforcement

│ ├── audit_service.py # Append-only audit log writes

│ ├── webhook_service.py # HMAC signing + HTTPX delivery

│ ├── billing_service.py # Stripe metering + Connect payouts

│ └── anomaly_service.py # Statistical spend anomaly detection

├── models/ # SQLAlchemy ORM models

│ ├── base.py # DeclarativeBase, UUID PK mixin

│ ├── organization.py

│ ├── agent.py

│ ├── delegation.py

│ ├── policy.py

│ ├── audit_log.py

│ ├── agent_budget.py

│ └── trust_score_event.py

├── db/

│ ├── session.py # Async engine + session factory

│ ├── migrations/ # Alembic migration files

│ │ ├── env.py

│ │ └── versions/

│ └── seeds/ # Dev seed data (not run in prod)

├── workers/ # Celery tasks

│ ├── celery_app.py # Celery app init + beat schedule

│ ├── webhook_worker.py # Async webhook delivery with retry

│ ├── billing_worker.py # Stripe event batching

│ └── anomaly_worker.py # Hourly anomaly detection scan

├── core/

│ ├── config.py # Pydantic Settings (reads .env)

│ ├── crypto.py # bcrypt, HMAC, AES-GCM helpers

│ ├── jwt.py # Delegation JWT issue + verify

│ └── errors.py # Exception classes + error codes

├── sdk/ # nexra-py SDK (also published to PyPI)

│ ├── nexra/

│ │ ├── \__init_\_.py

│ │ ├── client.py # NexraClient - main entry point

│ │ ├── adapters/

│ │ │ ├── langgraph.py

│ │ │ ├── crewai.py

│ │ │ └── bedrock.py

│ │ └── types.py # Typed response dataclasses

│ ├── pyproject.toml

│ └── README.md

├── tests/

│ ├── unit/ # Pure logic, no DB

│ │ ├── test_policy_engine.py

│ │ ├── test_trust_service.py

│ │ ├── test_budget_service.py

│ │ └── test_crypto.py

│ ├── integration/ # Uses test DB + Redis

│ │ ├── test_registration.py

│ │ ├── test_discovery.py

│ │ ├── test_delegation.py

│ │ └── test_audit_immutability.py

│ ├── e2e/ # Full stack tests

│ │ └── test_full_delegation_flow.py

│ └── fixtures/

│ ├── db.py # Test DB setup/teardown

│ └── factories.py # Factory Boy for test data

├── docker/

│ ├── Dockerfile # Multi-stage: builder + runtime

│ ├── Dockerfile.worker # Celery worker image

│ └── docker-compose.yml # Local dev: api + postgres + redis

├── infra/

│ └── terraform/ # ECS, RDS, ElastiCache, ALB, IAM

├── .github/

│ └── workflows/

│ ├── ci.yml # PR: lint + test

│ └── deploy.yml # Main: test + deploy

├── pyproject.toml # Project deps (uv or poetry)

├── railway.toml # Railway deployment config

├── .env.example # All required env vars documented

└── README.md

## **2.2 pyproject.toml - Core Dependencies**

\[tool.poetry.dependencies\]

python = "^3.12"

fastapi = "^0.115"

uvicorn = { extras = \["standard"\], version = "^0.32" }

pydantic = { extras = \["email"\], version = "^2.9" }

pydantic-settings = "^2.5"

sqlalchemy = { extras = \["asyncio"\], version = "^2.0" }

asyncpg = "^0.30"

alembic = "^1.14"

pgvector = "^0.3" # SQLAlchemy Vector type

redis = { extras = \["hiredis"\], version = "^5.2" }

celery = { extras = \["redis"\], version = "^5.4" }

httpx = "^0.28"

python-jose = { extras = \["cryptography"\], version = "^3.3" }

passlib = { extras = \["bcrypt"\], version = "^1.7" }

cryptography = "^43" # AES-GCM for secret encryption

openai = "^1.55"

stripe = "^11"

pyyaml = "^6.0"

jsonschema = "^4.23"

sentry-sdk = { extras = \["fastapi"\], version = "^2.18" }

# **§3 - Database Schema - PostgreSQL 16 + pgvector**

## **3.1 Schema Design Principles**

- All primary keys are UUID (gen_random_uuid()). No integer sequences.
- All timestamps use TIMESTAMPTZ (timezone-aware). Application always writes UTC.
- audit_log is append-only enforced at DB level via trigger. No UPDATE or DELETE at any abstraction layer.
- JSONB used for flexible nested structures (schemas, pricing, sla, task payloads, results).
- Text arrays (TEXT\[\]) used for context_scope - simple list of grant key strings.
- VECTOR(1536) for capability embeddings. Requires pgvector extension installed before migrations run.
- All migrations via Alembic. Never apply raw SQL in production.

## **3.2 Full DDL**

\-- ═══════════════════════════════════════════════════════════════

\-- PREREQUISITES

\-- ═══════════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS "pgcrypto"; -- gen_random_uuid()

CREATE EXTENSION IF NOT EXISTS "vector"; -- pgvector VECTOR type

\-- ═══════════════════════════════════════════════════════════════

\-- organizations

\-- Top-level billing entity. One per paying customer.

\-- ═══════════════════════════════════════════════════════════════

CREATE TABLE organizations (

id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

name TEXT NOT NULL,

api_key_hash TEXT NOT NULL UNIQUE, -- bcrypt(12) of actual key

stripe_id TEXT, -- Stripe Customer ID

plan TEXT NOT NULL DEFAULT 'starter'

CHECK (plan IN ('starter','growth','enterprise')),

approval_url TEXT, -- HiTL gate webhook target

jwt_secret_enc TEXT NOT NULL, -- AES-256-GCM encrypted 256-bit secret

delegation_count INT DEFAULT 0, -- running total for analytics

created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);

\-- ═══════════════════════════════════════════════════════════════

\-- agents

\-- Registered capabilities. One org can register many agents.

\-- ═══════════════════════════════════════════════════════════════

CREATE TABLE agents (

id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

agent_id TEXT NOT NULL, -- human-readable, unique per org

name TEXT NOT NULL,

description TEXT NOT NULL,

capability_type TEXT NOT NULL

CHECK (capability_type IN

('research','analysis','generation','enrichment',

'validation','execution','other')),

input_schema JSONB NOT NULL, -- JSON Schema spec for task payload

output_schema JSONB NOT NULL, -- JSON Schema spec for result

webhook_url TEXT NOT NULL

CHECK (webhook_url LIKE 'https://%'), -- HTTPS enforced

webhook_secret TEXT NOT NULL, -- raw secret for HMAC signing (encrypted at rest)

pricing JSONB NOT NULL, -- { "per_call_usd": 0.15 }

sla JSONB NOT NULL, -- { "p99_latency_ms": 8000, "availability": 0.99 }

is_public BOOLEAN NOT NULL DEFAULT FALSE,

embedding VECTOR(1536), -- text-embedding-3-small of name + description

trust_score DECIMAL(4,3) NOT NULL DEFAULT 1.000

CHECK (trust_score >= 0.000 AND trust_score <= 1.000),

status TEXT NOT NULL DEFAULT 'probationary'

CHECK (status IN ('active','probationary','quarantined')),

delegation_count INT NOT NULL DEFAULT 0,

created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

UNIQUE (org_id, agent_id)

);

CREATE INDEX agents_embedding_idx ON agents USING ivfflat (embedding vector_cosine_ops)

WITH (lists = 100);

CREATE INDEX agents_cap_type_idx ON agents (capability_type, status);

CREATE INDEX agents_org_status_idx ON agents (org_id, status);

CREATE INDEX agents_is_public_idx ON agents (is_public) WHERE is_public = TRUE;

\-- ═══════════════════════════════════════════════════════════════

\-- policies

\-- Delegation policies with version history.

\-- ═══════════════════════════════════════════════════════════════

CREATE TABLE policies (

id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

name TEXT NOT NULL,

description TEXT,

priority INT NOT NULL DEFAULT 100, -- lower = evaluated first

rule_yaml TEXT NOT NULL, -- full YAML policy definition

version INT NOT NULL DEFAULT 1,

enabled BOOLEAN NOT NULL DEFAULT TRUE,

created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

UNIQUE (org_id, name, version)

);

CREATE INDEX policies_org_priority_idx ON policies (org_id, priority ASC) WHERE enabled = TRUE;

\-- ═══════════════════════════════════════════════════════════════

\-- delegations

\-- One row per delegation attempt (including blocked ones).

\-- ═══════════════════════════════════════════════════════════════

CREATE TABLE delegations (

id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

caller_org_id UUID NOT NULL REFERENCES organizations(id),

caller_agent_id TEXT NOT NULL,

callee_org_id UUID REFERENCES organizations(id), -- NULL = same org

callee_agent_id TEXT NOT NULL,

task JSONB NOT NULL,

task_hash TEXT NOT NULL, -- SHA-256(canonical JSON) for tamper detection

context_scope TEXT\[\] NOT NULL DEFAULT '{}',

policy_id UUID REFERENCES policies(id),

policy_version INT,

policy_decision TEXT CHECK (policy_decision IN ('allow','block','pause')),

status TEXT NOT NULL

CHECK (status IN ('pending','in_flight','completed',

'failed','timeout','blocked','pending_approval')),

result JSONB,

budget_cap_usd DECIMAL(10,4),

estimated_cost_usd DECIMAL(10,4),

actual_cost_usd DECIMAL(10,4),

latency_ms INT,

llm_tokens INT,

callback_url TEXT,

delegation_depth INT NOT NULL DEFAULT 0,

parent_delegation_id UUID REFERENCES delegations(id),

created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

completed_at TIMESTAMPTZ

);

CREATE INDEX delegations_caller_idx ON delegations (caller_org_id, caller_agent_id, created_at DESC);

CREATE INDEX delegations_callee_idx ON delegations (callee_agent_id, created_at DESC);

CREATE INDEX delegations_status_idx ON delegations (status, created_at DESC);

CREATE INDEX delegations_parent_idx ON delegations (parent_delegation_id) WHERE parent_delegation_id IS NOT NULL;

\-- ═══════════════════════════════════════════════════════════════

\-- audit_log

\-- APPEND-ONLY. Trigger below prevents all UPDATE and DELETE.

\-- ═══════════════════════════════════════════════════════════════

CREATE TABLE audit_log (

id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

delegation_id UUID REFERENCES delegations(id),

org_id UUID NOT NULL REFERENCES organizations(id),

event_type TEXT NOT NULL

CHECK (event_type IN (

'policy_evaluated','delegation_initiated','delegation_completed',

'delegation_failed','delegation_blocked','delegation_timeout',

'agent_quarantined','agent_activated','budget_exceeded',

'hil_triggered','hil_approved','hil_expired',

'anomaly_detected','circuit_breaker_tripped'

)),

actor_agent_id TEXT,

target_agent_id TEXT,

details JSONB NOT NULL,

cost_usd DECIMAL(10,4),

created_at TIMESTAMPTZ NOT NULL DEFAULT NOW() -- IMMUTABLE

);

CREATE INDEX audit_log_org_idx ON audit_log (org_id, created_at DESC);

CREATE INDEX audit_log_delegation_idx ON audit_log (delegation_id);

CREATE INDEX audit_log_event_type_idx ON audit_log (event_type, created_at DESC);

CREATE INDEX audit_log_agent_idx ON audit_log (actor_agent_id, created_at DESC);

\-- Immutability trigger

CREATE OR REPLACE FUNCTION audit_log_immutable() RETURNS TRIGGER AS \$\$

BEGIN

RAISE EXCEPTION 'audit_log rows are immutable - no UPDATE or DELETE permitted';

END; \$\$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_audit_immutability

BEFORE UPDATE OR DELETE ON audit_log

FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();

\-- ═══════════════════════════════════════════════════════════════

\-- agent_budgets

\-- Spend tracking per agent per period. Updated on every delegation settle.

\-- ═══════════════════════════════════════════════════════════════

CREATE TABLE agent_budgets (

agent_id TEXT NOT NULL,

org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

period DATE NOT NULL,

period_type TEXT NOT NULL CHECK (period_type IN ('daily','monthly')),

cap_usd DECIMAL(10,4) NOT NULL,

spent_usd DECIMAL(10,4) NOT NULL DEFAULT 0,

updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

PRIMARY KEY (agent_id, org_id, period, period_type)

);

CREATE INDEX agent_budgets_agent_idx ON agent_budgets (agent_id, org_id, period DESC);

\-- ═══════════════════════════════════════════════════════════════

\-- trust_score_events

\-- Append-only history of trust score changes per agent.

\-- ═══════════════════════════════════════════════════════════════

CREATE TABLE trust_score_events (

id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

agent_id TEXT NOT NULL,

org_id UUID NOT NULL REFERENCES organizations(id),

delegation_id UUID REFERENCES delegations(id),

score_before DECIMAL(4,3) NOT NULL,

score_after DECIMAL(4,3) NOT NULL,

components JSONB NOT NULL, -- { success_rate, sla_compliance, cost_accuracy, policy_violations_inverse }

created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);

CREATE INDEX tse_agent_idx ON trust_score_events (agent_id, org_id, created_at DESC);

# **§4 - Authentication & Security Model**

## **4.1 Identity Hierarchy**

| **Level**        | **Identifier**                       | **Scope**                                        | **How Verified**                                                         |
| ---------------- | ------------------------------------ | ------------------------------------------------ | ------------------------------------------------------------------------ |
| Organization     | UUID (internal) + API key (external) | All agents, policies, delegations under this org | bcrypt(12) hash comparison on every request                              |
| Agent            | agent_id string (unique per org)     | Single registered capability                     | org API key + X-Agent-ID header; DB query confirms agent.org_id = org.id |
| Delegation Token | JWT jti (UUID, single-use)           | One specific delegation only                     | HS256 signature verify + Redis jti lookup (expires with TTL)             |

## **4.2 API Key Generation & Storage**

When an org is created, a new API key is generated. The key is returned exactly once in the creation response and never again.

\# core/crypto.py

import secrets, bcrypt

def generate_api_key() -> tuple\[str, str\]:

"""Returns (raw_key, bcrypt_hash). Store only the hash."""

raw = 'nx*live*' + secrets.token_urlsafe(32)

hashed = bcrypt.hashpw(raw.encode(), bcrypt.gensalt(rounds=12)).decode()

return raw, hashed

def verify_api_key(raw_key: str, stored_hash: str) -> bool:

return bcrypt.checkpw(raw_key.encode(), stored_hash.encode())

## **4.3 Auth Middleware (FastAPI Dependency)**

\# api/middleware/auth.py

from fastapi import Header, HTTPException, Depends

from sqlalchemy.ext.asyncio import AsyncSession

from core.crypto import verify_api_key

from models.organization import Organization

from models.agent import Agent

async def get_org_and_agent(

authorization: str = Header(...), # 'Bearer nx*live*...'

x_agent_id: str | None = Header(None, alias='X-Agent-ID'),

db: AsyncSession = Depends(get_db),

redis = Depends(get_redis)

) -> tuple\[Organization, Agent | None\]:

if not authorization.startswith('Bearer '):

raise HTTPException(401, 'Missing Bearer token')

raw_key = authorization\[7:\]

\# Rate limit check BEFORE bcrypt (CPU-expensive)

await check_rate_limit(redis, raw_key\[:16\]) # use prefix as rate limit key

\# Find org by key prefix (first 16 chars) to avoid full-table bcrypt scan

org = await db.query(Organization).filter(

Organization.api_key_prefix == raw_key\[:16\]

).first()

if not org or not verify_api_key(raw_key, org.api_key_hash):

raise HTTPException(401, 'Invalid API key')

agent = None

if x_agent_id:

agent = await db.query(Agent).filter(

Agent.org_id == org.id,

Agent.agent_id == x_agent_id

).first()

if not agent:

raise HTTPException(401, 'X-Agent-ID not found under this org')

if agent.status == 'quarantined':

raise HTTPException(403, 'Agent is quarantined')

return org, agent

_NOTE: api_key_prefix (first 16 chars) stored separately in organizations table to enable O(1) key lookup without full-table scan. This avoids timing-attack-vulnerable sequential bcrypt comparisons across all orgs._

## **4.4 Delegation JWT**

\# core/jwt.py

from jose import jwt, JWTError

from datetime import datetime, timedelta, timezone

from uuid import uuid4

import redis.asyncio as aioredis

TOKEN_EXPIRY_SECONDS = 300 # 5 minutes

def issue_delegation_token(

org_secret: str, # 256-bit secret, AES-GCM decrypted before use

delegation_id: str,

callee_agent_id: str,

context_scope: list\[str\],

) -> str:

jti = str(uuid4())

now = datetime.now(timezone.utc)

payload = {

'jti': jti, # single-use enforced via Redis

'iat': now,

'exp': now + timedelta(seconds=TOKEN_EXPIRY_SECONDS),

'delegation_id': delegation_id,

'callee_agent_id': callee_agent_id,

'context_scope': context_scope,

}

return jwt.encode(payload, org_secret, algorithm='HS256')

async def verify_delegation_token(

token: str,

org_secret: str,

redis_client: aioredis.Redis,

) -> dict:

try:

payload = jwt.decode(token, org_secret, algorithms=\['HS256'\])

except JWTError as e:

raise ValueError(f'Invalid delegation token: {e}')

jti = payload\['jti'\]

\# Single-use: mark as used in Redis with same TTL as token expiry

used = await redis_client.set(f'jti:{jti}', '1', nx=True, ex=TOKEN_EXPIRY_SECONDS)

if not used:

raise ValueError('Delegation token already used (single-use enforcement)')

return payload

## **4.5 HMAC Webhook Signing**

\# core/crypto.py (continued)

import hmac, hashlib, json

def sign_webhook_payload(payload: dict, secret: str) -> str:

"""Returns 'sha256=&lt;hex_digest&gt;' for X-Nexra-Signature header."""

body = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode()

sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

return f'sha256={sig}'

def verify_webhook_signature(payload_bytes: bytes, secret: str, signature: str) -> bool:

"""Callee uses this to verify incoming Nexra webhooks."""

expected = 'sha256=' + hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()

return hmac.compare_digest(expected, signature) # constant-time comparison

# **§5 - Core Services - Internal Module Design**

## **5.1 Service Layer Contracts**

All services are pure Python classes instantiated with dependency injection. No FastAPI imports. No direct route access. Each service takes an AsyncSession and/or Redis client in \__init_\_. All public methods are async.

| **Service Class** | **File**                       | **Key Methods**                                                | **External Calls**                                        |
| ----------------- | ------------------------------ | -------------------------------------------------------------- | --------------------------------------------------------- |
| AgentService      | services/agent_service.py      | register(), update_status(), get_by_agent_id(), list_for_org() | OpenAI (embedding)                                        |
| DiscoveryService  | services/discovery_service.py  | discover(), compute_composite_score()                          | Postgres pgvector                                         |
| PolicyEngine      | services/policy_engine.py      | evaluate(delegation_ctx) -> PolicyDecision                     | None (pure Python)                                        |
| DelegationService | services/delegation_service.py | initiate(), complete(), get_status()                           | PolicyEngine, BudgetService, WebhookService, AuditService |
| TrustService      | services/trust_service.py      | update_after_delegation(), get_score_breakdown()               | Postgres                                                  |
| BudgetService     | services/budget_service.py     | check_and_reserve(), settle(), get_summary()                   | Postgres                                                  |
| AuditService      | services/audit_service.py      | append(), query(), export_csv()                                | Postgres (append-only)                                    |
| WebhookService    | services/webhook_service.py    | deliver(), sign_payload(), verify_response()                   | HTTPX (outbound)                                          |
| BillingService    | services/billing_service.py    | record_usage(), trigger_connect_payout()                       | Stripe API                                                |
| AnomalyService    | services/anomaly_service.py    | check_agent_spend(), compute_baseline()                        | Postgres                                                  |

## **5.2 AgentService - Registration Detail**

\# services/agent_service.py

class AgentService:

def \__init_\_(self, db: AsyncSession, openai_client: AsyncOpenAI):

self.db = db

self.openai = openai_client

async def register(self, org_id: str, data: AgentRegisterRequest) -> Agent:

\# 1. Check if agent_id already exists for this org (idempotent re-register)

existing = await self.\_get_by_agent_id(org_id, data.agent_id)

\# 2. Validate webhook_url starts with https://

if not data.webhook_url.startswith('https://'):

raise ValidationError('webhook_url must use HTTPS')

\# 3. Validate input_schema and output_schema are valid JSON Schema

self.\_validate_json_schema(data.input_schema)

self.\_validate_json_schema(data.output_schema)

\# 4. Generate embedding from name + description

embed_text = f'{data.name}. {data.description}'

embedding = await self.\_embed(embed_text)

\# 5. Upsert agent record

if existing:

\# Update all fields, trigger re-embedding, preserve trust_score

existing.description = data.description

existing.input_schema = data.input_schema

existing.output_schema = data.output_schema

existing.webhook_url = data.webhook_url

existing.pricing = data.pricing

existing.sla = data.sla

existing.embedding = embedding

existing.is_public = data.is_public

existing.updated_at = datetime.utcnow()

agent = existing

else:

agent = Agent(org_id=org_id, status='probationary', embedding=embedding, \*\*data.model_dump())

self.db.add(agent)

await self.db.commit()

await self.db.refresh(agent)

return agent

async def \_embed(self, text: str) -> list\[float\]:

resp = await self.openai.embeddings.create(

input=text, model='text-embedding-3-small'

)

return resp.data\[0\].embedding # 1536-dim float list

# **§6 - API Layer - Complete Endpoint Specifications**

## **6.1 Base Configuration**

| **Base URL**             | <https://api.usenexra.com/v1>                                              |
| ------------------------ | -------------------------------------------------------------------------- |
| **Protocol**             | HTTPS only. TLS 1.3 minimum. HTTP rejected.                                |
| **Auth Header**          | Authorization: Bearer nx*live*&lt;api_key&gt;                              |
| **Agent Header**         | X-Agent-ID: &lt;agent_id&gt; (required for agent-initiated calls)          |
| **Content-Type**         | application/json (all endpoints)                                           |
| **Rate Limit (Growth)**  | 1,000 req/min per org. 429 with Retry-After on exceed.                     |
| **Rate Limit (Starter)** | 100 req/min per org.                                                       |
| **Pagination**           | Cursor-based on all list endpoints. next_cursor in response.               |
| **Response Envelope**    | All responses: { data: &lt;payload&gt;, meta: { request_id, latency_ms } } |
| **Error Envelope**       | All errors: { error: { code, message, details } }                          |

## **6.2 Endpoint Inventory**

| **Method** | **Path**                   | **Auth**           | **Priority** | **Description**                                     |
| ---------- | -------------------------- | ------------------ | ------------ | --------------------------------------------------- |
| POST       | /agents/register           | Org key            | P0           | Register or re-register an agent capability         |
| GET        | /agents/registry           | Org key            | P0           | List registered agents (paginated, filterable)      |
| GET        | /agents/{id}               | Org key            | P0           | Get agent details by UUID or agent_id               |
| GET        | /agents/{id}/trust         | Org key            | P1           | Trust score breakdown for an agent                  |
| POST       | /agents/{id}/quarantine    | Org key (admin)    | P1           | Immediately quarantine an agent                     |
| POST       | /agents/{id}/activate      | Org key (admin)    | P1           | Re-activate a quarantined/probationary agent        |
| POST       | /capabilities/discover     | Org key + Agent-ID | P0           | Semantic discovery of matching agent capabilities   |
| POST       | /delegate                  | Org key + Agent-ID | P0           | Initiate a delegation (full 13-step flow)           |
| GET        | /delegations/{id}          | Org key            | P0           | Get delegation status and result                    |
| POST       | /delegations/{id}/complete | Delegation JWT     | P0           | Callee posts result back to Nexra                   |
| POST       | /delegations/{id}/approve  | Org key (admin)    | P1           | Approve a HiTL-gated delegation                     |
| POST       | /delegations/{id}/reject   | Org key (admin)    | P1           | Reject a HiTL-gated delegation                      |
| POST       | /policies                  | Org key            | P0           | Create a new delegation policy                      |
| GET        | /policies                  | Org key            | P0           | List all policies for org                           |
| GET        | /policies/{id}             | Org key            | P0           | Get policy with full version history                |
| PUT        | /policies/{id}             | Org key            | P1           | Update policy (creates new version)                 |
| DELETE     | /policies/{id}             | Org key            | P1           | Disable a policy (soft delete, preserves history)   |
| GET        | /audit/log                 | Org key            | P0           | Query audit log (cursor-paginated, filterable)      |
| GET        | /analytics/usage           | Org key            | P1           | Delegation volume, latency, cost time-series        |
| GET        | /spend/summary             | Org key            | P0           | CFO-facing spend summary by agent/period            |
| GET        | /health                    | None               | P0           | Health check - returns 200 OK with component status |

## **6.3 POST /agents/register - Full Specification**

**Request Body**

POST /v1/agents/register

Authorization: Bearer nx*live*...

{

"agent_id": "research-agent-v2", // string, required, \[a-z0-9-\], max 64 chars

"name": "Competitive Research Agent", // string, required, max 200 chars

"description": "Researches competitors...", // string, required, min 20 chars

"capability_type": "research", // enum: research|analysis|generation|

// enrichment|validation|execution|other

"input_schema": { // object, required, valid JSON Schema Draft 7

"type": "object",

"required": \["company_name"\],

"properties": {

"company_name": { "type": "string" },

"focus_areas": { "type": "array", "items": { "type": "string" } }

}

},

"output_schema": { // object, required, valid JSON Schema Draft 7

"type": "object",

"required": \["summary", "competitors"\],

"properties": {

"summary": { "type": "string" },

"competitors": { "type": "array" }

}

},

"pricing": { "per_call_usd": 0.15 }, // object, required. per_call_usd > 0

"sla": { // object, required

"p99_latency_ms": 8000, // int, required, > 0

"availability": 0.99 // float, required, 0.0-1.0

},

"webhook_url": "<https://agent.co/nexra>", // string, required, must start with https://

"webhook_secret": "whs_abc123...", // string, required, min 32 chars

"is_public": false // bool, optional, default false

}

**Response 201 Created**

{

"data": {

"agent_id": "research-agent-v2",

"status": "probationary",

"embedding_id": "uuid",

"registered_at": "2026-03-13T21:00:00Z"

},

"meta": { "request*id": "req*...", "latency_ms": 340 }

}

**Error Cases**

| **HTTP Status** | **Code**            | **Condition**                                                        |
| --------------- | ------------------- | -------------------------------------------------------------------- |
| 400             | INVALID_SCHEMA      | input_schema or output_schema is not valid JSON Schema Draft 7       |
| 400             | INVALID_WEBHOOK_URL | webhook_url does not start with https://                             |
| 400             | INVALID_AGENT_ID    | agent_id contains characters outside \[a-z0-9-\] or exceeds 64 chars |
| 401             | UNAUTHORIZED        | API key missing or invalid                                           |
| 429             | RATE_LIMIT_EXCEEDED | Too many requests                                                    |

## **6.4 POST /capabilities/discover - Full Specification**

**Request Body**

{

"query": "competitive research for B2B SaaS", // string, required, min 3 chars

"capability_type": "research", // string, optional hard filter

"budget_cap_usd": 0.50, // float, optional (exclude above this)

"max_latency_ms": 10000, // int, optional (exclude above this)

"exclude_agents": \["agent-id-1"\], // array, optional

"include_cross_org": false, // bool, optional, default false

"limit": 5 // int, optional, default 5, max 20

}

**Response 200 OK**

{

"data": {

"matches": \[

{

"agent_id": "research-agent-v2",

"name": "Competitive Research Agent",

"match_score": 0.94, // composite: schema 50% + trust 25% + cost 15% + latency 10%

"trust_score": 0.91,

"status": "active",

"pricing": { "per_call_usd": 0.15 },

"sla": { "p99_latency_ms": 8000, "availability": 0.99 },

"is_cross_org": false,

"capability_type": "research"

}

\],

"total_candidates": 12, // agents evaluated before filtering

"filtered_count": 7, // agents remaining after hard filters

"latency_ms": 87 // P99 target: <200ms

},

"meta": { "request*id": "req*..." }

}

## **6.5 POST /delegate - Full Specification**

**Request Body**

{

"callee_agent_id": "research-agent-v2", // string, required

"task": { // object, required - validated against callee's input_schema

"type": "research",

"input": { "company_name": "Acme Corp", "focus_areas": \["pricing"\] }

},

"context_scope": \["deal_metadata", "account_tier"\], // array, required (can be \[\])

"budget_cap_usd": 0.25, // float, required

"timeout_ms": 12000, // int, optional, default 30000, max 120000

"callback_url": null // string|null: null=sync, URL=async callback

}

**Response Variants**

// 200 OK - synchronous completion

{

"data": {

"delegation*id": "del*...",

"status": "completed",

"policy_result": {

"policy*id": "pol*...",

"policy_version": 3,

"decision": "allow"

},

"result": { /\* callee's output - validated against output_schema \*/ },

"usage": {

"cost_usd": 0.15,

"latency_ms": 1840,

"llm_tokens": 2400

}

}

}

// 202 Accepted - async mode OR HiTL gate triggered

{

"data": {

"delegation*id": "del*...",

"status": "in_flight", // OR "pending_approval" if HiTL

"poll*url": "/v1/delegations/del*...",

"approval_deadline": "2026-03-14T21:00:00Z" // only present if HiTL

}

}

**Error Responses**

| **HTTP** | **Code**                 | **Condition**                                                                       |
| -------- | ------------------------ | ----------------------------------------------------------------------------------- |
| 403      | POLICY_BLOCKED           | Policy evaluation returned 'block'. Includes policy_id and reason in details.       |
| 402      | BUDGET_EXCEEDED          | Estimated cost + spent_usd > cap_usd. Includes remaining_budget_usd.                |
| 422      | SCHEMA_VALIDATION_FAILED | Task payload does not conform to callee's input_schema.                             |
| 408      | DELEGATION_TIMEOUT       | Callee did not respond within timeout_ms.                                           |
| 404      | AGENT_NOT_FOUND          | callee_agent_id not found in this org (or public marketplace if include_cross_org). |
| 503      | CALLEE_WEBHOOK_FAILED    | Nexra received non-2xx from callee webhook (not retried synchronously).             |

## **6.6 POST /delegations/{id}/complete - Callee Endpoint**

This endpoint is called by the callee agent after executing the task. It requires a delegation JWT (not an org API key).

POST /v1/delegations/del_01JFXP.../complete

Authorization: Bearer &lt;delegation_jwt&gt; // issued by Nexra in the webhook payload

{

"result": { // object, required - validated against output_schema

"summary": "Acme Corp is a mid-market CRM...",

"competitors": \[{ "name": "Rival Corp" }\]

},

"usage": { // object, optional - callee self-reports

"llm_tokens": 2400, // int, optional

"external_api_cost_usd": 0.02 // float, optional

}

}

On receipt, Nexra performs in order: (1) verify delegation JWT - signature + single-use jti, (2) verify delegation_id in JWT matches path param, (3) validate result against callee's registered output_schema, (4) update delegation status to 'completed', (5) settle budget, (6) update trust score, (7) append audit_log entry, (8) queue Stripe billing event, (9) if callback_url is set - fire it; else store result for synchronous return to caller.

# **§7 - Policy Engine - Design & Implementation**

## **7.1 Policy Structure - YAML Schema**

Policies are stored as YAML strings in the policies table. The policy engine parses YAML on evaluation - with Redis caching (TTL 60s per org) to avoid DB + parse overhead on hot paths.

name: sales-to-research

description: Sales agents may hire research agents during business hours

priority: 10 # lower = evaluated first across all org policies

enabled: true

allow: # ALL conditions in 'allow' must be true for delegation to proceed

caller_type: sales_agent

callee_type: research_agent

capability_types: # callee must have one of these capability_types

\- research

\- analysis

conditions: # Additional conditions evaluated after allow block

\- field: time_of_day

operator: between

value: \["06:00", "22:00"\] # UTC

\- field: caller.budget_remaining_usd

operator: ">",

value: 0.10

\- field: context_scope

operator: subset_of

value: \["deal_metadata", "account_tier"\] # callee may only access these

\- field: delegation_depth

operator: "<"

value: 5

hil_threshold_usd: 1.00 # pause for human approval if estimated_cost > this

on_violation: block_and_alert # block_and_alert|block_silent|audit_only|pause_for_approval

## **7.2 Delegation Context Object**

The policy engine evaluates a DelegationContext dataclass. All fields are populated before evaluation begins.

\# services/policy_engine.py

from dataclasses import dataclass

from datetime import datetime

@dataclass

class DelegationContext:

\# Caller

caller_agent_id: str

caller_agent_type: str # the capability_type of the caller

caller_org_id: str

caller_budget_remaining_usd: float

\# Callee

callee_agent_id: str

callee_agent_type: str # capability_type of the callee

callee_trust_score: float

callee_org_id: str

\# Task

capability_type: str # callee's capability_type

context_scope: list\[str\] # requested data grants

estimated_cost_usd: float

budget_cap_usd: float

\# Environment

time_of_day: str # 'HH:MM' UTC

delegation_depth: int # nesting level (0 = top-level)

timestamp: datetime

## **7.3 PolicyDecision Output**

@dataclass

class PolicyDecision:

decision: str # 'allow' | 'block' | 'pause'

policy_id: str | None # UUID of the matching policy

policy_version: int | None

policy_name: str | None

reason: str # human-readable explanation

on_violation: str # what action was taken

## **7.4 Policy Evaluation Algorithm**

The evaluation loop runs synchronously. No async operations. Decision returned immediately.

\# services/policy_engine.py

class PolicyEngine:

def \__init_\_(self, redis_client, db: AsyncSession):

self.redis = redis_client

self.db = db

async def evaluate(self, ctx: DelegationContext, org_id: str) -> PolicyDecision:

\# 1. Load policies from cache or DB, sorted by priority ASC

policies = await self.\_load_policies(org_id)

\# 2. If no policies exist: DEFAULT BLOCK (secure by default)

if not policies:

return PolicyDecision(decision='block', policy_id=None,

reason='No policies defined for org (default deny)')

\# 3. Evaluate each policy in priority order

for policy in policies:

rule = yaml.safe_load(policy.rule_yaml)

\# Check allow block (caller_type, callee_type, capability_types)

if not self.\_matches_allow(rule.get('allow', {}), ctx):

continue # this policy doesn't match, try next

\# Check all conditions

conditions_pass = all(

self.\_evaluate_condition(cond, ctx)

for cond in rule.get('conditions', \[\])

)

if not conditions_pass:

on_v = rule.get('on_violation', 'block_and_alert')

return PolicyDecision(

decision='block' if 'block' in on_v else

'pause' if on_v == 'pause_for_approval' else 'allow',

policy_id=str(policy.id), policy_version=policy.version,

reason=f'Condition failed on policy {policy.name}',

on_violation=on_v

)

\# Check HiTL threshold

hil = rule.get('hil_threshold_usd')

if hil and ctx.estimated_cost_usd > hil:

return PolicyDecision(decision='pause', policy_id=str(policy.id),

reason=f'Estimated cost \${ctx.estimated_cost_usd:.4f} exceeds HiTL threshold \${hil}')

\# All checks passed - this policy allows the delegation

return PolicyDecision(decision='allow', policy_id=str(policy.id),

policy_version=policy.version, reason='Policy matched and all conditions passed')

\# 4. No policy matched → default block

return PolicyDecision(decision='block', reason='No matching policy found (default deny)')

## **7.5 Supported Condition Operators**

| **Operator** | **Field Types**      | **Description**                         | **Example**                                                                    |
| ------------ | -------------------- | --------------------------------------- | ------------------------------------------------------------------------------ |
| \>           | float, int           | Greater than                            | { field: 'caller.budget_remaining_usd', operator: '>', value: 0.10 }           |
| <            | float, int           | Less than                               | { field: 'delegation_depth', operator: '<', value: 5 }                         |
| \>=          | float, int           | Greater than or equal                   | { field: 'callee_trust_score', operator: '>=', value: 0.70 }                   |
| <=           | float, int           | Less than or equal                      | { field: 'estimated_cost_usd', operator: '<=', value: 5.00 }                   |
| \==          | string, bool, number | Exact match                             | { field: 'callee_agent_type', operator: '==', value: 'research' }              |
| !=           | string, bool, number | Not equal                               | { field: 'caller_org_id', operator: '!=', value: 'some-org' }                  |
| in           | string → list        | Value in list                           | { field: 'capability_type', operator: 'in', value: \['research','analysis'\] } |
| not_in       | string → list        | Value not in list                       | { field: 'callee_agent_id', operator: 'not_in', value: \['blocked-agent'\] }   |
| between      | string (HH:MM)       | Time range (UTC)                        | { field: 'time_of_day', operator: 'between', value: \['06:00','22:00'\] }      |
| subset_of    | list → list          | All elements of field are in value list | { field: 'context_scope', operator: 'subset_of', value: \['deal_metadata'\] }  |

# **§8 - Delegation Flow - 13-Step Technical Walkthrough**

## **8.1 DelegationService.initiate() - Full Implementation**

This is the most critical code path in the system. Every delegation passes through these 13 steps in order. Any step failure causes an immediate return with the appropriate HTTP status.

\# services/delegation_service.py

class DelegationService:

def \__init_\_(self, db, redis, policy_engine, budget_service,

audit_service, webhook_service, billing_service,

trust_service, openai_client):

\# ... assign all dependencies

async def initiate(

self,

org: Organization,

caller_agent: Agent,

request: DelegateRequest

) -> DelegationResult:

\# ── STEP 1: Resolve callee agent ─────────────────────────

callee = await self.\_resolve_callee(

org.id, request.callee_agent_id, request.include_cross_org

)

if not callee:

raise NexraError(404, 'AGENT_NOT_FOUND', 'Callee agent not found')

\# ── STEP 2: Validate caller status ───────────────────────

if caller_agent.status == 'quarantined':

raise NexraError(403, 'AGENT_QUARANTINED', 'Caller agent is quarantined')

\# ── STEP 3: Schema validate task payload ─────────────────

try:

jsonschema.validate(request.task\['input'\], callee.input_schema)

except jsonschema.ValidationError as e:

raise NexraError(422, 'SCHEMA_VALIDATION_FAILED', str(e.message))

\# ── STEP 4: Estimate cost ─────────────────────────────────

estimated_cost = callee.pricing\['per_call_usd'\]

\# ── STEP 5: Check budget ──────────────────────────────────

budget_ok = await self.budget_service.check_and_reserve(

org.id, caller_agent.agent_id, estimated_cost, request.budget_cap_usd

)

if not budget_ok.allowed:

raise NexraError(402, 'BUDGET_EXCEEDED',

f'Remaining budget: \${budget_ok.remaining_usd:.4f}')

\# ── STEP 6: Compute delegation depth ─────────────────────

depth = await self.\_compute_depth(request.parent_delegation_id)

if depth >= (org.max_delegation_depth or 5):

raise NexraError(400, 'MAX_DEPTH_EXCEEDED', f'Delegation depth {depth} at limit')

\# ── STEP 7: Policy evaluation ─────────────────────────────

ctx = DelegationContext(

caller_agent_id=caller_agent.agent_id,

caller_agent_type=caller_agent.capability_type,

caller_org_id=str(org.id),

caller_budget_remaining_usd=budget_ok.remaining_usd,

callee_agent_id=callee.agent_id,

callee_agent_type=callee.capability_type,

callee_trust_score=float(callee.trust_score),

callee_org_id=str(callee.org_id),

capability_type=callee.capability_type,

context_scope=request.context_scope,

estimated_cost_usd=estimated_cost,

budget_cap_usd=request.budget_cap_usd,

time_of_day=datetime.utcnow().strftime('%H:%M'),

delegation_depth=depth,

timestamp=datetime.utcnow()

)

decision = await self.policy_engine.evaluate(ctx, str(org.id))

\# ── STEP 8: Create delegation record ─────────────────────

delegation = Delegation(

caller_org_id=org.id,

caller_agent_id=caller_agent.agent_id,

callee_org_id=callee.org_id,

callee_agent_id=callee.agent_id,

task=request.task,

task_hash=sha256_json(request.task),

context_scope=request.context_scope,

policy_id=decision.policy_id,

policy_version=decision.policy_version,

policy_decision=decision.decision,

budget_cap_usd=request.budget_cap_usd,

estimated_cost_usd=estimated_cost,

callback_url=request.callback_url,

delegation_depth=depth,

)

\# ── STEP 9: Handle non-allow decisions ───────────────────

if decision.decision == 'block':

delegation.status = 'blocked'

self.db.add(delegation)

await self.db.commit()

await self.audit_service.append(org.id, 'delegation_blocked',

caller_agent.agent_id, callee.agent_id,

{'delegation_id': str(delegation.id), 'reason': decision.reason,

'policy_id': decision.policy_id})

raise NexraError(403, 'POLICY_BLOCKED', decision.reason,

{'policy_id': decision.policy_id})

if decision.decision == 'pause':

delegation.status = 'pending_approval'

self.db.add(delegation)

await self.db.commit()

await self.\_trigger_hil_notification(org, delegation, decision)

await self.audit_service.append(org.id, 'hil_triggered', ...)

return DelegationResult(status='pending_approval',

delegation_id=str(delegation.id),

poll_url=f'/v1/delegations/{delegation.id}')

\# ── STEP 10: Issue delegation token ──────────────────────

org_secret = decrypt_aes_gcm(org.jwt_secret_enc)

delegation_token = issue_delegation_token(

org_secret, str(delegation.id), callee.agent_id, request.context_scope

)

\# ── STEP 11: Build and sign webhook payload ──────────────

webhook_payload = {

'delegation_id': str(delegation.id),

'task': request.task,

'context_scope': request.context_scope,

'budget_cap_usd': request.budget_cap_usd,

'timeout_ms': request.timeout_ms,

'delegation_token': delegation_token,

'complete_url': f'<https://api.usenexra.com/v1/delegations/{delegation.id}/complete>'

}

signature = sign_webhook_payload(webhook_payload, callee.webhook_secret)

\# ── STEP 12: Deliver webhook ──────────────────────────────

delegation.status = 'in_flight'

self.db.add(delegation)

await self.db.commit()

await self.audit_service.append(org.id, 'delegation_initiated', ...)

if request.callback_url:

\# Async: queue webhook delivery, return 202 immediately

await self.webhook_service.enqueue(callee.webhook_url, webhook_payload, signature)

return DelegationResult(status='in_flight', delegation_id=str(delegation.id))

else:

\# Sync: deliver webhook, await completion, return result

result = await self.webhook_service.deliver_and_await(

callee.webhook_url, webhook_payload, signature,

delegation.id, request.timeout_ms

)

return result

# **§9 - Discovery Engine - Semantic Search & Ranking**

## **9.1 Discovery SQL Query**

The composite score is computed entirely in PostgreSQL to avoid N+1 query patterns. The query runs in a single round-trip.

\-- services/discovery_service.py - raw SQL via SQLAlchemy text()

WITH candidates AS (

SELECT

a.id, a.agent_id, a.name, a.capability_type,

a.trust_score, a.pricing, a.sla, a.is_public, a.status,

1 - (a.embedding &lt;=&gt; :query_embedding) AS semantic_score,

a.pricing->>'per_call_usd' AS price_usd,

a.sla->>'p99_latency_ms' AS latency_ms

FROM agents a

WHERE

\-- Hard filter: exclude quarantined

a.status != 'quarantined'

\-- Hard filter: probationary gating (if org disallows probationary)

AND NOT (a.status = 'probationary' AND :restrict_probationary)

\-- Hard filter: capability_type if specified

AND (:capability_type IS NULL OR a.capability_type = :capability_type)

\-- Hard filter: budget cap

AND (:budget_cap IS NULL OR (a.pricing->>'per_call_usd')::float <= :budget_cap)

\-- Hard filter: latency SLA

AND (:max_latency IS NULL OR (a.sla->>'p99_latency_ms')::int <= :max_latency)

\-- Hard filter: cross-org visibility

AND (a.org_id = :caller_org_id OR a.is_public = TRUE)

\-- Hard filter: exclusion list

AND a.agent_id != ALL(:exclude_agents)

),

price_stats AS (

SELECT MAX((price_usd)::float) as max_price,

MAX((latency_ms)::float) as max_latency

FROM candidates

)

SELECT

c.\*,

(

(c.semantic_score \* 0.50)

\+ (c.trust_score \* 0.25)

\+ ((1 - (c.price_usd::float / NULLIF(ps.max_price, 0))) \* 0.15)

\+ ((1 - (c.latency_ms::float / NULLIF(ps.max_latency, 0))) \* 0.10)

) AS composite_score

FROM candidates c, price_stats ps

ORDER BY composite_score DESC

LIMIT :limit;

## **9.2 Embedding Generation**

\# services/agent_service.py

async def \_embed(self, text: str) -> list\[float\]:

"""Generate 1536-dim embedding. Retries on transient OpenAI errors."""

for attempt in range(3):

try:

resp = await self.openai.embeddings.create(

input=text,

model='text-embedding-3-small'

)

return resp.data\[0\].embedding

except openai.RateLimitError:

await asyncio.sleep(2 \*\* attempt)

raise RuntimeError('Failed to generate embedding after 3 attempts')

# **§10 - Trust Score System**

## **10.1 Score Formula**

trust_score = (

(success_rate \* 0.40) +

(sla_compliance \* 0.30) +

(cost_accuracy \* 0.20) +

(policy_violations_inverse \* 0.10)

)

| **Component**             | **Weight** | **Definition**                                                                              | **Value Range** |
| ------------------------- | ---------- | ------------------------------------------------------------------------------------------- | --------------- |
| success_rate              | 40%        | Completed delegations / total delegations attempted (rolling 30-day window)                 | 0.0 - 1.0       |
| sla_compliance            | 30%        | Delegations where actual latency_ms <= callee's registered p99_latency_ms / total completed | 0.0 - 1.0       |
| cost_accuracy             | 20%        | 1 - abs(actual_cost - estimated_cost) / estimated_cost. Clipped to \[0,1\].                 | 0.0 - 1.0       |
| policy_violations_inverse | 10%        | 1 - (policy_violations_last_30_days / total_delegations). Clipped to \[0,1\].               | 0.0 - 1.0       |

## **10.2 Status Transitions**

| **Current Status**     | **Trigger**                                             | **New Status** | **Effect**                                                  |
| ---------------------- | ------------------------------------------------------- | -------------- | ----------------------------------------------------------- |
| probationary           | trust_score >= 0.70 AND delegation_count >= 10          | active         | Full policy access. Visible in default discovery results.   |
| active                 | trust_score < 0.40                                      | probationary   | Restricted by default policy. Demoted in discovery ranking. |
| active OR probationary | trust_score < 0.20                                      | quarantined    | Excluded from discovery. All pending delegations blocked.   |
| probationary           | Manual admin activation (POST /agents/{id}/activate)    | active         | Overrides automatic threshold requirement.                  |
| quarantined            | Manual admin re-activation (POST /agents/{id}/activate) | probationary   | Agent must re-build trust score to reach 'active'.          |

## **10.3 Trust Score Update Implementation**

\# services/trust_service.py

class TrustService:

WINDOW_DAYS = 30

async def update_after_delegation(

self, agent_id: str, org_id: str, delegation: Delegation

) -> float:

\# Fetch rolling 30-day stats for this agent

stats = await self.\_fetch_rolling_stats(agent_id, org_id)

success_rate = stats.completed / max(stats.total, 1)

sla_compliance = stats.sla_met / max(stats.completed, 1)

cost_accuracy = max(0.0, 1.0 - abs(

delegation.actual_cost_usd - delegation.estimated_cost_usd

) / max(delegation.estimated_cost_usd, 0.001))

violations_inv = max(0.0, 1.0 - stats.violations / max(stats.total, 1))

new_score = round(

success_rate \* 0.40

\+ sla_compliance \* 0.30

\+ cost_accuracy \* 0.20

\+ violations_inv \* 0.10,

3 # 3 decimal places

)

\# Fetch current score before update

agent = await self.db.get(Agent, (agent_id, org_id))

score_before = float(agent.trust_score)

\# Update agent record

agent.trust_score = new_score

agent.delegation_count += 1

\# Apply automatic status transitions

if new_score < 0.20:

agent.status = 'quarantined'

elif new_score < 0.40:

if agent.status == 'active': agent.status = 'probationary'

elif new_score >= 0.70 and agent.delegation_count >= 10:

if agent.status == 'probationary': agent.status = 'active'

await self.db.commit()

\# Append trust_score_events record

event = TrustScoreEvent(

agent_id=agent_id, org_id=org_id,

delegation_id=delegation.id,

score_before=score_before, score_after=new_score,

components={

'success_rate': success_rate,

'sla_compliance': sla_compliance,

'cost_accuracy': cost_accuracy,

'policy_violations_inverse': violations_inv

}

)

self.db.add(event)

await self.db.commit()

return new_score

# **§11 - Spend Metering & Budget Enforcement**

## **11.1 Budget Check & Reserve**

Budget checks use SELECT FOR UPDATE to prevent race conditions when multiple delegations fire concurrently for the same agent.

\# services/budget_service.py

class BudgetService:

async def check_and_reserve(

self,

org_id: str,

agent_id: str,

estimated_cost: float,

request_cap: float

) -> BudgetCheckResult:

today = date.today()

first_of_month = today.replace(day=1)

async with self.db.begin():

\# Lock rows for this agent's current daily and monthly budgets

daily = await self.db.execute(

select(AgentBudget)

.where(AgentBudget.agent_id == agent_id,

AgentBudget.org_id == org_id,

AgentBudget.period == today,

AgentBudget.period_type == 'daily')

.with_for_update()

)

daily_row = daily.scalar_one_or_none()

\# Check per-delegation cap from request

if estimated_cost > request_cap:

return BudgetCheckResult(

allowed=False,

reason='per_delegation_cap',

remaining_usd=request_cap

)

\# Check daily cap if configured

if daily_row:

remaining = float(daily_row.cap_usd) - float(daily_row.spent_usd)

if estimated_cost > remaining:

return BudgetCheckResult(

allowed=False, reason='daily_cap',

remaining_usd=remaining

)

return BudgetCheckResult(allowed=True, remaining_usd=request_cap - estimated_cost)

async def settle(

self, org_id: str, agent_id: str, actual_cost: float

) -> None:

"""Called after delegation completes. Updates spent_usd."""

today = date.today()

first_of_month = today.replace(day=1)

\# Upsert daily and monthly spend rows

for period, period_type in \[(today, 'daily'), (first_of_month, 'monthly')\]:

await self.db.execute(

insert(AgentBudget).values(

agent_id=agent_id, org_id=org_id,

period=period, period_type=period_type,

cap_usd=999999, spent_usd=actual_cost # cap set separately

).on_conflict_do_update(

index_elements=\['agent_id','org_id','period','period_type'\],

set\_={'spent_usd': AgentBudget.spent_usd + actual_cost,

'updated_at': datetime.utcnow()}

)

)

await self.db.commit()

# **§12 - Webhook Delivery & HMAC Signing**

## **12.1 Synchronous Delivery (MVP)**

\# services/webhook_service.py

class WebhookService:

TIMEOUT_SECONDS = 30

async def deliver_and_await(

self,

webhook_url: str,

payload: dict,

signature: str,

delegation_id: str,

timeout_ms: int

) -> dict:

effective_timeout = min(timeout_ms / 1000, self.TIMEOUT_SECONDS - 0.1)

headers = {

'Content-Type': 'application/json',

'X-Nexra-Signature': signature,

'X-Delegation-ID': delegation_id,

'X-Nexra-Timestamp': str(int(time.time())),

}

async with httpx.AsyncClient(timeout=effective_timeout) as client:

try:

resp = await client.post(webhook_url, json=payload, headers=headers)

except httpx.TimeoutException:

raise NexraError(408, 'DELEGATION_TIMEOUT',

f'Callee did not respond within {timeout_ms}ms')

except httpx.RequestError as e:

raise NexraError(503, 'CALLEE_WEBHOOK_FAILED', str(e))

if resp.status_code in (401, 403):

\# Callee rejected signature - do NOT retry

raise NexraError(503, 'WEBHOOK_SIGNATURE_REJECTED',

'Callee returned 401/403 - likely HMAC mismatch. Not retried.')

if resp.status_code >= 500:

\# Single retry for server errors

await asyncio.sleep(1)

resp = await client.post(webhook_url, json=payload, headers=headers)

if not resp.is_success:

raise NexraError(503, 'CALLEE_WEBHOOK_FAILED',

f'Callee returned {resp.status_code}')

\# Callee returns result inline in webhook response body

\# OR posts to /complete endpoint (token-based completion)

\# Sync mode: result is in the response body

return resp.json()

## **12.2 Async Delivery - Celery Worker (Production)**

\# workers/webhook_worker.py

@celery_app.task(bind=True, max_retries=3, default_retry_delay=2)

def deliver_webhook(self, webhook_url: str, payload: dict, signature: str,

delegation_id: str, timeout_ms: int):

"""

Retry policy: exponential backoff

Attempt 1: immediate

Attempt 2: 2s delay

Attempt 3: 4s delay

After 3 failures: mark delegation 'failed', write to dead letter queue

"""

try:

\# Synchronous httpx call inside Celery task

with httpx.Client(timeout=timeout_ms/1000) as client:

resp = client.post(webhook_url, json=payload, headers={

'X-Nexra-Signature': signature,

'X-Delegation-ID': delegation_id

})

if resp.status_code >= 400:

raise ValueError(f'Webhook returned {resp.status_code}')

except Exception as exc:

if self.request.retries >= self.max_retries:

\# Write to dead letter

dead_letter_queue.append({'delegation_id': delegation_id, 'error': str(exc)})

mark_delegation_failed.delay(delegation_id, reason=str(exc))

else:

raise self.retry(exc=exc, countdown=2 \*\* self.request.retries)

# **§13 - Audit Log - Immutability & Structure**

## **13.1 Event Types & Payloads**

| **event_type**          | **Trigger**                                            | **Required details fields**                                                                          |
| ----------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| policy_evaluated        | Every delegation attempt (before allow/block decision) | { policy_id, policy_version, decision, reason, conditions_evaluated: \[\] }                          |
| delegation_initiated    | After policy allows, before webhook delivery           | { delegation_id, caller_agent, callee_agent, estimated_cost_usd, context_scope: \[\] }               |
| delegation_completed    | After callee posts result to /complete                 | { delegation_id, actual_cost_usd, latency_ms, llm_tokens, outcome: 'success' }                       |
| delegation_failed       | Callee error, timeout, or schema validation failure    | { delegation_id, error_code, error_message, latency_ms }                                             |
| delegation_blocked      | Policy decision = 'block'                              | { delegation_id, policy_id, reason, caller_agent, callee_agent }                                     |
| delegation_timeout      | Callee did not respond within timeout_ms               | { delegation_id, timeout_ms, callee_webhook_url }                                                    |
| agent_quarantined       | Automatic (trust < 0.20) or manual admin action        | { agent_id, reason, trust_score_at_quarantine, trigger: 'auto'\|'manual' }                           |
| agent_activated         | Manual admin re-activation                             | { agent_id, previous_status, admin_action: true }                                                    |
| budget_exceeded         | Budget cap check fails                                 | { agent_id, cap_usd, spent_usd, estimated_cost_usd, cap_type: 'daily'\|'monthly'\|'per_delegation' } |
| hil_triggered           | Policy decision = 'pause' (HiTL gate)                  | { delegation_id, hil_threshold_usd, estimated_cost_usd, approval_deadline }                          |
| hil_approved            | Admin POSTs /delegations/{id}/approve                  | { delegation_id, approved_by, approved_at, original_trigger }                                        |
| hil_expired             | HiTL approval deadline passed without response         | { delegation_id, approval_deadline }                                                                 |
| anomaly_detected        | Spend anomaly detection fires                          | { agent_id, current_hour_spend, baseline_mean, baseline_std, sigma_multiple }                        |
| circuit_breaker_tripped | Failure rate threshold exceeded                        | { agent_id, failure_rate, window_minutes, threshold }                                                |

## **13.2 AuditService Implementation**

\# services/audit_service.py

class AuditService:

"""

All writes go through this class. The DB trigger provides a second line

of defense, but no code path should attempt UPDATE or DELETE on audit_log.

"""

async def append(

self,

org_id: str,

event_type: str,

actor_agent_id: str | None,

target_agent_id: str | None,

details: dict,

delegation_id: str | None = None,

cost_usd: float | None = None

) -> AuditLog:

"""Append-only. Never update or delete."""

entry = AuditLog(

delegation_id=delegation_id,

org_id=org_id,

event_type=event_type,

actor_agent_id=actor_agent_id,

target_agent_id=target_agent_id,

details=details,

cost_usd=cost_usd

)

self.db.add(entry)

await self.db.commit()

return entry

async def query(

self,

org_id: str,

filters: AuditQueryFilters,

cursor: str | None = None,

limit: int = 50

) -> tuple\[list\[AuditLog\], str | None\]:

"""Cursor-based pagination. cursor = last seen audit_log UUID."""

q = select(AuditLog).where(AuditLog.org_id == org_id)

if filters.agent_id:

q = q.where(AuditLog.actor_agent_id == filters.agent_id)

if filters.event_type:

q = q.where(AuditLog.event_type == filters.event_type)

if filters.date_from:

q = q.where(AuditLog.created_at >= filters.date_from)

if filters.date_to:

q = q.where(AuditLog.created_at <= filters.date_to)

if cursor:

\# cursor is the created_at of the last item on previous page

q = q.where(AuditLog.created_at < cursor)

q = q.order_by(AuditLog.created_at.desc()).limit(limit + 1)

results = (await self.db.execute(q)).scalars().all()

next_cursor = str(results\[-1\].created_at) if len(results) > limit else None

return results\[:limit\], next_cursor

# **§14 - Circuit Breakers & Anomaly Detection**

## **14.1 Circuit Breaker Logic**

| **Trigger**                  | **Threshold (Default)**                    | **Action**                                                                  | **Recovery**                          |
| ---------------------------- | ------------------------------------------ | --------------------------------------------------------------------------- | ------------------------------------- |
| Failure rate (10-min window) | \> 30% failures                            | Status → probationary. Policy access restricted.                            | Automatic if failure rate improves    |
| Failure rate (10-min window) | \> 50% failures                            | Status → quarantined. Excluded from discovery. Pending delegations blocked. | Manual admin re-activation only       |
| Delegation depth             | \> 5 (configurable per org)                | Delegation blocked with DEPTH_EXCEEDED error.                               | No recovery needed - structural block |
| Out-of-scope context request | Any context key not in context_scope grant | Delegation blocked. Logged as policy_violation.                             | No recovery - enforcement action      |

## **14.2 Circuit Breaker Implementation**

\# services/anomaly_service.py

class CircuitBreakerService:

WINDOW_MINUTES = 10

PROBATIONARY_THRESHOLD = 0.30

QUARANTINE_THRESHOLD = 0.50

async def check_and_update(self, agent_id: str, org_id: str) -> None:

window_start = datetime.utcnow() - timedelta(minutes=self.WINDOW_MINUTES)

stats = await self.db.execute(

select(

func.count(Delegation.id).label('total'),

func.count().filter(Delegation.status == 'failed').label('failures')

)

.where(Delegation.callee_agent_id == agent_id,

Delegation.created_at >= window_start)

)

row = stats.one()

if row.total < 5:

return # Not enough data for statistical significance

failure_rate = row.failures / row.total

agent = await self.\_get_agent(agent_id, org_id)

if failure_rate > self.QUARANTINE_THRESHOLD:

if agent.status != 'quarantined':

agent.status = 'quarantined'

await self.db.commit()

await self.audit_service.append(org_id, 'circuit_breaker_tripped',

agent_id, None,

{'failure_rate': failure_rate, 'threshold': self.QUARANTINE_THRESHOLD,

'window_minutes': self.WINDOW_MINUTES, 'action': 'quarantined'})

await self.\_cancel_pending_delegations(agent_id, org_id)

elif failure_rate > self.PROBATIONARY_THRESHOLD:

if agent.status == 'active':

agent.status = 'probationary'

await self.db.commit()

await self.audit_service.append(org_id, 'circuit_breaker_tripped', ...)

## **14.3 Spend Anomaly Detection**

Celery beat job runs every hour. For each active agent with delegations in the last 7 days, computes a rolling baseline and alerts if current-hour spend is statistically anomalous.

\# workers/anomaly_worker.py

@celery_app.task

def check_spend_anomalies():

"""Runs hourly via Celery beat."""

active_agents = get_agents_with_recent_spend()

for agent_id, org_id in active_agents:

baseline = compute_7day_hourly_baseline(agent_id, org_id)

current_hour_spend = get_current_hour_spend(agent_id, org_id)

if baseline.std > 0:

sigma = (current_hour_spend - baseline.mean) / baseline.std

if sigma >= 3.0:

trigger_anomaly_alert(agent_id, org_id, current_hour_spend,

baseline.mean, baseline.std, sigma)

def compute_7day_hourly_baseline(agent_id, org_id):

"""Returns (mean, std) of hourly spend over last 7 days."""

\# SQL: GROUP BY hour, compute mean + stddev

hourly_totals = \[\]

for h in range(7 \* 24):

hour_start = datetime.utcnow() - timedelta(hours=h+1)

hour_end = datetime.utcnow() - timedelta(hours=h)

total = get_spend_in_window(agent_id, org_id, hour_start, hour_end)

hourly_totals.append(total)

return Baseline(mean=statistics.mean(hourly_totals), std=statistics.stdev(hourly_totals))

# **§15 - Human-in-the-Loop (HiTL) Gate**

## **15.1 HiTL Flow**

- Policy evaluation returns decision='pause' (estimated_cost > hil_threshold_usd).
- DelegationService creates delegation record with status='pending_approval'.
- Nexra fires a webhook notification to org's approval_url with delegation details.
- Nexra also sends email notification (SendGrid / SES) to org admin email.
- Delegation held in 'pending_approval' for up to 24 hours (configurable).
- Admin calls POST /delegations/{id}/approve or /reject.
- On approve: delegation proceeds immediately (issue token, deliver webhook).
- On reject: delegation status → 'blocked', audit entry written.
- On timeout (24h no response): status → 'failed', audit entry 'hil_expired' written.

## **15.2 HiTL Notification Payload**

{

"event": "hil_approval_required",

"delegation_id": "del_01JFXP...",

"caller_agent": { "agent_id": "sales-agent-v1", "name": "Sales Agent" },

"callee_agent": { "agent_id": "research-agent-v2", "name": "Research Agent" },

"estimated_cost_usd": 1.45,

"hil_threshold_usd": 1.00,

"task_summary": { "type": "research", "input_keys": \["company_name"\] },

"context_scope": \["deal_metadata", "account_tier"\],

"approval*url": "<https://api.usenexra.com/v1/delegations/del*.../approve>",

"reject*url": "<https://api.usenexra.com/v1/delegations/del*.../reject>",

"approval_deadline": "2026-03-14T21:00:00Z"

}

# **§16 - Stripe Billing Integration**

## **16.1 Billing Architecture**

| **Billing Model**          | Usage-based (metered) via Stripe Metering API. One meter per org per delegation type.                             |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| **Stripe Objects**         | Customer (per org), Subscription (plan + metered add-ons), Meter (delegation_count), Meter Event (per delegation) |
| **Plans**                  | Starter (free tier), Growth (\$499/mo base + \$0.003/delegation over 10K), Enterprise (custom)                    |
| **Cross-org Settlement**   | Stripe Connect. Callee org receives 80% of per_call_usd via Connect transfer. Nexra retains 20%.                  |
| **Connect Payout Cadence** | Monthly. Batched. Callee must complete Stripe Connect onboarding (KYC) before first payout.                       |
| **Billing Event Queue**    | Celery task. POST /delegate triggers a background task to record Stripe Meter Event after settlement.             |

## **16.2 Stripe Meter Event - Per Delegation**

\# services/billing_service.py

class BillingService:

async def record_delegation_usage(

self,

org: Organization,

delegation: Delegation,

actual_cost_usd: float

) -> None:

"""Record usage event with Stripe Metering API."""

event = stripe.billing.MeterEvent.create(

event_name='nexra_delegation',

payload={

'stripe_customer_id': org.stripe_id,

'value': '1', # 1 delegation

},

timestamp=int(delegation.created_at.timestamp())

)

async def trigger_connect_payout(

self,

callee_org: Organization,

amount_usd: float, # 80% of per_call_usd

delegation: Delegation

) -> None:

"""Create Stripe Connect transfer for cross-org delegation revenue."""

if not callee_org.stripe_connect_account_id:

\# Queue for when Connect onboarding is complete

await self.\_queue_pending_payout(callee_org.id, amount_usd, delegation.id)

return

stripe.Transfer.create(

amount=int(amount_usd \* 100), # cents

currency='usd',

destination=callee_org.stripe_connect_account_id,

metadata={'delegation_id': str(delegation.id)}

)

# **§17 - SDK Design - nexra-py & nexra-ts**

## **17.1 nexra-py - Python SDK**

\# sdk/nexra/client.py

import httpx

from typing import Any

from dataclasses import dataclass

class NexraClient:

def \__init_\_(self, api_key: str, agent_id: str,

base_url: str = '<https://api.usenexra.com/v1>'):

self.base_url = base_url

self.\_headers = {

'Authorization': f'Bearer {api_key}',

'X-Agent-ID': agent_id,

'Content-Type': 'application/json'

}

self.\_client = httpx.AsyncClient(headers=self.\_headers, timeout=60)

async def register(self, \*\*kwargs) -> RegisterResult:

resp = await self.\_client.post(f'{self.base_url}/agents/register', json=kwargs)

resp.raise_for_status()

return RegisterResult(\*\*resp.json()\['data'\])

async def discover(

self,

query: str,

capability_type: str | None = None,

budget_cap: float | None = None,

max_latency_ms: int | None = None,

limit: int = 5

) -> list\[AgentMatch\]:

payload = {'query': query, 'limit': limit}

if capability_type: payload\['capability_type'\] = capability_type

if budget_cap: payload\['budget_cap_usd'\] = budget_cap

if max_latency_ms: payload\['max_latency_ms'\] = max_latency_ms

resp = await self.\_client.post(f'{self.base_url}/capabilities/discover', json=payload)

resp.raise_for_status()

return \[AgentMatch(\*\*m) for m in resp.json()\['data'\]\['matches'\]\]

async def delegate(

self,

agent_id: str,

task: dict,

context_scope: list\[str\] = \[\],

budget_cap: float = 1.0,

timeout_ms: int = 30000,

callback_url: str | None = None

) -> DelegationResult:

resp = await self.\_client.post(f'{self.base_url}/delegate', json={

'callee_agent_id': agent_id,

'task': task,

'context_scope': context_scope,

'budget_cap_usd': budget_cap,

'timeout_ms': timeout_ms,

'callback_url': callback_url

})

resp.raise_for_status()

return DelegationResult(\*\*resp.json()\['data'\])

async def hire(

self,

capability: str,

task: dict,

context_scope: list\[str\] = \[\],

budget_cap: float = 1.0,

) -> DelegationResult:

"""Convenience: discover + delegate in one call."""

matches = await self.discover(capability, budget_cap=budget_cap, limit=1)

if not matches:

raise ValueError(f'No agents found for capability: {capability}')

return await self.delegate(

agent_id=matches\[0\].agent_id,

task=task,

context_scope=context_scope,

budget_cap=budget_cap

)

async def \__aenter_\_(self): return self

async def \__aexit_\_(self, \*\_): await self.\_client.aclose()

# **§18 - Framework Adapters - LangGraph, CrewAI, Bedrock, A2A**

## **18.1 LangGraph Adapter**

Exposes Nexra hire() as a LangGraph tool node. Zero changes required to existing LangGraph graph definitions.

\# sdk/nexra/adapters/langgraph.py

from langgraph.prebuilt import ToolNode

from langchain_core.tools import tool

from nexra import NexraClient

def nexra_tool(client: NexraClient):

@tool

async def hire_agent(capability: str, task_input: dict,

budget_cap: float = 1.0) -> dict:

"""Hire a Nexra-registered agent for a given capability."""

result = await client.hire(capability, {'input': task_input}, budget_cap=budget_cap)

return result.result

return hire_agent

\# Usage in a LangGraph graph:

\# tools = \[nexra_tool(nexra_client)\]

\# graph = StateGraph(State).add_node('agent', create_react_agent(llm, tools))

## **18.2 CrewAI Adapter**

\# sdk/nexra/adapters/crewai.py

from crewai_tools import BaseTool

from nexra import NexraClient

class NexraTool(BaseTool):

name: str = 'nexra_hire'

description: str = 'Hire a specialized agent from Nexra registry for a capability'

client: NexraClient

def \_run(self, capability: str, task_input: dict, budget_cap: float = 1.0) -> str:

import asyncio

result = asyncio.run(

self.client.hire(capability, {'input': task_input}, budget_cap=budget_cap)

)

return str(result.result)

## **18.3 AWS Bedrock Adapter**

When a webhook_url matches a Bedrock endpoint pattern, Nexra uses this adapter to handle SigV4 auth and payload translation.

\# sdk/nexra/adapters/bedrock.py

import boto3

from botocore.auth import SigV4Auth

from botocore.awsrequest import AWSRequest

BEDROCK_ENDPOINT_PATTERNS = \[

'bedrock-agent-runtime.',

'runtime.sagemaker.amazonaws.com'

\]

def is_bedrock_endpoint(url: str) -> bool:

return any(p in url for p in BEDROCK_ENDPOINT_PATTERNS)

async def deliver_to_bedrock(

webhook_url: str,

nexra_payload: dict,

aws_credentials: dict # { access_key, secret_key, region }

) -> dict:

"""

Translates Nexra delegation payload to Bedrock InvokeAgent format.

Handles SigV4 signing transparently.

"""

bedrock_payload = {

'agentId': \_extract_agent_id_from_url(webhook_url),

'agentAliasId': 'TSTALIASID',

'sessionId': nexra_payload\['delegation_id'\],

'inputText': nexra_payload\['task'\]\['input'\].get('prompt', str(nexra_payload\['task'\]\['input'\]))

}

session = boto3.Session(

aws_access_key_id=aws_credentials\['access_key'\],

aws_secret_access_key=aws_credentials\['secret_key'\],

region_name=aws_credentials\['region'\]

)

client = session.client('bedrock-agent-runtime')

response = client.invoke_agent(\*\*bedrock_payload)

\# Parse streaming response from Bedrock

output_text = ''

for event in response\['completion'\]:

if 'chunk' in event:

output_text += event\['chunk'\]\['bytes'\].decode()

return {'result': output_text, 'source': 'bedrock'}

## **18.4 A2A Native Compatibility**

Nexra accepts A2A Agent Cards at registration time. A2A-compliant agents need no SDK changes - they register their Agent Card JSON and receive a Nexra agent_id back.

\# api/routers/agents.py - A2A Agent Card registration endpoint

@router.post('/agents/register/a2a')

async def register_a2a_agent(agent_card: dict, ...):

"""

Accepts a Google A2A Agent Card and maps to Nexra's registration format.

agent_card fields: name, description, url, capabilities, skills

"""

nexra_payload = {

'agent_id': slugify(agent_card\['name'\]),

'name': agent_card\['name'\],

'description': agent_card.get('description', agent_card\['name'\]),

'capability_type': \_map_a2a_capabilities(agent_card.get('capabilities', {})),

'webhook_url': agent_card\['url'\],

\# A2A agents don't define typed JSON schemas - use passthrough schemas

'input_schema': { 'type': 'object' },

'output_schema': { 'type': 'object' },

'pricing': { 'per_call_usd': 0.0 }, # A2A agents set their own pricing

'sla': { 'p99_latency_ms': 30000, 'availability': 0.99 }

}

return await agent_service.register(org.id, AgentRegisterRequest(\*\*nexra_payload))

# **§19 - Environment Configuration & Secrets**

## **19.1 All Required Environment Variables**

| **Variable**                 | **Required** | **Description**                                                | **Example**                                    |
| ---------------------------- | ------------ | -------------------------------------------------------------- | ---------------------------------------------- |
| DATABASE_URL                 | Yes          | PostgreSQL async connection string                             | postgresql+asyncpg://user:pass@host:5432/nexra |
| REDIS_URL                    | Yes          | Redis connection string                                        | redis://localhost:6379/0                       |
| OPENAI_API_KEY               | Yes          | OpenAI API key for embeddings (text-embedding-3-small)         | sk-...                                         |
| STRIPE_SECRET_KEY            | Yes          | Stripe secret key for billing                                  | sk*live*...                                    |
| STRIPE_WEBHOOK_SECRET        | Yes          | Stripe webhook signing secret (for billing event verification) | whsec\_...                                     |
| STRIPE_DELEGATION_METER_ID   | Yes          | Stripe Meter ID for delegation usage events                    | mtr\_...                                       |
| SECRET_KEY_ENCRYPTION_KEY    | Yes          | 32-byte hex key for AES-GCM encryption of per-org JWT secrets  | 000aabb...                                     |
| SENTRY_DSN                   | Yes (prod)   | Sentry DSN for error tracking                                  | https://...@sentry.io/...                      |
| ENVIRONMENT                  | Yes          | development \| staging \| production                           | production                                     |
| LOG_LEVEL                    | No           | Log verbosity. Default: INFO                                   | DEBUG                                          |
| RATE_LIMIT_GROWTH_RPM        | No           | Rate limit for Growth plan orgs. Default: 1000                 | 1000                                           |
| MAX_DELEGATION_DEPTH_DEFAULT | No           | Default max delegation chain depth. Default: 5                 | 5                                              |
| WEBHOOK_TIMEOUT_DEFAULT_MS   | No           | Default webhook timeout. Default: 30000                        | 30000                                          |
| HIL_APPROVAL_TTL_HOURS       | No           | Hours before HiTL approval expires. Default: 24                | 24                                             |
| ANOMALY_SIGMA_THRESHOLD      | No           | Sigma multiple for spend anomaly detection. Default: 3.0       | 3.0                                            |
| CELERY_BROKER_URL            | Prod only    | Redis URL for Celery broker. Defaults to REDIS_URL.            | redis://...                                    |

## **19.2 core/config.py - Pydantic Settings**

\# core/config.py

from pydantic_settings import BaseSettings

from functools import lru_cache

class Settings(BaseSettings):

database_url: str

redis_url: str

openai_api_key: str

stripe_secret_key: str

stripe_webhook_secret: str

stripe_delegation_meter_id: str

secret_key_encryption_key: str # must be exactly 32 hex bytes

sentry_dsn: str | None = None

environment: str = 'development'

log_level: str = 'INFO'

rate_limit_growth_rpm: int = 1000

rate_limit_starter_rpm: int = 100

max_delegation_depth_default: int = 5

webhook_timeout_default_ms: int = 30000

hil_approval_ttl_hours: int = 24

anomaly_sigma_threshold: float = 3.0

celery_broker_url: str | None = None # falls back to redis_url

@property

def celery_broker(self) -> str:

return self.celery_broker_url or self.redis_url

class Config:

env_file = '.env'

case_sensitive = False

@lru_cache

def get_settings() -> Settings:

return Settings()

# **§20 - Testing Strategy - Unit, Integration, E2E**

## **20.1 Test Pyramid**

| **Unit Tests**        | Tests/unit/. No DB. No Redis. No HTTP. Mock all external dependencies. Focus: policy_engine, trust_service, budget_service, crypto, JWT logic. Target: >90% line coverage on service layer. |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Integration Tests** | tests/integration/. Real Postgres (test schema), real Redis (test DB index). Mock OpenAI + Stripe. Tests full DB read/write round-trips, audit immutability, FK constraints, audit trigger. |
| **E2E Tests**         | tests/e2e/. Full app running via httpx.AsyncClient(app=app). Two real agent fixtures (Sales, Research) with webhook handlers. Tests complete delegation flow end-to-end.                    |
| **Contract Tests**    | tests/contracts/. Validate all API request/response shapes match Pydantic schemas. Run on every PR.                                                                                         |

## **20.2 Critical Test Cases**

| **Test ID** | **Category**    | **Description**                                                                | **Assertion**                                                                    |
| ----------- | --------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------- |
| T-001       | Policy          | No policies defined → delegation blocked                                       | PolicyEngine returns decision='block' with 'default deny' reason                 |
| T-002       | Policy          | Allow policy matches, all conditions pass → allow                              | PolicyDecision.decision == 'allow', policy_id is set                             |
| T-003       | Policy          | Allow policy matches, condition fails → block                                  | PolicyDecision.decision == 'block', on_violation='block_and_alert'               |
| T-004       | Policy          | estimated_cost > hil_threshold_usd → pause                                     | PolicyDecision.decision == 'pause'                                               |
| T-005       | Policy          | Context scope NOT subset of allowed → block                                    | PolicyDecision.decision == 'block'                                               |
| T-006       | Budget          | estimated_cost + spent > daily cap → 402                                       | BudgetCheckResult.allowed == False, 402 HTTP response                            |
| T-007       | Budget          | concurrent delegations don't double-spend                                      | SELECT FOR UPDATE prevents race. Final spent_usd is atomic.                      |
| T-008       | Auth            | Valid API key + valid X-Agent-ID → 200                                         | get_org_and_agent returns (org, agent)                                           |
| T-009       | Auth            | Valid API key + wrong org agent_id → 401                                       | HTTPException 401 raised                                                         |
| T-010       | Auth            | Quarantined agent → 403 on any endpoint                                        | HTTPException 403 raised                                                         |
| T-011       | Delegation JWT  | Single-use enforcement - second use → error                                    | Redis jti marked used. verify_delegation_token raises ValueError.                |
| T-012       | Delegation JWT  | Expired token → error                                                          | JWTError raised. Delegation rejected.                                            |
| T-013       | Audit Log       | INSERT succeeds; UPDATE raises exception                                       | DB trigger raises EXCEPTION on UPDATE                                            |
| T-014       | Audit Log       | DELETE raises exception                                                        | DB trigger raises EXCEPTION on DELETE                                            |
| T-015       | Trust Score     | 10 successes, all under SLA → trust increases to ~0.95+                        | Agent status transitions from probationary to active                             |
| T-016       | Trust Score     | trust_score drops < 0.20 → quarantine                                          | agent.status == 'quarantined'                                                    |
| T-017       | Discovery       | Quarantined agent excluded from results                                        | No quarantined agent in matches\[\]                                              |
| T-018       | Discovery       | Budget filter excludes expensive agents                                        | No agent with per_call_usd > budget_cap in results                               |
| T-019       | Webhook         | HMAC signature mismatch → 401, delegation failed                               | Delegation.status == 'failed'. Not retried.                                      |
| T-020       | Webhook         | Callee timeout → 408 response                                                  | Delegation.status == 'timeout'. Audit log entry written.                         |
| T-021       | Schema          | Task payload missing required field → 422                                      | 422 with SCHEMA_VALIDATION_FAILED code                                           |
| T-022       | Circuit Breaker | \>50% failure rate in 10-min window → quarantine                               | agent.status == 'quarantined'. audit_log entry 'circuit_breaker_tripped'.        |
| T-023       | E2E             | Full delegation round-trip: register → discover → delegate → complete → settle | All audit_log entries present. delegation.status == 'completed'. budget updated. |

# **§21 - Deployment - Railway MVP → AWS ECS Production**

## **21.1 Dockerfile**

\# docker/Dockerfile

\# ── Stage 1: Builder ─────────────────────────────────────────

FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install poetry==1.8.0

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.in-project true \\

&& poetry install --no-dev --no-interaction --no-ansi

\# ── Stage 2: Runtime ─────────────────────────────────────────

FROM python:3.12-slim AS runtime

RUN adduser --disabled-password --gecos '' appuser

WORKDIR /app

COPY --from=builder /app/.venv ./.venv

COPY . .

USER appuser

ENV PATH="/app/.venv/bin:\$PATH"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s \\

CMD curl -f <http://localhost:8000/health> || exit 1

CMD \["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"\]

## **21.2 Railway MVP Configuration**

\# railway.toml

\[build\]

builder = "dockerfile"

dockerfilePath = "docker/Dockerfile"

\[deploy\]

healthcheckPath = "/health"

healthcheckTimeout = 30

restartPolicyType = "ON_FAILURE"

restartPolicyMaxRetries = 3

\[services.postgres\]

plugin = "postgresql"

version = "16"

extensions = \["vector"\]

\[services.redis\]

plugin = "redis"

version = "7"

## **21.3 Docker Compose - Local Development**

\# docker/docker-compose.yml

version: '3.9'

services:

api:

build: { context: .., dockerfile: docker/Dockerfile }

ports: \['8000:8000'\]

env_file: .env

depends_on:

postgres: { condition: service_healthy }

redis: { condition: service_healthy }

volumes: \['..:/app'\] # hot reload in dev

command: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

worker:

build: { context: .., dockerfile: docker/Dockerfile.worker }

env_file: .env

depends_on: \[postgres, redis\]

command: celery -A workers.celery_app worker --loglevel=info -Q webhooks,billing,anomaly

postgres:

image: pgvector/pgvector:pg16

environment:

POSTGRES_DB: nexra

POSTGRES_USER: nexra

POSTGRES_PASSWORD: nexra

ports: \['5432:5432'\]

healthcheck:

test: \['CMD-SHELL', 'pg_isready -U nexra'\]

interval: 5s

timeout: 5s

retries: 5

redis:

image: redis:7-alpine

ports: \['6379:6379'\]

healthcheck:

test: \['CMD', 'redis-cli', 'ping'\]

interval: 5s

timeout: 5s

retries: 5

# **§22 - 48-Hour MVP Build Execution Plan**

## **22.1 Hour-by-Hour Schedule**

| **Window** | **Hours** | **Deliverables**                                                                                                                                                                   | **Done When...**                                                                                                                        |
| ---------- | --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Block 1    | 0-3       | Project scaffold: directory structure, pyproject.toml, Docker Compose up, Postgres + pgvector + Redis running locally. Alembic init. .env.example.                                 | docker compose up is healthy. alembic upgrade head runs without error.                                                                  |
| Block 2    | 3-6       | Data models (SQLAlchemy): Organization, Agent, Policy, Delegation, AuditLog, AgentBudget, TrustScoreEvent. Immutability trigger migration. All models have working \__repr_\_.     | All models importable. Alembic migration runs clean. Trigger confirmed by test INSERT + UPDATE attempt.                                 |
| Block 3    | 6-9       | Auth: bcrypt API key generate/verify, api_key_prefix field, auth middleware as FastAPI Depends(). Rate limit middleware (Redis counter). /health endpoint.                         | /health returns 200. Curl with bad API key returns 401. Correct key returns 200.                                                        |
| Block 4    | 9-13      | POST /agents/register: full implementation with embedding (OpenAI), idempotent upsert, HTTPS webhook validation, JSON Schema validation. GET /agents/registry: paginated list.     | Register an agent with curl. Confirm embedding stored in DB. Re-register same agent_id updates without error.                           |
| Block 5    | 13-17     | POST /capabilities/discover: full pgvector SQL query, composite scoring, hard filters, P99 <200ms target. Test with 3+ agents in DB.                                               | Discover returns ranked results. Trust score, budget, latency filters work. Quarantined agent excluded.                                 |
| Block 6    | 17-22     | Policy engine: YAML parser, DelegationContext, evaluate() loop, all operators, default-deny behavior. Policy CRUD endpoints (POST/GET /policies).                                  | Policy eval unit tests pass (T-001 through T-005). Policy engine works without DB for pure eval.                                        |
| Block 7    | 22-27     | POST /delegate: steps 1-9 (resolve callee, validate, schema check, budget check, depth check, policy eval, create delegation record, block/pause handling). No webhook yet.        | 403 returned on policy block. 402 on budget exceeded. 422 on schema fail. Delegation record created in DB.                              |
| Block 8    | 27-31     | Webhook delivery: HMAC signing, HTTPX sync delivery, delegation token JWT issuance. POST /delegations/{id}/complete: JWT verify, single-use Redis, result schema validate, settle. | Full delegation round-trip works. Callee webhook receives payload, verifies HMAC, posts to /complete. delegation.status == 'completed'. |
| Block 9    | 31-35     | Budget settle (agent_budgets upsert), trust score update, audit log writes at each step. Audit immutability test.                                                                  | After delegation: budget spent_usd updated. trust_score_events record created. Audit log has 3+ entries.                                |
| Block 10   | 35-39     | Stripe integration: BillingService.record_delegation_usage(). nexra-py SDK: NexraClient with register(), discover(), delegate(), hire(). README quickstart.                        | Stripe usage event fires after delegation (verify in Stripe Dashboard test mode). SDK hire() works end-to-end.                          |
| Block 11   | 39-43     | Demo scenario: sales_agent.py + research_agent.py. Two agents coordinate via Nexra. Policy blocks outside business hours. Record 90-second demo video.                             | Demo video recorded. Policy switch from allow to block takes 10 seconds. No hardcoded connections between agents.                       |
| Block 12   | 43-48     | Railway deploy. usenexra.com waitlist landing page. GitHub repo open source. Launch posts: X, LinkedIn, HN Show HN. DM 20 AI engineering leads.                                    | Railway deploy green. Landing page live with demo video embedded. GitHub public.                                                        |

# **§23 - Error Handling & Status Codes**

## **23.1 NexraError Exception**

\# core/errors.py

class NexraError(Exception):

def \__init_\_(self, status_code: int, code: str, message: str, details: dict = None):

self.status_code = status_code

self.code = code

self.message = message

self.details = details or {}

\# FastAPI exception handler

@app.exception_handler(NexraError)

async def nexra_error_handler(request, exc: NexraError):

return JSONResponse(

status_code=exc.status_code,

content={

'error': {

'code': exc.code,

'message': exc.message,

'details': exc.details,

'request_id': request.state.request_id

}

}

)

## **23.2 Complete Error Code Reference**

| **HTTP** | **Code**                      | **Description**                                                            |
| -------- | ----------------------------- | -------------------------------------------------------------------------- |
| 400      | INVALID_SCHEMA                | input_schema or output_schema fails JSON Schema Draft 7 validation         |
| 400      | INVALID_WEBHOOK_URL           | webhook_url does not use HTTPS                                             |
| 400      | INVALID_AGENT_ID              | agent_id format violation (chars, length)                                  |
| 400      | INVALID_REQUEST               | Generic request validation failure (Pydantic)                              |
| 400      | MAX_DEPTH_EXCEEDED            | Delegation chain depth exceeds org limit                                   |
| 401      | UNAUTHORIZED                  | API key missing, invalid, or bcrypt mismatch                               |
| 401      | INVALID_DELEGATION_TOKEN      | JWT signature invalid, expired, or already used                            |
| 403      | AGENT_QUARANTINED             | Caller or callee agent is quarantined                                      |
| 403      | POLICY_BLOCKED                | Policy evaluation returned 'block'. policy_id in details.                  |
| 403      | WEBHOOK_SIGNATURE_REJECTED    | Callee returned 401/403 on webhook (HMAC mismatch)                         |
| 402      | BUDGET_EXCEEDED               | Delegation cost exceeds remaining budget. remaining_budget_usd in details. |
| 404      | AGENT_NOT_FOUND               | callee_agent_id not found or not accessible to caller                      |
| 404      | DELEGATION_NOT_FOUND          | delegation_id not found or not owned by org                                |
| 404      | POLICY_NOT_FOUND              | policy_id not found                                                        |
| 408      | DELEGATION_TIMEOUT            | Callee did not respond within timeout_ms                                   |
| 409      | DELEGATION_ALREADY_COMPLETE   | POST /complete called on already-completed delegation                      |
| 422      | SCHEMA_VALIDATION_FAILED      | Task payload does not conform to callee's input_schema                     |
| 422      | OUTPUT_SCHEMA_FAILED          | Callee result does not conform to registered output_schema                 |
| 429      | RATE_LIMIT_EXCEEDED           | Too many requests. Retry-After header included.                            |
| 500      | INTERNAL_ERROR                | Unexpected server error. Logged to Sentry.                                 |
| 503      | CALLEE_WEBHOOK_FAILED         | Non-2xx from callee webhook after retries                                  |
| 503      | EMBEDDING_SERVICE_UNAVAILABLE | OpenAI embeddings API unavailable after retries                            |

# **§24 - Performance Targets & SLAs**

## **24.1 Latency Targets**

| **Endpoint / Operation**                          | **P50 Target**  | **P99 Target**   | **Timeout**     |
| ------------------------------------------------- | --------------- | ---------------- | --------------- |
| POST /capabilities/discover                       | < 80ms          | < 200ms          | 5s              |
| POST /delegate (policy eval only, before webhook) | < 50ms          | < 150ms          | N/A             |
| POST /agents/register (with embedding)            | < 600ms         | < 2000ms         | 10s             |
| GET /audit/log (paginated)                        | < 100ms         | < 300ms          | 5s              |
| GET /spend/summary                                | < 150ms         | < 500ms          | 5s              |
| Auth middleware (bcrypt verify)                   | < 20ms          | < 80ms           | 1s              |
| Policy engine evaluation (pure Python)            | < 5ms           | < 20ms           | 100ms           |
| Webhook delivery (callee latency excluded)        | < 30ms overhead | < 100ms overhead | Callee SLA + 5s |

## **24.2 Capacity Targets**

| **Concurrent delegations in flight (Growth)** | 100 (configurable on Enterprise)                                       |
| --------------------------------------------- | ---------------------------------------------------------------------- |
| **Delegation throughput (MVP)**               | 50 delegations/second (Railway single instance)                        |
| **Delegation throughput (Production)**        | 500+ delegations/second (ECS auto-scaling)                             |
| **pgvector discovery candidates**             | Up to 10,000 agents evaluated per query under 200ms with IVFFlat index |
| **Audit log retention**                       | 7 days (Starter), 90 days (Growth), configurable (Enterprise)          |
| **Webhook retry budget**                      | 3 attempts, exponential backoff, max 7 seconds total retry window      |
| **Rate limit (Growth)**                       | 1,000 req/min per org. 429 with Retry-After on exceed.                 |
| **API uptime SLA (Growth)**                   | 99.5% (best-effort). 99.9% on Enterprise plan.                         |

## **24.3 IVFFlat Index Tuning**

pgvector IVFFlat index performance depends on the 'lists' parameter. Guidelines:

- lists = sqrt(n_rows) is the rule of thumb. For 1,000 agents: lists=32. For 10,000 agents: lists=100.
- probes parameter controls recall vs speed tradeoff. Default probes=10 gives >95% recall at typical agent counts.
- SET ivfflat.probes = 20 for higher recall in production environments with >5,000 agents.
- Re-index (REINDEX INDEX agents_embedding_idx) when agent count grows >2x from last index build.

# **§25 - Future Architecture - v2 & v3 Considerations**

## **25.1 v2 Features - Technical Implications**

| **v2 Feature**                   | **Technical Change Required**                                                                                                        | **Data Model Impact**                                                      |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------- |
| Cross-org marketplace            | Stripe Connect fully enabled. is_public=true agents visible in discovery. Revenue share auto-transfer.                               | Add stripe_connect_account_id to organizations. Add pending_payouts table. |
| SIEM export (real-time)          | Celery task that streams audit_log events to org-registered SIEM webhook. Structured JSON with consistent schema.                    | Add siem_config JSONB to organizations. Add siem_delivery_log table.       |
| Schema validation on delegation  | jsonschema.validate() already in codebase - enable by default in v2.                                                                 | No schema changes. Config flag: schema_validation_enabled per org.         |
| Policy version control           | Policies table already has version INT. Add parent_policy_id FK for history chain. Update audit entries to reference policy_version. | Add parent_policy_id UUID FK to policies table.                            |
| Compliance report exports        | New analytics service: generate structured CSV/JSON for SOC 2, GDPR, HIPAA. Maps audit_log events to report formats.                 | No schema change. Report generator queries existing tables.                |
| AWS Bedrock adapter (production) | Bedrock adapter fully tested, SigV4 signing production-hardened. AWS credentials encrypted per org.                                  | Add aws_credentials_enc JSONB to organizations.                            |
| Governance dashboard (UI)        | React SPA served separately (Vercel/Cloudflare Pages). Reads from existing /analytics/usage and /audit/log endpoints.                | No backend schema change. Dashboard is read-only.                          |

## **25.2 v3 - Enterprise Architecture Considerations**

- Data residency (EU): Separate PostgreSQL instance in eu-west-1. Router layer routes org queries to correct regional DB based on org.region field.
- On-prem deployment: Helm chart for Kubernetes. External secrets via AWS Secrets Manager / Vault. Stripped Stripe for air-gapped environments.
- SOC 2 Type II: Audit log export to immutable S3 bucket (Object Lock). CloudTrail integration. Automated evidence collection.
- Multi-tenancy hardening: Row-level security (RLS) policies in PostgreSQL as defense-in-depth layer. All queries already org-scoped at application layer.
- Async-first delegation engine: Replace synchronous webhook delivery with full event-driven architecture (Kafka or SQS). Enables at-least-once delivery guarantees.
- Embedding caching: Cache embeddings for repeated discovery queries (Redis, TTL 5 min). Reduces OpenAI API cost by ~60% at scale.

## **25.3 Scaling Inflection Points**

| **Scale Point**      | **Trigger**                            | **Required Change**                                                                                 |
| -------------------- | -------------------------------------- | --------------------------------------------------------------------------------------------------- |
| 10K delegations/day  | Railway CPU > 70% sustained            | Add second Railway instance. Enable Redis connection pooling.                                       |
| 1K registered agents | Discovery query P99 > 150ms            | Increase IVFFlat lists to 100. Add probes=20 session parameter.                                     |
| 100 orgs             | Auth middleware P99 > 50ms             | Add api_key_prefix index. Implement Redis API key cache (TTL 60s) to avoid bcrypt on every request. |
| \$10K MRR            | Railway single-region reliability risk | Migrate to AWS ECS Fargate. RDS Multi-AZ. ElastiCache. ALB. Terraform IaC.                          |
| Enterprise customer  | SOC 2 required                         | Begin SOC 2 Type I process. Pen test via Cobalt. Finalize data retention policies.                  |

**Document Status**

This TDD covers the complete MVP build scope and production architecture for Nexra v1. Every endpoint, data model, service class, algorithm, test case, and deployment step required to ship a working product is specified here. Development starts with §22 (48-Hour Build Plan). Questions on any section should be resolved before writing code for that section.

_Nexra - usenexra.com - Technical Design Document v1.0 - March 2026 - Confidential_