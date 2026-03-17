"""Unit tests for delegation service error handling."""

from unittest.mock import AsyncMock

import pytest

from core.config import get_settings
from core.crypto import encrypt_aes_gcm, generate_org_jwt_secret
from core.errors import INVALID_DELEGATION_TOKEN, NexraError
from models.organization import Organization
from services.delegation_service import DelegationService


@pytest.mark.asyncio
async def test_complete_maps_invalid_token_to_nexra_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "services.delegation_service.verify_delegation_token",
        AsyncMock(side_effect=ValueError("Invalid delegation token")),
    )

    service = DelegationService(
        db=AsyncMock(),
        redis_client=AsyncMock(),
        policy_engine=AsyncMock(),
        webhook_service=AsyncMock(),
        budget_service=AsyncMock(),
        audit_service=AsyncMock(),
        trust_service=AsyncMock(),
        billing_service=AsyncMock(),
        hitl_service=AsyncMock(),
        circuit_breaker=AsyncMock(),
    )

    settings = get_settings()
    org = Organization(
        id="00000000-0000-0000-0000-000000000001",
        name="Org",
        api_key_hash="hash",
        api_key_prefix="nx_live_test1234",
        plan="growth",
        jwt_secret_enc=encrypt_aes_gcm(
            generate_org_jwt_secret(),
            settings.secret_key_encryption_key,
        ),
        delegation_count=0,
    )

    with pytest.raises(NexraError) as exc:
        await service.complete("deleg-1", "bad-token", {"ok": True}, None, org)

    assert exc.value.status_code == 401
    assert exc.value.code == INVALID_DELEGATION_TOKEN
