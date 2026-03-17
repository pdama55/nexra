from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.agent_budget import AgentBudget
from models.budget_reservation import BudgetReservation


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
        delegation_id: str | None = None,
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
            outstanding = await self._outstanding_reserved_usd(org_id, agent_id)

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
                remaining = (
                    float(daily_row.cap_usd)
                    - float(daily_row.spent_usd)
                    - outstanding
                )
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
                remaining = (
                    float(monthly_row.cap_usd)
                    - float(monthly_row.spent_usd)
                    - outstanding
                )
                if estimated_cost > remaining:
                    return BudgetCheckResult(
                        allowed=False, reason="monthly_cap", remaining_usd=remaining
                    )

            if delegation_id:
                existing_reservation = await self._get_reservation_for_update(
                    org_id, agent_id, delegation_id
                )
                if existing_reservation is None:
                    self.db.add(
                        BudgetReservation(
                            delegation_id=delegation_id,
                            org_id=org_id,
                            agent_id=agent_id,
                            reserved_usd=Decimal(str(estimated_cost)),
                            settled_usd=Decimal("0"),
                            released_usd=Decimal("0"),
                            state="reserved",
                        )
                    )
                else:
                    existing_reservation.reserved_usd = Decimal(str(estimated_cost))
                    existing_reservation.state = "reserved"
                await self.db.flush()

                await self._assert_invariant(org_id, agent_id, delegation_id)

        return BudgetCheckResult(
            allowed=True, reason="", remaining_usd=request_cap - estimated_cost
        )

    async def settle(
        self, org_id: str, agent_id: str, delegation_id: str, actual_cost: float
    ) -> None:
        """Settle an existing reservation and release any unused amount."""
        reservation = await self._get_reservation_for_update(
            org_id, agent_id, delegation_id
        )
        if reservation is None:
            reservation = BudgetReservation(
                delegation_id=delegation_id,
                org_id=org_id,
                agent_id=agent_id,
                reserved_usd=Decimal(str(actual_cost)),
                settled_usd=Decimal("0"),
                released_usd=Decimal("0"),
                state="reserved",
            )
            self.db.add(reservation)
            await self.db.flush()

        outstanding = reservation.reserved_usd - reservation.settled_usd - reservation.released_usd
        if outstanding <= 0:
            await self._assert_invariant(org_id, agent_id, delegation_id)
            await self.db.commit()
            return

        requested = Decimal(str(actual_cost))
        settle_amount = min(requested, outstanding)

        if settle_amount > 0:
            reservation.settled_usd = reservation.settled_usd + settle_amount
            await self._apply_spend(org_id, agent_id, float(settle_amount))

        unused = reservation.reserved_usd - reservation.settled_usd - reservation.released_usd
        if unused > 0:
            reservation.released_usd = reservation.released_usd + unused

        reservation.state = (
            "settled"
            if reservation.settled_usd == reservation.reserved_usd
            else "adjusted"
        )

        await self._assert_invariant(org_id, agent_id, delegation_id)
        await self.db.commit()

    async def release(self, org_id: str, agent_id: str, delegation_id: str) -> None:
        """Release any remaining reserved amount for a delegation."""
        reservation = await self._get_reservation_for_update(
            org_id, agent_id, delegation_id
        )
        if reservation is None:
            return

        releasable = reservation.reserved_usd - reservation.settled_usd - reservation.released_usd
        if releasable > 0:
            reservation.released_usd = reservation.released_usd + releasable
        reservation.state = "released" if reservation.settled_usd == 0 else "adjusted"

        await self._assert_invariant(org_id, agent_id, delegation_id)
        await self.db.commit()

    async def _apply_spend(self, org_id: str, agent_id: str, actual_cost: float) -> None:
        """Update spent_usd for daily and monthly periods."""
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

    async def get_summary(
        self,
        org_id: str,
        agent_id: str | None = None,
    ) -> list[dict[str, object]]:
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

    async def _outstanding_reserved_usd(self, org_id: str, agent_id: str) -> float:
        outstanding_expr = (
            BudgetReservation.reserved_usd
            - BudgetReservation.settled_usd
            - BudgetReservation.released_usd
        )
        result = await self.db.execute(
            select(func.coalesce(func.sum(outstanding_expr), 0)).where(
                BudgetReservation.org_id == org_id,
                BudgetReservation.agent_id == agent_id,
                BudgetReservation.state.in_(["reserved", "adjusted"]),
            )
        )
        return float(result.scalar() or 0)

    async def _get_reservation_for_update(
        self, org_id: str, agent_id: str, delegation_id: str
    ) -> BudgetReservation | None:
        result = await self.db.execute(
            select(BudgetReservation)
            .where(
                BudgetReservation.org_id == org_id,
                BudgetReservation.agent_id == agent_id,
                BudgetReservation.delegation_id == delegation_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def _assert_invariant(
        self, org_id: str, agent_id: str, delegation_id: str
    ) -> None:
        reservation = await self._get_reservation_for_update(
            org_id, agent_id, delegation_id
        )
        if reservation is None:
            return
        if reservation.reserved_usd < reservation.settled_usd:
            raise ValueError("Budget invariant violated: reserved < settled")
        if reservation.reserved_usd < reservation.settled_usd + reservation.released_usd:
            raise ValueError("Budget invariant violated: reserved < settled + released")
