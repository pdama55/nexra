# Phase 2 — Authentication & Security

> **TDD Sections**: §4 (Authentication & Security Model), §19 (Environment Config — secrets)
>
> **48-Hour Block**: Hours 6–9
>
> **Depends On**: Phase 1 (Scaffold) complete — all models importable, Docker Compose running, migrations applied.

---

## 1. Prerequisites

- [ ] `docker compose up` is healthy (Postgres + Redis)
- [ ] `alembic upgrade head` has run successfully
- [ ] All 7 ORM models import without error
- [ ] `core/config.py` loads `.env` successfully
- [ ] `core/errors.py` NexraError class exists

---

## 2. Objective

Deliver a fully functional authentication and rate-limiting layer:

- API key generation (bcrypt hashed, prefix stored for O(1) lookup)
- API key verification middleware (FastAPI Depends)
- Agent identity verification (X-Agent-ID header ownership check)
- Delegation JWT issuance and single-use verification (Redis)
- HMAC-SHA256 webhook signing and verification
- AES-256-GCM encryption/decryption for per-org JWT secrets
- Redis sliding-window rate limiting
- `/health` endpoint with component status checks
- Structured JSON request logging middleware

---

## 3. Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| bcrypt rounds | 12 | TDD §4.2. Balance between security and latency (~20ms per verify). |
| API key format | `nx_live_` + 32 bytes urlsafe base64 | TDD §4.2. Prefix identifies Nexra keys. |
| Key lookup | api_key_prefix (first 16 chars) indexed | TDD §4.3 note. Avoids full-table bcrypt scan. O(1) lookup. |
| JWT algorithm | HS256 | TDD §4.4. Per-org secret. Symmetric — no public key distribution needed for MVP. |
| JWT single-use | Redis SET NX with TTL | TDD §4.4. jti stored in Redis. TTL matches token expiry (300s). |
| Rate limiting | Redis sliding window | TDD §6.1. 1000 req/min Growth, 100 req/min Starter. |
| Secret encryption | AES-256-GCM | TDD §4.4. Per-org JWT secrets encrypted at rest. |

---

## 4. File-by-File Implementation Guide

### 4.1 `core/crypto.py`

**Path**: `nexra/core/crypto.py`

This file contains ALL cryptographic operations. No other file performs crypto directly.

```python
import secrets
import hmac
import hashlib
import json
import bcrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os


# ─── API Key Generation ───────────────────────────────────────

def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        Tuple of (raw_key, bcrypt_hash, prefix).
        raw_key is returned to the user exactly once.
        bcrypt_hash is stored in the database.
        prefix (first 16 chars) is stored for O(1) lookup.
    """
    raw = "nx_live_" + secrets.token_urlsafe(32)
    hashed = bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    prefix = raw[:16]
    return raw, hashed, prefix


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    """Verify a raw API key against its bcrypt hash.

    Uses bcrypt.checkpw which is constant-time for the hash comparison.
    """
    return bcrypt.checkpw(raw_key.encode("utf-8"), stored_hash.encode("utf-8"))


# ─── HMAC Webhook Signing ─────────────────────────────────────

def sign_webhook_payload(payload: dict, secret: str) -> str:
    """Sign a webhook payload with HMAC-SHA256.

    Returns 'sha256=<hex_digest>' for the X-Nexra-Signature header.
    Payload is serialized with sorted keys and no whitespace for deterministic signing.
    """
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def verify_webhook_signature(payload_bytes: bytes, secret: str, signature: str) -> bool:
    """Verify an incoming webhook signature.

    Uses hmac.compare_digest for constant-time comparison (timing attack safe).
    """
    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ─── AES-256-GCM Encryption ──────────────────────────────────

def generate_org_jwt_secret() -> str:
    """Generate a 256-bit random secret for signing delegation JWTs.

    Returns the raw hex string (64 chars = 32 bytes).
    This value must be encrypted before storage.
    """
    return secrets.token_hex(32)


def encrypt_aes_gcm(plaintext: str, encryption_key_hex: str) -> str:
    """Encrypt a string using AES-256-GCM.

    Args:
        plaintext: The string to encrypt.
        encryption_key_hex: 64-char hex string (32 bytes) from SECRET_KEY_ENCRYPTION_KEY env var.

    Returns:
        Hex-encoded string: nonce (24 chars) + ciphertext (variable length).
    """
    key = bytes.fromhex(encryption_key_hex)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return (nonce + ciphertext).hex()


def decrypt_aes_gcm(encrypted_hex: str, encryption_key_hex: str) -> str:
    """Decrypt an AES-256-GCM encrypted string.

    Args:
        encrypted_hex: Hex string from encrypt_aes_gcm (nonce + ciphertext).
        encryption_key_hex: Same key used for encryption.

    Returns:
        The original plaintext string.

    Raises:
        cryptography.exceptions.InvalidTag: If the key is wrong or data is tampered.
    """
    data = bytes.fromhex(encrypted_hex)
    key = bytes.fromhex(encryption_key_hex)
    aesgcm = AESGCM(key)
    nonce = data[:12]
    ciphertext = data[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")


# ─── Task Hash ────────────────────────────────────────────────

def sha256_json(data: dict) -> str:
    """SHA-256 hash of a JSON-serialized dict.

    Used for tamper detection on delegation task payloads.
    Deterministic: sorted keys, no whitespace.
    """
    body = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(body).hexdigest()
```

