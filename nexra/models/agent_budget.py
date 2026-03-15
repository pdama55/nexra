import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class AgentBudget(Base):
    __tablename__ = "agent_budgets"

    agent_id: Mapped[str] = mapped_column(Text, primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    period: Mapped[date] = mapped_column(Date, primary_key=True)
    period_type: Mapped[str] = mapped_column(Text, primary_key=True)
    cap_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    spent_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "period_type IN ('daily', 'monthly')",
            name="ck_agent_budgets_period_type",
        ),
        Index("ix_agent_budgets_agent", "agent_id", "org_id", "period"),
    )
