import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, UUIDMixin


class Delegation(UUIDMixin, Base):
    __tablename__ = "delegations"

    caller_org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    caller_agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    callee_org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=True,
    )
    callee_agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    task: Mapped[dict] = mapped_column(JSONB, nullable=False)
    task_hash: Mapped[str] = mapped_column(Text, nullable=False)
    context_scope: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policies.id"),
        nullable=True,
    )
    policy_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    policy_decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    budget_cap_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    actual_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    callback_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow: Mapped[str] = mapped_column(Text, nullable=False, server_default="unclassified")
    delegation_depth: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    parent_delegation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("delegations.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "policy_decision IN ('allow','block','pause')",
            name="ck_delegations_policy_decision",
        ),
        CheckConstraint(
            "status IN ('pending','in_flight','completed','failed','timeout','blocked','pending_approval')",
            name="ck_delegations_status",
        ),
        Index(
            "ix_delegations_caller",
            "caller_org_id",
            "caller_agent_id",
            "created_at",
        ),
        Index("ix_delegations_callee", "callee_agent_id", "created_at"),
        Index("ix_delegations_status", "status", "created_at"),
        Index(
            "ix_delegations_parent",
            "parent_delegation_id",
            postgresql_where="parent_delegation_id IS NOT NULL",
        ),
    )
