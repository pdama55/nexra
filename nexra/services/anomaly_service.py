import logging
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from models.agent import Agent
from models.delegation import Delegation
from services.audit_service import AuditService

logger = logging.getLogger("nexra.services.anomaly")


class AnomalyService:
    """Statistical anomaly detection for agent spend.

    Detects agents whose hourly spend deviates by more than 3-sigma
    from their historical mean. Runs as a Celery beat job (hourly).
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def detect_spend_anomalies(self) -> list[dict]:
        settings = get_settings()
        sigma_threshold = settings.anomaly_sigma_threshold
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)
        seven_days_ago = now - timedelta(days=7)

        agents_result = await self.db.execute(
            select(Agent.agent_id, Agent.org_id)
            .where(Agent.status != "quarantined")
            .distinct()
        )
        agents = agents_result.all()

        anomalies: list[dict] = []
        audit_service = AuditService(self.db)

        for agent_id, org_id in agents:
            hist_result = await self.db.execute(
                select(func.sum(Delegation.actual_cost_usd))
                .where(
                    Delegation.callee_agent_id == agent_id,
                    Delegation.callee_org_id == org_id,
                    Delegation.status == "completed",
                    Delegation.created_at >= seven_days_ago,
                    Delegation.created_at < one_hour_ago,
                )
                .group_by(func.date_trunc("hour", Delegation.created_at))
            )
            hourly_spends = [float(row[0] or 0) for row in hist_result.all()]

            if len(hourly_spends) < 24:
                continue

            mean = sum(hourly_spends) / len(hourly_spends)
            variance = sum((x - mean) ** 2 for x in hourly_spends) / len(hourly_spends)
            stddev = math.sqrt(variance) if variance > 0 else 0

            current_result = await self.db.execute(
                select(func.sum(Delegation.actual_cost_usd)).where(
                    Delegation.callee_agent_id == agent_id,
                    Delegation.callee_org_id == org_id,
                    Delegation.status == "completed",
                    Delegation.created_at >= one_hour_ago,
                )
            )
            current_spend = float(current_result.scalar() or 0)

            threshold = mean + (sigma_threshold * stddev)
            if stddev > 0 and current_spend > threshold:
                anomaly = {
                    "agent_id": agent_id,
                    "org_id": str(org_id),
                    "current_hour_spend": current_spend,
                    "mean_hourly_spend": round(mean, 4),
                    "stddev": round(stddev, 4),
                    "threshold": round(threshold, 4),
                    "sigma_deviation": round((current_spend - mean) / stddev, 2),
                }
                anomalies.append(anomaly)
                logger.warning(f"Spend anomaly detected: {anomaly}")

                await audit_service.append(
                    org_id=str(org_id),
                    event_type="anomaly_detected",
                    actor_agent_id=None,
                    target_agent_id=agent_id,
                    details=anomaly,
                )

        return anomalies
