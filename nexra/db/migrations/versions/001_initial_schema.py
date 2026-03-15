"""Initial schema - all tables, indexes, triggers

Revision ID: 001
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')

    # organizations
    op.create_table(
        "organizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("api_key_hash", sa.Text, nullable=False, unique=True),
        sa.Column("api_key_prefix", sa.String(16), nullable=False, index=True),
        sa.Column("stripe_id", sa.Text, nullable=True),
        sa.Column("plan", sa.Text, nullable=False, server_default="starter"),
        sa.Column("approval_url", sa.Text, nullable=True),
        sa.Column("jwt_secret_enc", sa.Text, nullable=False),
        sa.Column("delegation_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("plan IN ('starter','growth','enterprise')", name="ck_organizations_plan"),
    )

    # agents
    op.create_table(
        "agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("capability_type", sa.Text, nullable=False),
        sa.Column("input_schema", JSONB, nullable=False),
        sa.Column("output_schema", JSONB, nullable=False),
        sa.Column("webhook_url", sa.Text, nullable=False),
        sa.Column("webhook_secret", sa.Text, nullable=False),
        sa.Column("pricing", JSONB, nullable=False),
        sa.Column("sla", JSONB, nullable=False),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("trust_score", sa.Numeric(4, 3), nullable=False, server_default="1.000"),
        sa.Column("status", sa.Text, nullable=False, server_default="probationary"),
        sa.Column("delegation_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "agent_id", name="uq_agents_org_agent"),
        sa.CheckConstraint(
            "capability_type IN ('research','analysis','generation','enrichment','validation','execution','other')",
            name="ck_agents_capability_type",
        ),
        sa.CheckConstraint("webhook_url LIKE 'https://%'", name="ck_agents_webhook_https"),
        sa.CheckConstraint("trust_score >= 0.000 AND trust_score <= 1.000", name="ck_agents_trust_score_range"),
        sa.CheckConstraint("status IN ('active','probationary','quarantined')", name="ck_agents_status"),
    )

    # pgvector embedding column — Alembic doesn't natively support VECTOR type
    op.execute("ALTER TABLE agents ADD COLUMN embedding VECTOR(1536)")

    # agents indexes
    op.execute(
        "CREATE INDEX ix_agents_embedding ON agents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
    op.create_index("ix_agents_cap_type", "agents", ["capability_type", "status"])
    op.create_index("ix_agents_org_status", "agents", ["org_id", "status"])
    op.execute("CREATE INDEX ix_agents_is_public ON agents (is_public) WHERE is_public = TRUE")

    # policies
    op.create_table(
        "policies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("priority", sa.Integer, nullable=False, server_default="100"),
        sa.Column("rule_yaml", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "name", "version", name="uq_policies_org_name_version"),
    )
    op.execute("CREATE INDEX ix_policies_org_priority ON policies (org_id, priority ASC) WHERE enabled = TRUE")

    # delegations
    op.create_table(
        "delegations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("caller_org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("caller_agent_id", sa.Text, nullable=False),
        sa.Column("callee_org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("callee_agent_id", sa.Text, nullable=False),
        sa.Column("task", JSONB, nullable=False),
        sa.Column("task_hash", sa.Text, nullable=False),
        sa.Column("context_scope", sa.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("policy_id", UUID(as_uuid=True), sa.ForeignKey("policies.id"), nullable=True),
        sa.Column("policy_version", sa.Integer, nullable=True),
        sa.Column("policy_decision", sa.Text, nullable=True),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("budget_cap_usd", sa.Numeric(10, 4), nullable=True),
        sa.Column("estimated_cost_usd", sa.Numeric(10, 4), nullable=True),
        sa.Column("actual_cost_usd", sa.Numeric(10, 4), nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("llm_tokens", sa.Integer, nullable=True),
        sa.Column("callback_url", sa.Text, nullable=True),
        sa.Column("delegation_depth", sa.Integer, nullable=False, server_default="0"),
        sa.Column("parent_delegation_id", UUID(as_uuid=True), sa.ForeignKey("delegations.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("policy_decision IN ('allow','block','pause')", name="ck_delegations_policy_decision"),
        sa.CheckConstraint(
            "status IN ('pending','in_flight','completed','failed','timeout','blocked','pending_approval')",
            name="ck_delegations_status",
        ),
    )
    op.create_index("ix_delegations_caller", "delegations", ["caller_org_id", "caller_agent_id", "created_at"])
    op.create_index("ix_delegations_callee", "delegations", ["callee_agent_id", "created_at"])
    op.create_index("ix_delegations_status", "delegations", ["status", "created_at"])
    op.execute(
        "CREATE INDEX ix_delegations_parent ON delegations (parent_delegation_id) "
        "WHERE parent_delegation_id IS NOT NULL"
    )

    # audit_log
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("delegation_id", UUID(as_uuid=True), sa.ForeignKey("delegations.id"), nullable=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("actor_agent_id", sa.Text, nullable=True),
        sa.Column("target_agent_id", sa.Text, nullable=True),
        sa.Column("details", JSONB, nullable=False),
        sa.Column("cost_usd", sa.Numeric(10, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "event_type IN ("
            "'policy_evaluated','delegation_initiated','delegation_completed',"
            "'delegation_failed','delegation_blocked','delegation_timeout',"
            "'agent_quarantined','agent_activated','budget_exceeded',"
            "'hil_triggered','hil_approved','hil_expired',"
            "'anomaly_detected','circuit_breaker_tripped'"
            ")",
            name="ck_audit_log_event_type",
        ),
    )
    op.create_index("ix_audit_log_org", "audit_log", ["org_id", "created_at"])
    op.create_index("ix_audit_log_delegation", "audit_log", ["delegation_id"])
    op.create_index("ix_audit_log_event_type", "audit_log", ["event_type", "created_at"])
    op.create_index("ix_audit_log_agent", "audit_log", ["actor_agent_id", "created_at"])

    # audit_log immutability trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_log_immutable() RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log rows are immutable - no UPDATE or DELETE permitted';
        END; $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER enforce_audit_immutability
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();
    """)

    # agent_budgets
    op.create_table(
        "agent_budgets",
        sa.Column("agent_id", sa.Text, primary_key=True),
        sa.Column(
            "org_id", UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column("period", sa.Date, primary_key=True),
        sa.Column("period_type", sa.Text, primary_key=True),
        sa.Column("cap_usd", sa.Numeric(10, 4), nullable=False),
        sa.Column("spent_usd", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("period_type IN ('daily','monthly')", name="ck_agent_budgets_period_type"),
    )
    op.create_index("ix_agent_budgets_agent", "agent_budgets", ["agent_id", "org_id", "period"])

    # trust_score_events
    op.create_table(
        "trust_score_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_id", sa.Text, nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("delegation_id", UUID(as_uuid=True), sa.ForeignKey("delegations.id"), nullable=True),
        sa.Column("score_before", sa.Numeric(4, 3), nullable=False),
        sa.Column("score_after", sa.Numeric(4, 3), nullable=False),
        sa.Column("components", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_tse_agent", "trust_score_events", ["agent_id", "org_id", "created_at"])


def downgrade() -> None:
    op.drop_table("trust_score_events")
    op.drop_table("agent_budgets")
    op.execute("DROP TRIGGER IF EXISTS enforce_audit_immutability ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS audit_log_immutable()")
    op.drop_table("audit_log")
    op.drop_table("delegations")
    op.drop_table("policies")
    op.drop_table("agents")
    op.drop_table("organizations")
    op.execute('DROP EXTENSION IF EXISTS "vector"')
    op.execute('DROP EXTENSION IF EXISTS "pgcrypto"')