**Guardrails**:
- NEVER log raw API keys. NEVER return them after the initial creation response.
- NEVER store the raw JWT secret. Always encrypt with AES-GCM before writing to the `jwt_secret_enc` column.
- The `encryption_key_hex` comes from `get_settings().secret_key_encryption_key`. Do NOT hardcode it.
- `sign_webhook_payload` and `verify_webhook_signature` MUST use the same serialization (sorted keys, no whitespace). Any difference causes signature mismatch.
- **CRITICAL**: When Nexra sends a webhook, it uses `sign_webhook_payload(payload_dict, secret)` which serializes the dict internally. The callee receives the HTTP body as raw bytes. `verify_webhook_signature(body_bytes, secret, sig)` re-computes the HMAC over those raw bytes. This works correctly ONLY if the HTTP body was serialized with `json.dumps(payload, separators=(",",":"), sort_keys=True)`. When using `httpx.AsyncClient.post(url, json=payload)`, httpx serializes the payload itself — which does NOT use sorted keys or compact separators. **Therefore, `WebhookService.deliver_and_await` must serialize the payload manually and send it as `content=` (raw bytes), NOT `json=`**. See Phase 6 for the corrected implementation.

### 4.2 `core/jwt.py`

**Path**: `nexra/core/jwt.py`

Delegation JWT issuance and verification with single-use enforcement via Redis.

```python
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import redis.asyncio as aioredis

TOKEN_EXPIRY_SECONDS = 300  # 5 minutes


def issue_delegation_token(
    org_secret: str,
    delegation_id: str,
    callee_agent_id: str,
    context_scope: list[str],
) -> str:
    """Issue a scoped, single-use delegation JWT.

    Args:
        org_secret: Decrypted per-org 256-bit secret (from AES-GCM decryption).
        delegation_id: UUID string of the delegation.
        callee_agent_id: The agent_id of the callee (for verification on /complete).
        context_scope: List of data grant keys the callee is authorized to read.

    Returns:
        Encoded JWT string.
    """
    jti = str(uuid4())
    now = datetime.now(timezone.utc)
    payload = {
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(seconds=TOKEN_EXPIRY_SECONDS),
        "delegation_id": delegation_id,
        "callee_agent_id": callee_agent_id,
        "context_scope": context_scope,
    }
    return jwt.encode(payload, org_secret, algorithm="HS256")


async def verify_delegation_token(
    token: str,
    org_secret: str,
    redis_client: aioredis.Redis,
) -> dict:
    """Verify a delegation JWT and enforce single-use via Redis.

    Args:
        token: The JWT string from the Authorization header.
        org_secret: Decrypted per-org secret.
        redis_client: Async Redis client for jti tracking.

    Returns:
        Decoded JWT payload dict.

    Raises:
        ValueError: If token is invalid, expired, or already used.
    """
    try:
        payload = jwt.decode(token, org_secret, algorithms=["HS256"])
    except JWTError as e:
        raise ValueError(f"Invalid delegation token: {e}")

    jti = payload["jti"]

    # Single-use enforcement: SET NX (only succeeds if key doesn't exist)
    # TTL matches token expiry so Redis auto-cleans up
    was_set = await redis_client.set(
        f"jti:{jti}", "1", nx=True, ex=TOKEN_EXPIRY_SECONDS
    )
    if not was_set:
        raise ValueError("Delegation token already used (single-use enforcement)")

    return payload
```

