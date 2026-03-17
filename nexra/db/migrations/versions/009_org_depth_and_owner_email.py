"""add org max delegation depth and owner email

Revision ID: 009
Revises: 008
Create Date: 2026-03-17
"""

from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "max_delegation_depth",
            sa.Integer(),
            nullable=True,
            server_default="5",
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "owner_email",
            sa.Text(),
            nullable=True,
            server_default="admin@nexra.local",
        ),
    )
    op.create_check_constraint(
        "ck_organizations_max_delegation_depth",
        "organizations",
        "(max_delegation_depth IS NULL OR max_delegation_depth BETWEEN 1 AND 20)",
    )

    op.execute(
        """
        UPDATE organizations o
        SET owner_email = m.email
        FROM org_members m
        WHERE m.org_id = o.id
          AND m.role = 'admin'
          AND (
            o.owner_email IS NULL
            OR o.owner_email = 'admin@nexra.local'
          )
        """
    )


def downgrade() -> None:
    op.drop_constraint("ck_organizations_max_delegation_depth", "organizations", type_="check")
    op.drop_column("organizations", "owner_email")
    op.drop_column("organizations", "max_delegation_depth")
