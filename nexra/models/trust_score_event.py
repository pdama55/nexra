import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, UUIDMixin


class TrustScoreEvent(UUIDMixin, Base):
    __tablename__ = "trust_score_events"

    agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    delegation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("delegations.id"),
        nullable=True,
    )
    score_before: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False
    )
    score_after: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False
    )
    components: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    __table_args__ = (
        Index("ix_tse_agent", "agent_id", "org_id", "created_at"),
    )
