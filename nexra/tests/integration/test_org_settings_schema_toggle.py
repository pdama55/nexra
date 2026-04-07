"""Integration tests for org schema validation settings surface."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import RequestActor
from api.routers.orgs import (
    OrgSettingsUpdateRequest,
    get_org_settings,
    update_org_settings,
)
from core.crypto import encrypt_aes_gcm, generate_api_key, generate_org_jwt_secret
from models.organization import Organization

TEST_ENC_KEY = "a" * 64


def _req() -> object:
    return type("Req", (), {"state": type("State", (), {"request_id": "req-org-settings"})()})()


async def _create_org(db_session: AsyncSession, name: str = "Org Settings Toggle Org") -> Organization:
    _, hashed, prefix = generate_api_key()
    org = Organization(
        id=uuid.uuid4(),
        name=name,
        api_key_hash=hashed,
        api_key_prefix=prefix,
        plan="growth",
        jwt_secret_enc=encrypt_aes_gcm(generate_org_jwt_secret(), TEST_ENC_KEY),
        delegation_count=0,
    )
    db_session.add(org)
    await db_session.flush()
    return org


@pytest.mark.asyncio
async def test_org_settings_exposes_and_updates_schema_validation_toggle(
    db_session: AsyncSession,
) -> None:
    org = await _create_org(db_session)
    actor = RequestActor(email="admin@nexra.local", role="admin")

    before = await get_org_settings(_req(), org=org)
    assert before["data"]["schema_validation_enabled"] is True

    updated = await update_org_settings(
        _req(),
        OrgSettingsUpdateRequest(schema_validation_enabled=False),
        org=org,
        _actor=actor,
        db=db_session,
    )
    assert updated["data"]["schema_validation_enabled"] is False

    await db_session.refresh(org)
    assert org.schema_validation_enabled is False
