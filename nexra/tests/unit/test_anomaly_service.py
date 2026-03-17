"""Unit tests for AnomalyService spend anomaly detection."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.anomaly_service import AnomalyService


def _agents_result(rows):
    result = MagicMock()
    result.all.return_value = rows
    return result


def _sum_rows(values):
    result = MagicMock()
    result.all.return_value = [(v,) for v in values]
    return result


def _scalar(value):
    result = MagicMock()
    result.scalar.return_value = value
    return result


@pytest.mark.asyncio
async def test_detects_anomaly_and_emits_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _agents_result([("agent-1", "org-1")]),
            _sum_rows([float(i) for i in range(1, 31)]),
            _scalar(100.0),
        ]
    )

    append_called = AsyncMock()

    class FakeAuditService:
        def __init__(self, _db: object) -> None:
            pass

        append = append_called

    monkeypatch.setattr("services.anomaly_service.AuditService", FakeAuditService)

    service = AnomalyService(db)
    anomalies = await service.detect_spend_anomalies()

    assert len(anomalies) == 1
    assert anomalies[0]["agent_id"] == "agent-1"
    append_called.assert_awaited_once()


@pytest.mark.asyncio
async def test_skips_agents_with_insufficient_baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _agents_result([("agent-2", "org-2")]),
            _sum_rows([1.0] * 10),
        ]
    )

    append_called = AsyncMock()

    class FakeAuditService:
        def __init__(self, _db: object) -> None:
            pass

        append = append_called

    monkeypatch.setattr("services.anomaly_service.AuditService", FakeAuditService)

    service = AnomalyService(db)
    anomalies = await service.detect_spend_anomalies()

    assert anomalies == []
    append_called.assert_not_awaited()
