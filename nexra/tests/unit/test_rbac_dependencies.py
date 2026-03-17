"""Unit tests for RBAC dependency helpers."""

import pytest

from api.dependencies import RequestActor, require_roles
from core.errors import INSUFFICIENT_ROLE, NexraError


@pytest.mark.asyncio
async def test_require_roles_rejects_insufficient_role() -> None:
    dependency = require_roles("admin")
    with pytest.raises(NexraError) as exc:
        await dependency(actor=RequestActor(email="viewer@example.com", role="viewer"))

    assert exc.value.status_code == 403
    assert exc.value.code == INSUFFICIENT_ROLE


@pytest.mark.asyncio
async def test_require_roles_allows_authorized_role() -> None:
    dependency = require_roles("admin", "engineer")
    actor = await dependency(actor=RequestActor(email="eng@example.com", role="engineer"))
    assert actor.role == "engineer"
