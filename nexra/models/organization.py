import uuid

from sqlalchemy import CheckConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDMixin


class Organization(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    api_key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    api_key_prefix: Mapped[str] = mapped_column(
        String(16), nullable=False, index=True
    )
    stripe_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    stripe_connect_account_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="starter"
    )
    approval_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_email: Mapped[str | None] = mapped_column(
        Text, nullable=True, server_default="admin@nexra.local"
    )
    jwt_secret_enc: Mapped[str] = mapped_column(Text, nullable=False)
    max_delegation_depth: Mapped[int | None] = mapped_column(
        Integer, nullable=True, server_default="5"
    )
    schema_validation_enabled: Mapped[bool] = mapped_column(
        nullable=False,
        server_default="true",
    )
    delegation_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    agents = relationship(
        "Agent", back_populates="organization", cascade="all, delete-orphan"
    )
    policies = relationship(
        "Policy", back_populates="organization", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "plan IN ('starter', 'growth', 'enterprise')",
            name="ck_organizations_plan",
        ),
        CheckConstraint(
            "(max_delegation_depth IS NULL OR max_delegation_depth BETWEEN 1 AND 20)",
            name="ck_organizations_max_delegation_depth",
        ),
    )
