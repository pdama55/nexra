"""marketplace and compliance additions

Revision ID: 002
Revises: 001
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add stripe_connect_account_id to organizations
    op.add_column(
        "organizations",
        sa.Column("stripe_connect_account_id", sa.Text(), nullable=True),
    )

    # Create pending_payouts table
    op.create_table(
        "pending_payouts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("delegation_id", UUID(as_uuid=True), sa.ForeignKey("delegations.id"), nullable=False),
        sa.Column("callee_org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("amount_usd", sa.Numeric(10, 4), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("stripe_transfer_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pending_payouts_org_status", "pending_payouts", ["org_id", "status"])
    op.create_index("ix_pending_payouts_callee", "pending_payouts", ["callee_org_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_pending_payouts_callee", table_name="pending_payouts")
    op.drop_index("ix_pending_payouts_org_status", table_name="pending_payouts")
    op.drop_table("pending_payouts")
    op.drop_column("organizations", "stripe_connect_account_id")
