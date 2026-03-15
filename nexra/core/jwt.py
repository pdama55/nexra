from datetime import datetime, timedelta, timezone
from uuid import uuid4

import redis.asyncio as aioredis
from jose import JWTError, jwt

TOKEN_EXPIRY_SECONDS = 300  # 5 minutes


def issue_delegation_token(
    org_secret: str,
    delegation_id: str,
    callee_agent_id: str,
    context_scope: list[str],
) -> str:
    """Issue a scoped, single-use delegation JWT.

    Args:
        org_secret: Decrypted per-org 256-bit secret.
        delegation_id: UUID string of the delegation.
        callee_agent_id: The agent_id of the callee.
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

    Raises:
        ValueError: If token is invalid, expired, or already used.
    """
    try:
        payload = jwt.decode(token, org_secret, algorithms=["HS256"])
    except JWTError as e:
        raise ValueError(f"Invalid delegation token: {e}")

    jti = payload["jti"]

    was_set = await redis_client.set(
        f"jti:{jti}", "1", nx=True, ex=TOKEN_EXPIRY_SECONDS
    )
    if not was_set:
        raise ValueError("Delegation token already used (single-use enforcement)")

    return payload
