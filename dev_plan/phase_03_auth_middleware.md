# Phase 03 — Auth Middleware & Rate Limiting

**Phase:** 03 / 12 | **TDD Sections:** §4.1-4.3, §6.1 | **48h Block:** Block 3 (6–9h)

> ⚠️ **Prerequisite:** Phase 02 acceptance criteria all GREEN before starting.

---

## Objective

Implement API key authentication (bcrypt verify with prefix-indexed lookup), Redis sliding-window rate limiting, structured JSON request logging, and the `/health` endpoint with real component status checks. No endpoints beyond `/health` yet — just the middleware stack.

---

## Claude Code Prompt

```
You are implementing the auth and middleware layer for Nexra (FastAPI, Python 3.12, Redis, bcrypt).

TASK: Implement auth middleware, rate limiting, logging, and health check per TDD §4.1-4.3.

Requirements:

1. **core/crypto.py** — API key generation and verification:
   ```python
   import secrets, bcrypt
   
   def generate_api_key() -> tuple[str, str, str]:
       """Returns (raw_key, hashed_key, prefix_16).
       raw_key format: 'nx_live_' + 32 random hex chars
       prefix_16: first 16 chars of raw_key (used for O(1) DB lookup)
       hashed_key: bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt(rounds=12)).decode()
       """
   
   def verify_api_key(raw_key: str, stored_hash: str) -> bool:
       """bcrypt.checkpw — constant time. Never use == for key comparison."""
   ```

2. **core/jwt.py** — Delegation JWT (TDD §4.4):
   - issue_delegation_token(org_secret, delegation_id, callee_agent_id, context_scope) → str
   - verify_delegation_token(token, org_secret, redis_client) → dict
   - Uses python-jose. jti single-use enforcement via Redis SET NX with TOKEN_EXPIRY_SECONDS=300 TTL.
   
3. **core/crypto.py (continued)** — HMAC webhook signing (TDD §4.5):
   - sign_webhook_payload(payload: dict, secret: str) → str  # returns 'sha256=<hex>'
   - verify_webhook_signature(payload_bytes: bytes, secret: str, signature: str) → bool  # constant-time

4. **api/dependencies.py** — FastAPI Depends():
   ```python
   async def get_db() -> AsyncGenerator[AsyncSession, None]: ...
   async def get_redis() -> aioredis.Redis: ...
   async def get_org_and_agent(
       authorization: str = Header(...),
       x_agent_id: str | None = Header(None, alias='X-Agent-ID'),
       db: AsyncSession = Depends(get_db),
       redis = Depends(get_redis)
   ) -> tuple[Organization, Agent | None]:
       # EXACTLY as in TDD §4.3:
       # 1. Check rate limit FIRST (before bcrypt — CPU protection)
       # 2. Extract raw_key from 'Bearer nx_live_...'
       # 3. Look up org by api_key_prefix (first 16 chars) — O(1) lookup
       # 4. bcrypt verify raw_key against org.api_key_hash
       # 5. If X-Agent-ID provided: fetch agent, verify org ownership, check not quarantined
       # Return (org, agent) or (org, None)
   ```

5. **api/middleware/rate_limit.py** — Redis sliding window:
   ```python
   async def check_rate_limit(redis, key_prefix: str, plan: str = 'starter') -> None:
       # key: f"rl:{key_prefix}:{current_minute_epoch}"
       # Starter: 100 req/min, Growth: 1000 req/min (from config)
       # INCR + EXPIRE 60s
       # If count > limit: raise HTTPException(429, headers={"Retry-After": "60"})
   ```

6. **api/middleware/logging.py** — Structured JSON request logging:
   - Log: method, path, status_code, latency_ms, request_id (UUID generated per request)
   - Attach request_id to request.state for use in error responses
   - Use Python's structlog or stdlib logging with JSON formatter

7. **core/errors.py** — NexraError exception and handler (TDD §23.1):
   ```python
   class NexraError(Exception):
       def __init__(self, status_code: int, code: str, message: str, details: dict = None): ...
   
   # Register in main.py:
   @app.exception_handler(NexraError)
   async def nexra_error_handler(request, exc): ...
   # Returns: {"error": {"code": ..., "message": ..., "details": ..., "request_id": ...}}
   ```

8. **api/routers/health.py** — real health check:
   ```python
   @router.get("/health")
   async def health(db=Depends(get_db), redis=Depends(get_redis)):
       # Check DB: await db.execute(text("SELECT 1"))
       # Check Redis: await redis.ping()
       # Return 200: {"status": "ok", "components": {"db": "ok", "redis": "ok"}}
       # If any component fails: return 503 with the failing component marked "error"
   ```

9. **api/main.py** — update app factory:
   - Register NexraError handler
   - Add logging middleware 
   - Mount health router

AGENTS.md protocol: compile check after each file. Test auth with curl before moving on.
```

