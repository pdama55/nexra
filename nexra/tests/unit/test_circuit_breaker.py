"""Unit tests for CircuitBreakerService behavior."""

import pytest

from services.trust_service import CircuitBreakerService


class _FakeRedis:
    def __init__(self) -> None:
        self._sets: dict[str, list[tuple[float, str]]] = {}

    async def zadd(self, key: str, values: dict[str, float]) -> None:
        items = self._sets.setdefault(key, [])
        for member, score in values.items():
            items.append((score, member))

    async def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> None:
        items = self._sets.get(key, [])
        self._sets[key] = [item for item in items if not (min_score <= item[0] <= max_score)]

    async def expire(self, key: str, ttl: int) -> None:
        return None

    async def zrangebyscore(self, key: str, min_score: float, max_score: float):
        return [member for score, member in self._sets.get(key, []) if min_score <= score <= max_score]


@pytest.mark.asyncio
async def test_not_tripped_with_fewer_than_five_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = _FakeRedis()
    service = CircuitBreakerService(redis)  # type: ignore[arg-type]
    monkeypatch.setattr("services.trust_service._time.time", lambda: 1_000.0)

    for idx in range(4):
        await service.record_outcome("agent-1", "org-1", success=(idx % 2 == 0))

    assert await service.is_tripped("agent-1", "org-1") is False


@pytest.mark.asyncio
async def test_tripped_when_failure_rate_exceeds_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = _FakeRedis()
    service = CircuitBreakerService(redis)  # type: ignore[arg-type]
    monkeypatch.setattr("services.trust_service._time.time", lambda: 2_000.0)

    outcomes = [False, False, False, True, True]
    for success in outcomes:
        await service.record_outcome("agent-2", "org-2", success=success)

    assert await service.is_tripped("agent-2", "org-2") is True


@pytest.mark.asyncio
async def test_old_entries_are_pruned(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = _FakeRedis()
    service = CircuitBreakerService(redis)  # type: ignore[arg-type]

    monkeypatch.setattr("services.trust_service._time.time", lambda: 10_000.0)
    for _ in range(5):
        await service.record_outcome("agent-3", "org-3", success=False)

    # Move clock beyond 10-minute window; old entries should no longer count.
    monkeypatch.setattr("services.trust_service._time.time", lambda: 10_700.0)
    assert await service.is_tripped("agent-3", "org-3") is False
