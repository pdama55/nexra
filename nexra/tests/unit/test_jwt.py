"""Unit tests for delegation JWT issue/verification."""

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from core.jwt import issue_delegation_token, verify_delegation_token


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None):
        if nx and key in self._store:
            return False
        self._store[key] = value
        return True


@pytest.mark.asyncio
async def test_verify_enforces_single_use() -> None:
    secret = "s" * 64
    redis = _FakeRedis()
    token = issue_delegation_token(
        org_secret=secret,
        delegation_id="deleg-1",
        callee_agent_id="callee-1",
        context_scope=["deal_metadata"],
    )

    payload = await verify_delegation_token(token, secret, redis)
    assert payload["delegation_id"] == "deleg-1"

    with pytest.raises(ValueError, match="already used"):
        await verify_delegation_token(token, secret, redis)


@pytest.mark.asyncio
async def test_verify_rejects_expired_token() -> None:
    secret = "s" * 64
    redis = _FakeRedis()
    expired_payload = {
        "jti": "expired-1",
        "iat": datetime.now(timezone.utc) - timedelta(minutes=10),
        "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
        "delegation_id": "deleg-expired",
        "callee_agent_id": "callee-1",
        "context_scope": ["deal_metadata"],
    }
    token = jwt.encode(expired_payload, secret, algorithm="HS256")

    with pytest.raises(ValueError, match="Invalid delegation token"):
        await verify_delegation_token(token, secret, redis)