---

## Guardrails

- ✅ **Rate limit check MUST happen BEFORE bcrypt** — bcrypt is CPU-expensive; rate limiting protects against DoS
- ✅ **O(1) key lookup via `api_key_prefix`** — look up org by first 16 chars, then bcrypt verify. Never full-table scan.
- ✅ **`hmac.compare_digest()`** for all signature comparisons — constant-time, prevents timing attacks
- ✅ **JTI single-use via Redis `SET NX`** — mark jti used atomically on first use
- ✅ **`request_id`** is a UUID generated per request, attached to `request.state`, and returned in all error responses
- ❌ **Never use `==` for secret/key comparison** — always `hmac.compare_digest()` or `bcrypt.checkpw()`
- ❌ **Do NOT store the raw API key anywhere** — only `api_key_hash` (bcrypt) and `api_key_prefix` (16 chars) in DB
- ✅ **429 response must include `Retry-After: 60` header**
- ✅ **Quarantined agents** raise 403 `AGENT_QUARANTINED` even with a valid API key

---

## Acceptance Criteria

```bash
# 1. Health endpoint responds with component status
curl http://localhost:8000/health
# → {"status": "ok", "components": {"db": "ok", "redis": "ok"}}

# 2. Missing auth returns 401
curl http://localhost:8000/agents/registry
# → {"error": {"code": "UNAUTHORIZED", "message": "Missing Bearer token", ...}}

# 3. Wrong API key returns 401
curl -H "Authorization: Bearer nx_live_badkey12345678" http://localhost:8000/agents/registry
# → 401 UNAUTHORIZED

# 4. Rate limit triggers 429 after exceeding limit
# (use ab or hey to fire 110 requests in 1 minute with starter plan)
hey -n 110 -c 10 -H "Authorization: Bearer nx_live_..." http://localhost:8000/health
# → Some requests return 429 with Retry-After header

# 5. HMAC verify
python -c "
from core.crypto import sign_webhook_payload, verify_webhook_signature
import json
payload = {'delegation_id': 'test-123', 'task': {'type': 'research'}}
sig = sign_webhook_payload(payload, 'mysecret12345678901234567890123456789012')
body = json.dumps(payload, separators=(',',':'), sort_keys=True).encode()
assert verify_webhook_signature(body, 'mysecret12345678901234567890123456789012', sig)
print('HMAC OK')
"
```

---

## Test Cases

```bash
# Unit: API key generation and verification
poetry run pytest tests/unit/test_crypto.py -v
# - generate_api_key() returns tuple of 3 strings
# - verify_api_key(raw, hash) returns True for correct key
# - verify_api_key(wrong, hash) returns False

# Unit: JWT issue and single-use verify
poetry run pytest tests/unit/test_jwt.py -v
# - T-011: Second use of same JWT raises ValueError
# - T-012: Expired token raises JWTError

# Unit: HMAC signing
poetry run pytest tests/unit/test_hmac.py -v
# - sign_webhook_payload returns 'sha256=<hex>'
# - verify_webhook_signature returns True for correct secret
# - Returns False for wrong secret (not exception)

# Integration: Auth middleware (T-008, T-009, T-010)
poetry run pytest tests/integration/test_auth.py -v
# - T-008: Valid key + valid X-Agent-ID → 200
# - T-009: Valid key + wrong org agent_id → 401
# - T-010: Quarantined agent → 403
```

**Write these test files as part of this phase:**
- `tests/unit/test_crypto.py` — bcrypt key gen/verify, HMAC sign/verify
- `tests/unit/test_jwt.py` — delegation JWT issue/verify/single-use (T-011, T-012)
- `tests/unit/test_hmac.py` — HMAC webhook signing
- `tests/integration/test_auth.py` — auth middleware with real Postgres (T-008, T-009, T-010)