**Guardrails**:
- The `org_secret` passed to these functions must ALREADY be decrypted. Do NOT decrypt inside jwt.py — that's the caller's responsibility using `decrypt_aes_gcm`.
- `algorithms=["HS256"]` in `jwt.decode` is a security requirement — prevents algorithm confusion attacks.
- The Redis key `jti:{jti}` uses the same TTL as the token expiry. This means Redis auto-cleans used tokens.

### 4.3 `api/dependencies.py`

**Path**: `nexra/api/dependencies.py`

Central FastAPI dependency injection. All route handlers use these.

```python
from fastapi import Header, HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis

from db.session import get_db
from core.config import get_settings
from core.crypto import verify_api_key
from models.organization import Organization
from models.agent import Agent


# ─── Redis Dependency ─────────────────────────────────────────

_redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Returns a shared async Redis client."""
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=50,
        )
    return _redis_pool


# ─── Rate Limit Check ────────────────────────────────────────

async def check_rate_limit(
    redis_client: aioredis.Redis,
    org_key_prefix: str,
    rpm_limit: int,
) -> None:
    """Sliding window rate limit check.

    Uses Redis INCR + EXPIRE for a 60-second window.
    Raises HTTPException 429 if limit exceeded.
    """
    key = f"rate:{org_key_prefix}"
    current = await redis_client.incr(key)
    if current == 1:
        await redis_client.expire(key, 60)
    if current > rpm_limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Rate limit exceeded: {rpm_limit} requests per minute",
                }
            },
            headers={"Retry-After": "60"},
        )


# ─── Auth Dependency ──────────────────────────────────────────

async def get_authenticated_org(
    request: Request,
    authorization: str = Header(..., description="Bearer nx_live_..."),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> Organization:
    """Authenticate the request and return the Organization.

    Extracts API key from Authorization header, verifies via bcrypt,
    and enforces rate limits.

    Raises:
        HTTPException 401: Missing or invalid API key.
        HTTPException 429: Rate limit exceeded.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"error": {"code": "UNAUTHORIZED", "message": "Missing Bearer token"}})

    raw_key = authorization[7:]
    prefix = raw_key[:16]

    # Rate limit BEFORE bcrypt (bcrypt is CPU-expensive)
    settings = get_settings()

    # Find org by prefix (O(1) indexed lookup)
    result = await db.execute(
        select(Organization).where(Organization.api_key_prefix == prefix)
    )
    org = result.scalar_one_or_none()

    if not org or not verify_api_key(raw_key, org.api_key_hash):
        raise HTTPException(status_code=401, detail={"error": {"code": "UNAUTHORIZED", "message": "Invalid API key"}})

    # Apply rate limit based on plan
    rpm = settings.rate_limit_growth_rpm if org.plan in ("growth", "enterprise") else settings.rate_limit_starter_rpm
    await check_rate_limit(redis_client, prefix, rpm)

    return org


async def get_authenticated_org_and_agent(
    request: Request,
    authorization: str = Header(...),
    x_agent_id: str = Header(..., alias="X-Agent-ID"),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> tuple[Organization, Agent]:
    """Authenticate and return both Organization and Agent.

    Used for agent-initiated requests (discover, delegate).

    Raises:
        HTTPException 401: Invalid API key or agent not found under org.
        HTTPException 403: Agent is quarantined.
    """
    org = await get_authenticated_org(request, authorization, db, redis_client)

    result = await db.execute(
        select(Agent).where(
            Agent.org_id == org.id,
            Agent.agent_id == x_agent_id,
        )
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "UNAUTHORIZED", "message": f"Agent '{x_agent_id}' not found under this organization"}},
        )

    if agent.status == "quarantined":
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "AGENT_QUARANTINED", "message": f"Agent '{x_agent_id}' is quarantined"}},
        )

    return org, agent
```

