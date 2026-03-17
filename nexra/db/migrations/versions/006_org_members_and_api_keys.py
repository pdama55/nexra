"""add org api keys and org members

Revision ID: 006
Revises: 005
Create Date: 2026-03-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "org_api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "org_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False, server_default="default"),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("org_id", "key_prefix", name="uq_org_api_keys_prefix"),
    )
    op.create_index("ix_org_api_keys_org", "org_api_keys", ["org_id", "created_at"])
    op.create_index("ix_org_api_keys_prefix", "org_api_keys", ["key_prefix"])

    op.execute(
        """
        INSERT INTO org_api_keys (org_id, name, key_hash, key_prefix, created_at)
        SELECT id, 'primary', api_key_hash, api_key_prefix, created_at
        FROM organizations
        WHERE api_key_hash IS NOT NULL AND api_key_prefix IS NOT NULL
        """
    )

    op.create_table(
        "org_members",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "org_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default="viewer"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('admin','engineer','compliance','viewer')", name="ck_org_members_role"),
        sa.UniqueConstraint("org_id", "email", name="uq_org_members_email"),
    )
    op.create_index("ix_org_members_org", "org_members", ["org_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_org_members_org", table_name="org_members")
    op.drop_table("org_members")
    op.drop_index("ix_org_api_keys_prefix", table_name="org_api_keys")
    op.drop_index("ix_org_api_keys_org", table_name="org_api_keys")
    op.drop_table("org_api_keys")

