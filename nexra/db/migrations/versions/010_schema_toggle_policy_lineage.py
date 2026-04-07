"""add schema validation toggle and policy lineage pointer

Revision ID: 010
Revises: 009
Create Date: 2026-04-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "schema_validation_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )

    op.add_column(
        "policies",
        sa.Column(
            "parent_policy_id",
            UUID(as_uuid=True),
            sa.ForeignKey("policies.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.execute(
        """
        WITH ranked AS (
            SELECT
                p.id,
                FIRST_VALUE(p.id) OVER (
                    PARTITION BY p.org_id, p.name
                    ORDER BY p.version ASC, p.created_at ASC, p.id ASC
                ) AS root_id
            FROM policies p
        )
        UPDATE policies p
        SET parent_policy_id = ranked.root_id
        FROM ranked
        WHERE ranked.id = p.id
        """
    )

    op.create_index(
        "ix_policies_org_parent_version",
        "policies",
        ["org_id", "parent_policy_id", "version"],
    )


def downgrade() -> None:
    op.drop_index("ix_policies_org_parent_version", table_name="policies")
    op.drop_column("policies", "parent_policy_id")
    op.drop_column("organizations", "schema_validation_enabled")