**Guardrails**:
- Rate limit check MUST happen BEFORE bcrypt verification. bcrypt is ~20ms per call — an attacker could use it for DoS.
- The `api_key_prefix` lookup is O(1) via the indexed column. Do NOT iterate over all orgs and compare hashes.
- `get_authenticated_org_and_agent` requires the `X-Agent-ID` header. Endpoints that don't need agent identity (e.g., /agents/registry list) use `get_authenticated_org` instead.

### 4.4 `api/middleware/auth.py`

**Path**: `nexra/api/middleware/auth.py`

This file is intentionally thin — the actual auth logic lives in `api/dependencies.py` as FastAPI `Depends()`. This middleware file exists for any future global middleware needs but for MVP, auth is dependency-injected per route.

```python
# Auth logic is implemented as FastAPI dependencies in api/dependencies.py
# This file reserved for future global auth middleware if needed.
```

### 4.5 `api/middleware/rate_limit.py`

**Path**: `nexra/api/middleware/rate_limit.py`

```python
# Rate limiting is implemented in api/dependencies.py via check_rate_limit()
# Called inside get_authenticated_org() — runs on every authenticated request.
# This file reserved for future standalone rate limit middleware if needed.
```

### 4.6 `api/middleware/logging.py`

**Path**: `nexra/api/middleware/logging.py`

Structured JSON request logging for every API request.

```python
import time
import logging
import json
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = logging.getLogger("nexra.api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every request with structured JSON fields.

    Fields logged:
    - request_id (from request.state)
    - method
    - path
    - status_code
    - latency_ms
    - org_id (if authenticated — set by auth dependency)

    Sensitive fields NEVER logged:
    - Authorization header value
    - Request body (may contain task payloads with PII)
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        log_data = {
            "request_id": getattr(request.state, "request_id", None),
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
        }

        if response.status_code >= 500:
            logger.error(json.dumps(log_data))
        elif response.status_code >= 400:
            logger.warning(json.dumps(log_data))
        else:
            logger.info(json.dumps(log_data))

        return response
```

**Register in `api/main.py`** — add to `create_app()`:
```python
from api.middleware.logging import RequestLoggingMiddleware
app.add_middleware(RequestLoggingMiddleware)
```

### 4.7 `api/routers/health.py`

**Path**: `nexra/api/routers/health.py`

Health check endpoint. No authentication required. Returns component status.

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as aioredis

