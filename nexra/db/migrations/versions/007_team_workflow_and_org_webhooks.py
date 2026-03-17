"""Add team/workflow metadata and org notification webhook.

Revision ID: 007
Revises: 006
Create Date: 2026-03-17
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("notification_url", sa.Text(), nullable=True))

    op.add_column(
        "agents",
        sa.Column("team", sa.Text(), nullable=False, server_default="unassigned"),
    )
    op.create_index("ix_agents_org_team", "agents", ["org_id", "team"])

    op.add_column(
        "delegations",
        sa.Column("workflow", sa.Text(), nullable=False, server_default="unclassified"),
    )
    op.create_index("ix_delegations_workflow", "delegations", ["caller_org_id", "workflow", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_delegations_workflow", table_name="delegations")
    op.drop_column("delegations", "workflow")

    op.drop_index("ix_agents_org_team", table_name="agents")
    op.drop_column("agents", "team")

    op.drop_column("organizations", "notification_url")
