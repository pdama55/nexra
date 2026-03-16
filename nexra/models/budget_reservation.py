import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin, UUIDMixin


class BudgetReservation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "budget_reservations"

    delegation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("delegations.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    reserved_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    settled_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, server_default="0")
    released_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, server_default="0")
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="reserved")

    __table_args__ = (
        UniqueConstraint(
            "delegation_id",
            "org_id",
            "agent_id",
            name="uq_budget_reservation_delegation_principal",
        ),
        CheckConstraint(
            "state IN ('reserved','settled','released','adjusted')",
            name="ck_budget_reservations_state",
        ),
        CheckConstraint(
            "reserved_usd >= 0 AND settled_usd >= 0 AND released_usd >= 0",
            name="ck_budget_reservations_non_negative",
        ),
        CheckConstraint(
            "reserved_usd >= settled_usd + released_usd",
            name="ck_budget_reservations_invariant",
        ),
        Index("ix_budget_reservations_org_agent", "org_id", "agent_id", "created_at"),
        Index("ix_budget_reservations_delegation", "delegation_id"),
    )
