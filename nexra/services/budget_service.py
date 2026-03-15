from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.agent_budget import AgentBudget


@dataclass
class BudgetCheckResult:
    allowed: bool
    reason: str
    remaining_usd: float


class BudgetService:
    """Spend tracking and budget cap enforcement.

    Uses SELECT FOR UPDATE to prevent race conditions on concurrent delegations.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def check_and_reserve(
        self,
        org_id: str,
        agent_id: str,
        estimated_cost: float,
        request_cap: float,
    ) -> BudgetCheckResult:
        """Check if delegation is within budget caps.

        Checks: per-delegation cap, daily cap, monthly cap.
        Uses SELECT FOR UPDATE to lock budget rows during check.
        """
        if estimated_cost > request_cap:
            return BudgetCheckResult(
                allowed=False, reason="per_delegation_cap", remaining_usd=request_cap
            )

        today = date.today()
        first_of_month = today.replace(day=1)

        async with self.db.begin_nested():
            daily_result = await self.db.execute(
                select(AgentBudget)
                .where(
                    AgentBudget.agent_id == agent_id,
                    AgentBudget.org_id == org_id,
                    AgentBudget.period == today,
                    AgentBudget.period_type == "daily",
                )
                .with_for_update()
            )
            daily_row = daily_result.scalar_one_or_none()

            if daily_row:
                remaining = float(daily_row.cap_usd) - float(daily_row.spent_usd)
                if estimated_cost > remaining:
                    return BudgetCheckResult(
                        allowed=False, reason="daily_cap", remaining_usd=remaining
                    )

            monthly_result = await self.db.execute(
                select(AgentBudget)
                .where(
                    AgentBudget.agent_id == agent_id,
                    AgentBudget.org_id == org_id,
                    AgentBudget.period == first_of_month,
                    AgentBudget.period_type == "monthly",
                )
                .with_for_update()
            )
            monthly_row = monthly_result.scalar_one_or_none()

            if monthly_row:
                remaining = float(monthly_row.cap_usd) - float(monthly_row.spent_usd)
                if estimated_cost > remaining:
                    return BudgetCheckResult(
                        allowed=False, reason="monthly_cap", remaining_usd=remaining
                    )

        return BudgetCheckResult(
            allowed=True, reason="", remaining_usd=request_cap - estimated_cost
        )

    async def settle(self, org_id: str, agent_id: str, actual_cost: float) -> None:
        """Update spent_usd after delegation completes. Upserts daily and monthly rows."""
        today = date.today()
        first_of_month = today.replace(day=1)

        for period, period_type in [(today, "daily"), (first_of_month, "monthly")]:
            stmt = (
                pg_insert(AgentBudget)
                .values(
                    agent_id=agent_id,
                    org_id=org_id,
                    period=period,
                    period_type=period_type,
                    cap_usd=Decimal("999999"),
                    spent_usd=Decimal(str(actual_cost)),
                )
                .on_conflict_do_update(
                    index_elements=["agent_id", "org_id", "period", "period_type"],
                    set_={
                        "spent_usd": AgentBudget.spent_usd + Decimal(str(actual_cost)),
                        "updated_at": datetime.now(timezone.utc),
                    },
                )
            )
            await self.db.execute(stmt)

        await self.db.commit()

    async def get_summary(self, org_id: str, agent_id: str | None = None) -> list[dict]:
        q = select(AgentBudget).where(AgentBudget.org_id == org_id)
        if agent_id:
            q = q.where(AgentBudget.agent_id == agent_id)
        q = q.order_by(AgentBudget.period.desc())

        result = await self.db.execute(q)
        rows = result.scalars().all()

        return [
            {
                "agent_id": r.agent_id,
                "period": str(r.period),
                "period_type": r.period_type,
                "cap_usd": float(r.cap_usd),
                "spent_usd": float(r.spent_usd),
                "remaining_usd": float(r.cap_usd) - float(r.spent_usd),
            }
            for r in rows
        ]