from db.session import get_db
from api.dependencies import get_redis

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Health check endpoint.

    Returns 200 with component status if all dependencies are reachable.
    Returns 503 if any critical dependency is down.
    """
    components = {}
    all_healthy = True

    # Check PostgreSQL
    try:
        await db.execute(text("SELECT 1"))
        components["postgres"] = "healthy"
    except Exception as e:
        components["postgres"] = f"unhealthy: {str(e)[:100]}"
        all_healthy = False

    # Check Redis
    try:
        await redis_client.ping()
        components["redis"] = "healthy"
    except Exception as e:
        components["redis"] = f"unhealthy: {str(e)[:100]}"
        all_healthy = False

    status_code = 200 if all_healthy else 503
    return {
        "status": "healthy" if all_healthy else "degraded",
        "components": components,
    }
```

**Fix: Health endpoint must return correct HTTP status code**. The function currently returns a dict but the `status_code` local variable is not used. Fix by returning a `JSONResponse`:

```python
from fastapi.responses import JSONResponse

@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    components = {}
    all_healthy = True

    try:
        await db.execute(text("SELECT 1"))
        components["postgres"] = "healthy"
    except Exception as e:
        components["postgres"] = f"unhealthy: {str(e)[:100]}"
        all_healthy = False

    try:
        await redis_client.ping()
        components["redis"] = "healthy"
    except Exception as e:
        components["redis"] = f"unhealthy: {str(e)[:100]}"
        all_healthy = False

    status_code = 200 if all_healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if all_healthy else "degraded",
            "components": components,
        },
    )
```

**Register in `api/main.py`** — add to `create_app()`:
```python
from api.routers.health import router as health_router
app.include_router(health_router)
```

### 4.8a `api/routers/orgs.py` — Organization Creation

**Path**: `nexra/api/routers/orgs.py`

**CRITICAL**: No other phase creates organizations. Without this endpoint, there is no way to create an org, generate an API key, or use any authenticated endpoint. This is the bootstrap mechanism.

```python
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from db.session import get_db
from core.crypto import generate_api_key, generate_org_jwt_secret, encrypt_aes_gcm
from core.config import get_settings
from models.organization import Organization
from api.schemas.common import DataResponse, MetaResponse

router = APIRouter(prefix="/orgs", tags=["organizations"])


class OrgCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    plan: str = Field("starter", description="starter | growth | enterprise")


class OrgCreateResponse(BaseModel):
    org_id: str
    name: str
    plan: str
    api_key: str  # Returned ONCE — never stored or retrievable again


@router.post("/register", status_code=201)
async def create_organization(
    request: Request,
    body: OrgCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new organization and return its API key.

    The API key is returned exactly once in this response.
    It is bcrypt-hashed before storage and cannot be retrieved again.
    """
    settings = get_settings()

    raw_key, hashed_key, prefix = generate_api_key()
    jwt_secret = generate_org_jwt_secret()
    jwt_secret_enc = encrypt_aes_gcm(jwt_secret, settings.secret_key_encryption_key)

    org = Organization(
        name=body.name,
        plan=body.plan,
        api_key_hash=hashed_key,
        api_key_prefix=prefix,
        jwt_secret_enc=jwt_secret_enc,
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)

    return DataResponse(
        data=OrgCreateResponse(
            org_id=str(org.id),
            name=org.name,
            plan=org.plan,
            api_key=raw_key,
        ),
        meta=MetaResponse(
            request_id=getattr(request.state, "request_id", None),
        ),
    )
