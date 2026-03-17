import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, UUIDMixin


class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_log"

    delegation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("delegations.id"),
        nullable=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_agent_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_agent_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False)
    cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'policy_evaluated','delegation_initiated','delegation_completed',"
            "'delegation_failed','delegation_blocked','delegation_timeout',"
            "'agent_quarantined','agent_activated','budget_exceeded',"
            "'hil_triggered','hil_approved','hil_expired',"
            "'anomaly_detected','circuit_breaker_tripped',"
            "'marketplace_payout','callback_delivered','callback_failed'"
            ")",
            name="ck_audit_log_event_type",
        ),
        Index("ix_audit_log_org", "org_id", "created_at"),
        Index("ix_audit_log_delegation", "delegation_id"),
        Index("ix_audit_log_event_type", "event_type", "created_at"),
        Index("ix_audit_log_agent", "actor_agent_id", "created_at"),
    )
