"""Performance sanity test for discovery query orchestration."""

import time
from types import SimpleNamespace

import pytest

from api.schemas.capabilities import DiscoverRequest
from services.discovery_service import DiscoveryService


class _FakeOpenAI:
    class _Embeddings:
        async def create(self, input: str, model: str):
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.01] * 1536)])

    def __init__(self) -> None:
        self.embeddings = self._Embeddings()


class _RowsResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _ScalarResult:
    def __init__(self, value: int):
        self._value = value

    def scalar(self):
        return self._value


class _FakeDB:
    async def execute(self, stmt, params=None):
        sql = str(stmt)
        if "SELECT COUNT(*) FROM agents" in sql:
            return _ScalarResult(3)
        if "ORDER BY composite_score DESC" in sql:
            row = SimpleNamespace(
                agent_id="a1",
                name="Agent One",
                capability_type="analysis",
                trust_score=0.91,
                status="active",
                pricing={"per_call_usd": 0.1},
                sla={"p99_latency_ms": 1000},
                is_public=False,
                org_id="org-1",
                semantic_score=0.95,
                composite_score=0.93,
                filtered_count=1,
            )
            return _RowsResult([row])
        return _RowsResult([])


@pytest.mark.asyncio
async def test_discovery_p99_under_200ms() -> None:
    service = DiscoveryService(_FakeDB(), _FakeOpenAI())

    samples_ms = []
    for _ in range(50):
        start = time.perf_counter()
        matches, total, filtered = await service.discover(
            caller_org_id="org-1",
            request=DiscoverRequest(query="analysis", limit=5),
        )
        samples_ms.append((time.perf_counter() - start) * 1000)
        assert matches
        assert total >= filtered

    p99 = sorted(samples_ms)[int(0.99 * len(samples_ms)) - 1]
    assert p99 < 200.0