```

**Register in `api/main.py`**:
```python
from api.routers.orgs import router as orgs_router
app.include_router(orgs_router, prefix="/v1")
```

**Note**: This endpoint is intentionally unauthenticated (no API key required) because it IS the bootstrap mechanism. In production, add a separate admin secret or disable after initial setup.

### 4.8b Redis Lifecycle — Shutdown Handler

Add to `api/dependencies.py`:

```python
async def close_redis() -> None:
    """Close the Redis connection pool on app shutdown."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None
```

Wire into `api/main.py` `create_app()`:
```python
from api.dependencies import close_redis

@app.on_event("shutdown")
async def shutdown():
    await close_redis()
```

### 4.8 Update `api/main.py`

After Phase 2, the `create_app()` function should include:

1. Request ID middleware (already from Phase 1)
2. RequestLoggingMiddleware
3. NexraError exception handler (already from Phase 1)
4. Health router mounted
5. Sentry init (already from Phase 1)

```python
def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Nexra API",
        description="The control plane for AI agent networks",
        version="0.1.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )

    # Middleware
    from api.middleware.logging import RequestLoggingMiddleware
    app.add_middleware(RequestLoggingMiddleware)

    @app.middleware("http")
    async def add_request_id(request, call_next):
        import uuid as _uuid
        request_id = str(_uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # Exception handlers
    @app.exception_handler(NexraError)
    async def nexra_error_handler(request, exc: NexraError):
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

    # Routers
    from api.routers.health import router as health_router
    app.include_router(health_router)

    # Sentry
    if settings.sentry_dsn:
        import sentry_sdk
        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1, environment=settings.environment)

    return app
```

---

## 5. Database Changes

No new migrations in this phase. All tables were created in Phase 1.

The `api_key_prefix` column on `organizations` was already included in the Phase 1 migration.

---

## 6. Environment Variables

No new environment variables. All were defined in Phase 1's `.env.example`.

Key variables used in this phase:
- `SECRET_KEY_ENCRYPTION_KEY` — used by `encrypt_aes_gcm` / `decrypt_aes_gcm`
- `REDIS_URL` — used by rate limiter and JWT single-use enforcement
- `RATE_LIMIT_GROWTH_RPM` / `RATE_LIMIT_STARTER_RPM` — rate limit thresholds

---

## 7. Guardrails

1. **DO NOT** log raw API keys. Not in request logs, not in error messages, not in Sentry.
2. **DO NOT** return the API key after the initial org creation response. It is shown once and never again.
3. **DO NOT** store the raw per-org JWT secret. Always encrypt with `encrypt_aes_gcm` before writing to `jwt_secret_enc`.
4. **DO NOT** use `bcrypt.hashpw` for rate limit key derivation — use the raw prefix string. bcrypt is too slow for rate limiting.
5. **DO NOT** skip the `nx=True` flag on Redis SET for jti enforcement. Without it, a replayed token would succeed.
6. **DO NOT** use `algorithms=["HS256", "RS256"]` in jwt.decode — only `["HS256"]`. Multiple algorithms enable algorithm confusion attacks.
7. **DO NOT** compare HMAC signatures with `==`. Always use `hmac.compare_digest` for constant-time comparison.
8. **DO NOT** log the Authorization header value in the request logging middleware.

---

## 8. Verification Checklist

```bash
# 1. Verify crypto module
python -c "
from core.crypto import generate_api_key, verify_api_key
raw, hashed, prefix = generate_api_key()
assert raw.startswith('nx_live_')
assert len(prefix) == 16
assert verify_api_key(raw, hashed) == True
assert verify_api_key('wrong_key', hashed) == False
print('API key generation/verification: PASS')
"

# 2. Verify AES-GCM encryption
python -c "
from core.crypto import generate_org_jwt_secret, encrypt_aes_gcm, decrypt_aes_gcm
import secrets
enc_key = secrets.token_hex(32)
secret = generate_org_jwt_secret()
encrypted = encrypt_aes_gcm(secret, enc_key)
decrypted = decrypt_aes_gcm(encrypted, enc_key)
assert decrypted == secret
print('AES-GCM encryption/decryption: PASS')
"

# 3. Verify HMAC signing
python -c "
from core.crypto import sign_webhook_payload, verify_webhook_signature
import json
payload = {'task': 'test', 'id': '123'}
secret = 'test_secret_key'
sig = sign_webhook_payload(payload, secret)
body = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode()
assert verify_webhook_signature(body, secret, sig) == True
assert verify_webhook_signature(body, 'wrong_secret', sig) == False
print('HMAC signing/verification: PASS')
"

# 4. Verify JWT issuance and verification
python -c "
import asyncio
from core.jwt import issue_delegation_token, verify_delegation_token
import redis.asyncio as aioredis

async def test():
    r = aioredis.from_url('redis://localhost:6379/1', decode_responses=True)
    secret = 'a' * 64
    token = issue_delegation_token(secret, 'del-123', 'agent-1', ['scope1'])
    payload = await verify_delegation_token(token, secret, r)
    assert payload['delegation_id'] == 'del-123'
    assert payload['callee_agent_id'] == 'agent-1'
    # Second use should fail
    try:
        await verify_delegation_token(token, secret, r)
        assert False, 'Should have raised'
    except ValueError as e:
        assert 'already used' in str(e)
    print('JWT single-use enforcement: PASS')
    await r.flushdb()
    await r.aclose()

asyncio.run(test())
"

# 5. Verify /health endpoint
curl -s http://localhost:8000/health | python -m json.tool
# Expected: { "status": "healthy", "components": { "postgres": "healthy", "redis": "healthy" } }

# 6. Verify 401 on missing auth
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health
# Expected: 200 (health is unauthenticated)

# 7. Verify request logging (check terminal output)
# Should see structured JSON log lines for each request
```

---

## 9. Test Cases

| Test ID | Category | Description | Setup | Assertion |
|---------|----------|-------------|-------|-----------|
| T-AUTH-001 | Crypto | generate_api_key returns (raw, hash, prefix) | None | raw starts with "nx_live_", len(prefix)==16, verify_api_key(raw, hash)==True |
| T-AUTH-002 | Crypto | verify_api_key rejects wrong key | Generate key | verify_api_key("wrong", hash)==False |
| T-AUTH-003 | Crypto | AES-GCM round-trip | Generate key + encrypt | decrypt(encrypt(plaintext)) == plaintext |
| T-AUTH-004 | Crypto | AES-GCM wrong key raises InvalidTag | Encrypt with key A | decrypt with key B raises InvalidTag |
| T-AUTH-005 | Crypto | sign_webhook_payload deterministic | Same payload + secret | Two calls produce identical signature |
| T-AUTH-006 | Crypto | verify_webhook_signature rejects wrong secret | Sign with secret A | verify with secret B returns False |
| T-AUTH-007 | Crypto | sha256_json deterministic | Same dict | Two calls produce identical hash |
| T-AUTH-008 | JWT | issue_delegation_token contains all claims | Issue token | Decode and verify jti, delegation_id, callee_agent_id, context_scope, exp |
| T-AUTH-009 | JWT | verify_delegation_token succeeds on first use | Issue + verify | Returns payload with correct fields |
| T-AUTH-010 | JWT | verify_delegation_token fails on second use | Issue + verify twice | Second call raises ValueError with "already used" |
| T-AUTH-011 | JWT | verify_delegation_token fails on expired token | Issue with past exp | Raises ValueError with "expired" |
| T-AUTH-012 | JWT | verify_delegation_token fails on wrong secret | Issue with secret A | Verify with secret B raises ValueError |
| T-AUTH-013 | Auth Dep | Valid API key returns org | Create org in DB with known key | get_authenticated_org returns matching org |
| T-AUTH-014 | Auth Dep | Invalid API key returns 401 | No org with this key | HTTPException 401 raised |
| T-AUTH-015 | Auth Dep | Missing Bearer prefix returns 401 | Send "Basic xxx" | HTTPException 401 raised |
| T-AUTH-016 | Auth Dep | Valid key + valid X-Agent-ID returns (org, agent) | Create org + agent | get_authenticated_org_and_agent returns both |
| T-AUTH-017 | Auth Dep | Valid key + wrong X-Agent-ID returns 401 | Create org, no matching agent | HTTPException 401 raised |
| T-AUTH-018 | Auth Dep | Quarantined agent returns 403 | Create org + quarantined agent | HTTPException 403 with AGENT_QUARANTINED |
| T-AUTH-019 | Rate Limit | Under limit succeeds | 5 requests | All succeed |
| T-AUTH-020 | Rate Limit | Over limit returns 429 | Set limit to 2, send 3 requests | Third request gets 429 with Retry-After header |
| T-AUTH-021 | Health | /health returns 200 when all healthy | DB + Redis running | status=="healthy", both components "healthy" |
| T-AUTH-022 | Health | /health returns 503 when DB down | Stop Postgres | status=="degraded", postgres=="unhealthy" |
| T-AUTH-023 | Logging | Request logging middleware logs structured JSON | Send request | Log output contains method, path, status_code, latency_ms |

**Mock setup for unit tests**:
- Mock `AsyncSession` for DB queries (return pre-built Organization/Agent objects)
- Mock `aioredis.Redis` for rate limit and jti checks (use `fakeredis` or manual mock)
- Do NOT mock bcrypt — it's fast enough for unit tests and testing the actual hash is important
