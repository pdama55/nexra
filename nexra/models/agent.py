import uuid
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDMixin


class Agent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "agents"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    capability_type: Mapped[str] = mapped_column(Text, nullable=False)
    input_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    webhook_url: Mapped[str] = mapped_column(Text, nullable=False)
    webhook_secret: Mapped[str] = mapped_column(Text, nullable=False)
    pricing: Mapped[dict] = mapped_column(JSONB, nullable=False)
    sla: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    embedding = mapped_column(Vector(1536), nullable=True)
    trust_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False, server_default="1.000"
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="probationary"
    )
    delegation_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    organization = relationship("Organization", back_populates="agents")

    __table_args__ = (
        UniqueConstraint("org_id", "agent_id", name="uq_agents_org_agent"),
        CheckConstraint(
            "capability_type IN ('research','analysis','generation','enrichment','validation','execution','other')",
            name="ck_agents_capability_type",
        ),
        CheckConstraint(
            "webhook_url LIKE 'https://%'",
            name="ck_agents_webhook_https",
        ),
        CheckConstraint(
            "trust_score >= 0.000 AND trust_score <= 1.000",
            name="ck_agents_trust_score_range",
        ),
        CheckConstraint(
            "status IN ('active','probationary','quarantined')",
            name="ck_agents_status",
        ),
        Index(
            "ix_agents_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_agents_cap_type", "capability_type", "status"),
        Index("ix_agents_org_status", "org_id", "status"),
        Index(
            "ix_agents_is_public",
            "is_public",
            postgresql_where="is_public = TRUE",
        ),
    )
