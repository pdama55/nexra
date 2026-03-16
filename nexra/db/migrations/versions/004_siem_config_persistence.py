"""persist SIEM configuration and export cursor

Revision ID: 004
Revises: 003
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "siem_configs",
        sa.Column(
            "org_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("target", sa.Text(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("api_key", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("event_types", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("cursor", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_siem_configs_enabled", "siem_configs", ["enabled"])


def downgrade() -> None:
    op.drop_index("ix_siem_configs_enabled", table_name="siem_configs")
    op.drop_table("siem_configs")
