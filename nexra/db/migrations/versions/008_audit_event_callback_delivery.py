"""add callback delivery events to audit_log event constraint

Revision ID: 008
Revises: 007
Create Date: 2026-03-17
"""

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_audit_log_event_type", "audit_log", type_="check")
    op.create_check_constraint(
        "ck_audit_log_event_type",
        "audit_log",
        "("
        "event_type IN ("
        "'policy_evaluated','delegation_initiated','delegation_completed',"
        "'delegation_failed','delegation_blocked','delegation_timeout',"
        "'agent_quarantined','agent_activated','budget_exceeded',"
        "'hil_triggered','hil_approved','hil_expired',"
        "'anomaly_detected','circuit_breaker_tripped',"
        "'marketplace_payout','callback_delivered','callback_failed'"
        ")"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint("ck_audit_log_event_type", "audit_log", type_="check")
    op.create_check_constraint(
        "ck_audit_log_event_type",
        "audit_log",
        "("
        "event_type IN ("
        "'policy_evaluated','delegation_initiated','delegation_completed',"
        "'delegation_failed','delegation_blocked','delegation_timeout',"
        "'agent_quarantined','agent_activated','budget_exceeded',"
        "'hil_triggered','hil_approved','hil_expired',"
        "'anomaly_detected','circuit_breaker_tripped',"
        "'marketplace_payout'"
        ")"
        ")",
    )
