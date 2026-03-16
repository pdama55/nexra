"""budget reservation ledger for deterministic reserve/settle/release

Revision ID: 003
Revises: 002
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "budget_reservations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("delegation_id", UUID(as_uuid=True), sa.ForeignKey("delegations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column("reserved_usd", sa.Numeric(10, 4), nullable=False),
        sa.Column("settled_usd", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("released_usd", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("state", sa.Text(), nullable=False, server_default="reserved"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "delegation_id",
            "org_id",
            "agent_id",
            name="uq_budget_reservation_delegation_principal",
        ),
        sa.CheckConstraint(
            "state IN ('reserved','settled','released','adjusted')",
            name="ck_budget_reservations_state",
        ),
        sa.CheckConstraint(
            "reserved_usd >= 0 AND settled_usd >= 0 AND released_usd >= 0",
            name="ck_budget_reservations_non_negative",
        ),
        sa.CheckConstraint(
            "reserved_usd >= settled_usd + released_usd",
            name="ck_budget_reservations_invariant",
        ),
    )
    op.create_index(
        "ix_budget_reservations_org_agent",
        "budget_reservations",
        ["org_id", "agent_id", "created_at"],
    )
    op.create_index(
        "ix_budget_reservations_delegation",
        "budget_reservations",
        ["delegation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_budget_reservations_delegation", table_name="budget_reservations")
    op.drop_index("ix_budget_reservations_org_agent", table_name="budget_reservations")
    op.drop_table("budget_reservations")
