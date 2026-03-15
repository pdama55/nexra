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
    jwt_secret_enc: Mapped[str] = mapped_column(Text, nullable=False)
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
    )
