# Phase 13 — Cross-Org Marketplace & Compliance (P2)

> **TDD Sections**: §25.1 (v2 Features — Marketplace, Schema Validation, Policy Versioning, Compliance Exports), §25.2 (v3 Considerations)
>
> **Depends On**: Phase 12 (Dashboard + SIEM + Adapters complete). All P1 features operational.

---

## 1. Prerequisites

- [ ] All P0 (Phases 1–9) and P1 (Phases 10–12) features complete and tested
- [ ] Stripe integration operational (BillingService from Phase 8)
- [ ] `is_public` column exists on agents table (from Phase 1)
- [ ] `include_cross_org` parameter exists on discovery endpoint (from Phase 4)
- [ ] Policy model has `version` column (from Phase 1)
- [ ] AuditService fully operational with all event types
- [ ] jsonschema library available (from Phase 6)
- [ ] Stripe Connect API access configured (test mode)

---

## 2. Objective

This phase delivers four P2 features that enable enterprise sales:

1. **Cross-Org Marketplace**: Agents with `is_public=true` become discoverable by other orgs. Callee org receives 80% of `per_call_usd` via Stripe Connect. Nexra retains 20% platform fee.

2. **Compliance Report Exports**: One-click structured exports for SOC 2, GDPR, and HIPAA from the audit_log. Maps audit events to regulator-specific report formats.

3. **Schema Validation Enforcement**: Enable by default — validate caller's task payload against callee's `input_schema` and callee's result against `output_schema` on every delegation.

4. **Policy Version Control**: Policy updates create new versions. Old versions preserved. Audit entries reference the exact `policy_version` that governed them. Enables post-hoc compliance review.

---

## 3. Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Cross-org discovery | Extend existing pgvector query with `is_public=true OR same_org` filter | TDD §25.1. No new table needed. |
| Stripe Connect flow | Standard Connect with manual payouts (monthly batch) | TDD §16.2. Callee orgs complete Stripe Connect onboarding before receiving payouts. |
| Platform fee | 20% retained by Nexra, 80% transferred to callee org | PRD §14. Hardcoded for v1, configurable per-org in v2. |
| Pending payouts | `pending_payouts` table for pre-onboarding revenue | Callee orgs may register public agents before completing Stripe Connect KYC. Revenue accrues and is paid out after onboarding. |
| Compliance reports | Generated from audit_log queries, returned as JSON or CSV | TDD §25.1. No new data needed — reports are views over existing audit data. |
| Report formats | SOC 2 (all actions + policy decisions), GDPR (data access by agent), HIPAA (PHI access log) | PRD §6. Each format maps specific audit event types to report fields. |
| Schema validation | `jsonschema.validate()` on input before webhook, on output after response | TDD §25.1. Already in codebase from Phase 6 — enable by default. |
| Validation toggle | Per-org config flag `schema_validation_enabled` (default: true) | Some orgs may need to disable for A2A agents with passthrough schemas. |
| Policy versioning | `parent_policy_id` FK on policies table, version auto-incremented | TDD §25.1. Old versions immutable. New version created on update. |

---

## 4. Database Migrations

### 4.1 Add `stripe_connect_account_id` to Organizations

**Migration file**: `db/migrations/versions/XXX_add_stripe_connect.py`

```python
"""Add Stripe Connect fields to organizations."""

from alembic import op
import sqlalchemy as sa

revision = "XXX"
down_revision = "<previous_revision>"


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("stripe_connect_account_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("schema_validation_enabled", sa.Boolean(), server_default="true"),
    )


def downgrade() -> None:
    op.drop_column("organizations", "stripe_connect_account_id")
    op.drop_column("organizations", "schema_validation_enabled")
```

### 4.2 Create `pending_payouts` Table

**Migration file**: `db/migrations/versions/XXX_create_pending_payouts.py`

```python
"""Create pending_payouts table for pre-Connect-onboarding revenue."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "XXX"
down_revision = "<previous_revision>"


def upgrade() -> None:
    op.create_table(
        "pending_payouts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("callee_org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("delegation_id", UUID(as_uuid=True),
                  sa.ForeignKey("delegations.id"), nullable=False),
        sa.Column("amount_usd", sa.Numeric(10, 4), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("stripe_transfer_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'paid', 'failed')",
            name="pending_payouts_status_check",
        ),
    )
    op.create_index(
        "ix_pending_payouts_callee_status",
        "pending_payouts",
        ["callee_org_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("pending_payouts")
```

### 4.3 Add `parent_policy_id` to Policies

**Migration file**: `db/migrations/versions/XXX_add_policy_versioning.py`

```python
"""Add parent_policy_id for policy version control."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "XXX"
down_revision = "<previous_revision>"


def upgrade() -> None:
    op.add_column(
        "policies",
        sa.Column("parent_policy_id", UUID(as_uuid=True),
                  sa.ForeignKey("policies.id"), nullable=True),
    )
    op.create_index(
        "ix_policies_parent_version",
        "policies",
        ["parent_policy_id", "version"],
    )


def downgrade() -> None:
    op.drop_index("ix_policies_parent_version")
    op.drop_column("policies", "parent_policy_id")
```

---

## 5. File-by-File Implementation Guide

### 5.1 `models/pending_payout.py` (New File)

**Path**: `nexra/models/pending_payout.py`

```python
from sqlalchemy import Column, Text, Numeric, ForeignKey, DateTime, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from models.base import Base


class PendingPayout(Base):
    __tablename__ = "pending_payouts"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    callee_org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    delegation_id = Column(UUID(as_uuid=True), ForeignKey("delegations.id"), nullable=False)
    amount_usd = Column(Numeric(10, 4), nullable=False)
    status = Column(Text, nullable=False, server_default="pending")
    stripe_transfer_id = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    paid_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'paid', 'failed')", name="pending_payouts_status_check"),
    )
```

---

### 5.2 `services/marketplace_service.py` (New File)

**Path**: `nexra/services/marketplace_service.py`

```python
import logging
from datetime import datetime, timezone
from decimal import Decimal

import stripe
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from models.organization import Organization
from models.delegation import Delegation
from models.pending_payout import PendingPayout
from services.audit_service import AuditService
from core.config import get_settings
from core.errors import NexraError

logger = logging.getLogger("nexra.services.marketplace")

PLATFORM_FEE_PCT = Decimal("0.20")  # 20% Nexra platform fee
CALLEE_SHARE_PCT = Decimal("1.00") - PLATFORM_FEE_PCT  # 80% to callee


class MarketplaceService:
    """Cross-org marketplace settlement via Stripe Connect.

    When a delegation crosses org boundaries (caller_org != callee_org),
    this service handles the revenue split:
    - 80% of per_call_usd → callee org (via Stripe Connect transfer)
    - 20% → Nexra platform fee (retained in Stripe balance)

    If callee org has not completed Stripe Connect onboarding,
    revenue is stored in pending_payouts and paid out after onboarding.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.audit = AuditService(db)
        self.settings = get_settings()
        stripe.api_key = self.settings.stripe_secret_key

    async def settle_cross_org_delegation(
        self,
        delegation: Delegation,
        callee_org: Organization,
        actual_cost_usd: Decimal,
    ) -> dict:
        """Settle a cross-org delegation with revenue split.

        Args:
            delegation: Completed delegation record
            callee_org: Organization that owns the callee agent
            actual_cost_usd: Actual cost of the delegation

        Returns:
            dict with settlement details
        """
        callee_amount = actual_cost_usd * CALLEE_SHARE_PCT
        platform_fee = actual_cost_usd * PLATFORM_FEE_PCT

        if callee_org.stripe_connect_account_id:
            return await self._transfer_immediately(
                delegation=delegation,
                callee_org=callee_org,
                callee_amount=callee_amount,
                platform_fee=platform_fee,
            )
        else:
            return await self._queue_pending_payout(
                delegation=delegation,
                callee_org=callee_org,
                callee_amount=callee_amount,
                platform_fee=platform_fee,
            )

    async def _transfer_immediately(
        self,
        delegation: Delegation,
        callee_org: Organization,
        callee_amount: Decimal,
        platform_fee: Decimal,
    ) -> dict:
        """Execute Stripe Connect transfer immediately."""
        try:
            transfer = stripe.Transfer.create(
                amount=int(callee_amount * 100),  # Convert to cents
                currency="usd",
                destination=callee_org.stripe_connect_account_id,
                metadata={
                    "delegation_id": str(delegation.id),
                    "callee_org_id": str(callee_org.id),
                    "platform_fee_usd": str(platform_fee),
                },
            )

            await self.audit.append(
                org_id=str(callee_org.id),
                event_type="marketplace_payout",
                actor_agent_id=None,
                target_agent_id=delegation.callee_agent_id,
                delegation_id=str(delegation.id),
                cost_usd=float(callee_amount),
                details={
                    "stripe_transfer_id": transfer.id,
                    "callee_amount_usd": float(callee_amount),
                    "platform_fee_usd": float(platform_fee),
                    "status": "paid",
                },
            )

            return {
                "status": "paid",
                "callee_amount_usd": float(callee_amount),
                "platform_fee_usd": float(platform_fee),
                "stripe_transfer_id": transfer.id,
            }

        except stripe.StripeError as e:
            logger.error(
                f"Stripe Connect transfer failed for delegation "
                f"{delegation.id}: {e}"
            )
            return await self._queue_pending_payout(
                delegation=delegation,
                callee_org=callee_org,
                callee_amount=callee_amount,
                platform_fee=platform_fee,
            )

    async def _queue_pending_payout(
        self,
        delegation: Delegation,
        callee_org: Organization,
        callee_amount: Decimal,
        platform_fee: Decimal,
    ) -> dict:
        """Queue payout for when callee org completes Stripe Connect onboarding."""
        payout = PendingPayout(
            callee_org_id=callee_org.id,
            delegation_id=delegation.id,
            amount_usd=callee_amount,
            status="pending",
        )
        self.db.add(payout)
        await self.db.flush()

        logger.info(
            f"Queued pending payout of ${callee_amount} for org "
            f"{callee_org.id} (delegation {delegation.id})"
        )

        return {
            "status": "pending",
            "callee_amount_usd": float(callee_amount),
            "platform_fee_usd": float(platform_fee),
            "reason": "Callee org has not completed Stripe Connect onboarding",
        }

    async def process_pending_payouts(self, org_id: str) -> list[dict]:
        """Process all pending payouts for an org that has completed Connect onboarding.

        Called after an org completes Stripe Connect onboarding.

        Args:
            org_id: UUID of the org to process payouts for

        Returns:
            List of processed payout results
        """
        org_result = await self.db.execute(
            select(Organization).where(Organization.id == org_id)
        )
        org = org_result.scalar_one_or_none()

        if not org or not org.stripe_connect_account_id:
            raise NexraError(
                400,
                "CONNECT_NOT_CONFIGURED",
                "Org has not completed Stripe Connect onboarding",
            )

        pending_result = await self.db.execute(
            select(PendingPayout).where(
                PendingPayout.callee_org_id == org_id,
                PendingPayout.status == "pending",
            )
        )
        pending = pending_result.scalars().all()

        results = []
        for payout in pending:
            try:
                transfer = stripe.Transfer.create(
                    amount=int(payout.amount_usd * 100),
                    currency="usd",
                    destination=org.stripe_connect_account_id,
                    metadata={
                        "delegation_id": str(payout.delegation_id),
                        "pending_payout_id": str(payout.id),
                    },
                )
                payout.status = "paid"
                payout.stripe_transfer_id = transfer.id
                payout.paid_at = datetime.now(timezone.utc)
                results.append({
                    "payout_id": str(payout.id),
                    "amount_usd": float(payout.amount_usd),
                    "status": "paid",
                    "stripe_transfer_id": transfer.id,
                })
            except stripe.StripeError as e:
                payout.status = "failed"
                results.append({
                    "payout_id": str(payout.id),
                    "amount_usd": float(payout.amount_usd),
                    "status": "failed",
                    "error": str(e),
                })

        await self.db.commit()
        return results
```

---

### 5.3 `services/compliance_service.py` (New File)

**Path**: `nexra/services/compliance_service.py`

```python
import csv
import io
import json
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from models.audit_log import AuditLog
from models.delegation import Delegation
from models.agent import Agent
from core.errors import NexraError

logger = logging.getLogger("nexra.services.compliance")


class ComplianceService:
    """Compliance report generation from audit_log data.

    Generates structured exports for:
    - SOC 2: All agent actions with timestamps and policy decisions
    - GDPR: Data access audit trail per agent (context_scope tracking)
    - HIPAA: PHI access log by agent and delegation
    - Generic: Full audit dump for internal review

    Reports are generated as JSON or CSV from existing audit_log data.
    No new data collection required.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def generate_soc2_report(
        self,
        org_id: str,
        date_from: datetime,
        date_to: datetime,
        output_format: str = "json",
    ) -> dict | str:
        """Generate SOC 2 compliance report.

        SOC 2 requires evidence of:
        - Access controls (who accessed what, when)
        - Policy enforcement (what rules governed each action)
        - Change management (policy changes, agent status changes)
        - Incident response (quarantines, circuit breaker trips)

        Mapped audit event types:
        - policy_evaluated → Access control evidence
        - delegation_completed/failed → Processing integrity
        - agent_quarantined → Incident response
        - circuit_breaker_tripped → Availability monitoring
        - hil_triggered/approved/expired → Change management
        """
        events = await self._fetch_events(
            org_id=org_id,
            date_from=date_from,
            date_to=date_to,
            event_types=[
                "policy_evaluated",
                "delegation_initiated",
                "delegation_completed",
                "delegation_failed",
                "delegation_blocked",
                "agent_quarantined",
                "agent_activated",
                "circuit_breaker_tripped",
                "hil_triggered",
                "hil_approved",
                "hil_expired",
                "anomaly_detected",
            ],
        )

        report = {
            "report_type": "SOC 2 Type II Evidence",
            "organization_id": org_id,
            "period": {
                "from": date_from.isoformat(),
                "to": date_to.isoformat(),
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_events": len(events),
                "policy_evaluations": sum(
                    1 for e in events if e["event_type"] == "policy_evaluated"
                ),
                "delegations_completed": sum(
                    1 for e in events if e["event_type"] == "delegation_completed"
                ),
                "delegations_blocked": sum(
                    1 for e in events if e["event_type"] == "delegation_blocked"
                ),
                "incidents": sum(
                    1
                    for e in events
                    if e["event_type"]
                    in ("agent_quarantined", "circuit_breaker_tripped", "anomaly_detected")
                ),
                "hil_gates_triggered": sum(
                    1 for e in events if e["event_type"] == "hil_triggered"
                ),
            },
            "sections": {
                "access_controls": [
                    e for e in events if e["event_type"] == "policy_evaluated"
                ],
                "processing_integrity": [
                    e
                    for e in events
                    if e["event_type"]
                    in ("delegation_completed", "delegation_failed")
                ],
                "incident_response": [
                    e
                    for e in events
                    if e["event_type"]
                    in (
                        "agent_quarantined",
                        "circuit_breaker_tripped",
                        "anomaly_detected",
                    )
                ],
                "change_management": [
                    e
                    for e in events
                    if e["event_type"]
                    in ("hil_triggered", "hil_approved", "hil_expired")
                ],
            },
            "events": events,
        }

        if output_format == "csv":
            return self._to_csv(events)
        return report

    async def generate_gdpr_report(
        self,
        org_id: str,
        date_from: datetime,
        date_to: datetime,
        agent_id: str | None = None,
        output_format: str = "json",
    ) -> dict | str:
        """Generate GDPR data access report.

        GDPR requires evidence of:
        - What data was accessed (context_scope grants)
        - By which agent (actor/target)
        - For what purpose (delegation task type)
        - When (timestamp)
        - Under what authority (policy_id)

        Focuses on delegation_initiated events which contain context_scope.
        """
        events = await self._fetch_events(
            org_id=org_id,
            date_from=date_from,
            date_to=date_to,
            event_types=["delegation_initiated", "delegation_completed"],
            agent_id=agent_id,
        )

        # Enrich with context_scope from delegation records
        delegation_ids = [
            e["delegation_id"] for e in events if e.get("delegation_id")
        ]
        context_map = {}
        if delegation_ids:
            deleg_result = await self.db.execute(
                select(Delegation.id, Delegation.context_scope, Delegation.task).where(
                    Delegation.id.in_(delegation_ids)
                )
            )
            for d in deleg_result.all():
                context_map[str(d.id)] = {
                    "context_scope": d.context_scope or [],
                    "task_type": d.task.get("type", "unknown") if d.task else "unknown",
                }

        data_access_entries = []
        for event in events:
            deleg_info = context_map.get(event.get("delegation_id"), {})
            data_access_entries.append({
                "timestamp": event["timestamp"],
                "actor_agent_id": event.get("actor_agent_id"),
                "target_agent_id": event.get("target_agent_id"),
                "delegation_id": event.get("delegation_id"),
                "data_accessed": deleg_info.get("context_scope", []),
                "purpose": deleg_info.get("task_type", "unknown"),
                "policy_id": event.get("details", {}).get("policy_id"),
                "event_type": event["event_type"],
            })

        report = {
            "report_type": "GDPR Data Access Audit",
            "organization_id": org_id,
            "period": {
                "from": date_from.isoformat(),
                "to": date_to.isoformat(),
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "filter_agent_id": agent_id,
            "summary": {
                "total_data_access_events": len(data_access_entries),
                "unique_agents": len(
                    set(
                        e["actor_agent_id"]
                        for e in data_access_entries
                        if e["actor_agent_id"]
                    )
                ),
                "unique_data_scopes": list(
                    set(
                        scope
                        for e in data_access_entries
                        for scope in e["data_accessed"]
                    )
                ),
            },
            "data_access_log": data_access_entries,
        }

        if output_format == "csv":
            return self._to_csv(data_access_entries)
        return report

    async def generate_hipaa_report(
        self,
        org_id: str,
        date_from: datetime,
        date_to: datetime,
        output_format: str = "json",
    ) -> dict | str:
        """Generate HIPAA PHI access report.

        HIPAA requires tracking of:
        - All access to Protected Health Information (PHI)
        - Who accessed it (agent identity)
        - When (timestamp)
        - What was accessed (context_scope containing PHI-related keys)
        - Authorization basis (policy_id)

        PHI-related context_scope keys are identified by pattern matching:
        'patient_*', 'health_*', 'medical_*', 'phi_*', 'hipaa_*'
        """
        PHI_PATTERNS = ["patient_", "health_", "medical_", "phi_", "hipaa_"]

        events = await self._fetch_events(
            org_id=org_id,
            date_from=date_from,
            date_to=date_to,
            event_types=["delegation_initiated", "delegation_completed"],
        )

        delegation_ids = [
            e["delegation_id"] for e in events if e.get("delegation_id")
        ]
        phi_entries = []

        if delegation_ids:
            deleg_result = await self.db.execute(
                select(Delegation).where(Delegation.id.in_(delegation_ids))
            )
            for d in deleg_result.scalars().all():
                phi_scopes = [
                    scope
                    for scope in (d.context_scope or [])
                    if any(scope.startswith(p) for p in PHI_PATTERNS)
                ]
                if phi_scopes:
                    phi_entries.append({
                        "timestamp": d.created_at.isoformat() if d.created_at else None,
                        "delegation_id": str(d.id),
                        "caller_agent_id": d.caller_agent_id,
                        "callee_agent_id": d.callee_agent_id,
                        "phi_data_accessed": phi_scopes,
                        "all_context_scope": d.context_scope,
                        "policy_id": str(d.policy_id) if d.policy_id else None,
                        "policy_version": d.policy_version,
                        "status": d.status,
                    })

        report = {
            "report_type": "HIPAA PHI Access Audit",
            "organization_id": org_id,
            "period": {
                "from": date_from.isoformat(),
                "to": date_to.isoformat(),
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_phi_access_events": len(phi_entries),
                "unique_phi_scopes": list(
                    set(
                        scope
                        for e in phi_entries
                        for scope in e["phi_data_accessed"]
                    )
                ),
                "unique_agents_accessing_phi": list(
                    set(e["callee_agent_id"] for e in phi_entries)
                ),
            },
            "phi_access_log": phi_entries,
        }

        if output_format == "csv":
            return self._to_csv(phi_entries)
        return report

    async def _fetch_events(
        self,
        org_id: str,
        date_from: datetime,
        date_to: datetime,
        event_types: list[str],
        agent_id: str | None = None,
    ) -> list[dict]:
        """Fetch audit_log events for report generation."""
        filters = [
            AuditLog.org_id == org_id,
            AuditLog.created_at >= date_from,
            AuditLog.created_at <= date_to,
            AuditLog.event_type.in_(event_types),
        ]
        if agent_id:
            filters.append(
                (AuditLog.actor_agent_id == agent_id)
                | (AuditLog.target_agent_id == agent_id)
            )

        result = await self.db.execute(
            select(AuditLog)
            .where(and_(*filters))
            .order_by(AuditLog.created_at.asc())
        )
        events = result.scalars().all()

        return [
            {
                "id": str(e.id),
                "timestamp": e.created_at.isoformat() if e.created_at else None,
                "event_type": e.event_type,
                "delegation_id": str(e.delegation_id) if e.delegation_id else None,
                "actor_agent_id": e.actor_agent_id,
                "target_agent_id": e.target_agent_id,
                "cost_usd": float(e.cost_usd) if e.cost_usd else None,
                "details": e.details or {},
            }
            for e in events
        ]

    @staticmethod
    def _to_csv(rows: list[dict]) -> str:
        """Convert list of dicts to CSV string."""
        if not rows:
            return ""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        for row in rows:
            flat_row = {}
            for k, v in row.items():
                if isinstance(v, (dict, list)):
                    flat_row[k] = json.dumps(v)
                else:
                    flat_row[k] = v
            writer.writerow(flat_row)
        return output.getvalue()
```

---

### 5.4 `services/policy_version_service.py` (New File)

**Path**: `nexra/services/policy_version_service.py`

```python
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from models.policy import Policy
from services.audit_service import AuditService
from core.errors import NexraError

logger = logging.getLogger("nexra.services.policy_version")


class PolicyVersionService:
    """Policy version control.

    Every policy update creates a new version. Old versions are preserved
    and referenced by audit entries. This enables post-hoc compliance review:
    'What policy was in effect when this delegation happened?'

    Version chain: parent_policy_id links versions together.
    Only the latest version (highest version number) is active.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.audit = AuditService(db)

    async def update_policy(
        self,
        org_id: str,
        policy_id: str,
        updates: dict,
    ) -> Policy:
        """Create a new version of an existing policy.

        Steps:
        1. Fetch current policy
        2. Disable current version (enabled=False)
        3. Create new policy record with incremented version
        4. Set parent_policy_id to original policy's ID
        5. Write audit entry

        Args:
            org_id: Organization UUID
            policy_id: UUID of the policy to update
            updates: Dict of fields to update (name, description, priority,
                     rule_yaml, etc.)

        Returns:
            New Policy record (latest version)

        Raises:
            NexraError(404) if policy not found
        """
        # Fetch current active version
        result = await self.db.execute(
            select(Policy).where(
                Policy.id == policy_id,
                Policy.org_id == org_id,
                Policy.enabled == True,
            )
        )
        current = result.scalar_one_or_none()

        if not current:
            raise NexraError(404, "POLICY_NOT_FOUND", "Policy not found or already disabled")

        # Find the root policy ID (first in the version chain)
        root_id = current.parent_policy_id or current.id

        # Get the highest version number in this chain
        max_version_result = await self.db.execute(
            select(func.max(Policy.version)).where(
                (Policy.id == root_id) | (Policy.parent_policy_id == root_id)
            )
        )
        max_version = max_version_result.scalar() or current.version

        # Disable current version
        current.enabled = False

        # Create new version
        new_policy = Policy(
            org_id=org_id,
            name=updates.get("name", current.name),
            description=updates.get("description", current.description),
            priority=updates.get("priority", current.priority),
            rule_yaml=updates.get("rule_yaml", current.rule_yaml),
            version=max_version + 1,
            parent_policy_id=root_id,
            enabled=True,
        )
        self.db.add(new_policy)
        await self.db.flush()

        await self.audit.append(
            org_id=org_id,
            event_type="policy_updated",
            actor_agent_id=None,
            target_agent_id=None,
            details={
                "policy_id": str(new_policy.id),
                "parent_policy_id": str(root_id),
                "old_version": current.version,
                "new_version": new_policy.version,
                "changes": list(updates.keys()),
            },
        )

        await self.db.commit()
        logger.info(
            f"Policy {current.name} updated: v{current.version} → v{new_policy.version}"
        )
        return new_policy

    async def get_version_history(
        self, org_id: str, policy_id: str
    ) -> list[Policy]:
        """Get full version history for a policy.

        Returns all versions in the chain, ordered by version number descending.
        """
        # Find root policy ID
        result = await self.db.execute(
            select(Policy).where(
                Policy.id == policy_id,
                Policy.org_id == org_id,
            )
        )
        policy = result.scalar_one_or_none()
        if not policy:
            raise NexraError(404, "POLICY_NOT_FOUND", "Policy not found")

        root_id = policy.parent_policy_id or policy.id

        # Fetch all versions in chain
        result = await self.db.execute(
            select(Policy)
            .where(
                Policy.org_id == org_id,
                (Policy.id == root_id) | (Policy.parent_policy_id == root_id),
            )
            .order_by(Policy.version.desc())
        )
        return list(result.scalars().all())

    async def get_policy_at_version(
        self, org_id: str, policy_id: str, version: int
    ) -> Policy | None:
        """Get a specific version of a policy.

        Used for compliance review: 'What policy was in effect at version X?'
        """
        root_id = policy_id  # Assume policy_id is the root

        result = await self.db.execute(
            select(Policy).where(
                Policy.org_id == org_id,
                (Policy.id == root_id) | (Policy.parent_policy_id == root_id),
                Policy.version == version,
            )
        )
        return result.scalar_one_or_none()
```

---

### 5.5 `api/routers/compliance.py` (New File)

**Path**: `nexra/api/routers/compliance.py`

```python
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_org
from services.compliance_service import ComplianceService

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get(
    "/export/soc2",
    summary="Export SOC 2 compliance report",
    description=(
        "Generate a SOC 2 Type II evidence report from the audit log. "
        "Includes access controls, processing integrity, incident response, "
        "and change management sections."
    ),
)
async def export_soc2(
    days: int = Query(90, ge=1, le=365, description="Lookback period in days"),
    format: str = Query("json", pattern="^(json|csv)$"),
    org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceService(db)
    date_to = datetime.now(timezone.utc)
    date_from = date_to - timedelta(days=days)

    report = await service.generate_soc2_report(
        org_id=str(org.id),
        date_from=date_from,
        date_to=date_to,
        output_format=format,
    )

    if format == "csv":
        return PlainTextResponse(
            content=report,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=soc2_report.csv"},
        )
    return report


@router.get(
    "/export/gdpr",
    summary="Export GDPR data access report",
    description=(
        "Generate a GDPR-compliant data access audit trail. "
        "Shows what data each agent accessed, when, and under what policy."
    ),
)
async def export_gdpr(
    days: int = Query(90, ge=1, le=365),
    agent_id: str | None = Query(None, description="Filter by specific agent"),
    format: str = Query("json", pattern="^(json|csv)$"),
    org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceService(db)
    date_to = datetime.now(timezone.utc)
    date_from = date_to - timedelta(days=days)

    report = await service.generate_gdpr_report(
        org_id=str(org.id),
        date_from=date_from,
        date_to=date_to,
        agent_id=agent_id,
        output_format=format,
    )

    if format == "csv":
        return PlainTextResponse(
            content=report,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=gdpr_report.csv"},
        )
    return report


@router.get(
    "/export/hipaa",
    summary="Export HIPAA PHI access report",
    description=(
        "Generate a HIPAA-compliant PHI access log. "
        "Identifies delegations that accessed PHI-related context scopes."
    ),
)
async def export_hipaa(
    days: int = Query(90, ge=1, le=365),
    format: str = Query("json", pattern="^(json|csv)$"),
    org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceService(db)
    date_to = datetime.now(timezone.utc)
    date_from = date_to - timedelta(days=days)

    report = await service.generate_hipaa_report(
        org_id=str(org.id),
        date_from=date_from,
        date_to=date_to,
        output_format=format,
    )

    if format == "csv":
        return PlainTextResponse(
            content=report,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=hipaa_report.csv"},
        )
    return report
```

---

### 5.6 Update `api/routers/policies.py` — Add Version Control Endpoints

**Path**: `nexra/api/routers/policies.py`

Add these endpoints to the existing policies router.

```python
from services.policy_version_service import PolicyVersionService
from pydantic import BaseModel, Field


class PolicyUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    priority: int | None = None
    rule_yaml: str | None = None


class PolicyVersionResponse(BaseModel):
    id: str
    name: str
    version: int
    enabled: bool
    parent_policy_id: str | None
    created_at: str


@router.put(
    "/policies/{policy_id}",
    summary="Update a policy (creates new version)",
    description=(
        "Updates a policy by creating a new version. The old version is "
        "preserved and disabled. Audit entries reference the exact policy_version "
        "that governed them. Enables post-hoc compliance review."
    ),
)
async def update_policy(
    policy_id: str,
    body: PolicyUpdateRequest,
    org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise NexraError(400, "INVALID_REQUEST", "No fields to update")

    service = PolicyVersionService(db)
    new_policy = await service.update_policy(
        org_id=str(org.id),
        policy_id=policy_id,
        updates=updates,
    )

    return {
        "id": str(new_policy.id),
        "name": new_policy.name,
        "version": new_policy.version,
        "parent_policy_id": str(new_policy.parent_policy_id)
        if new_policy.parent_policy_id
        else None,
        "enabled": new_policy.enabled,
        "message": f"Policy updated to version {new_policy.version}",
    }


@router.get(
    "/policies/{policy_id}/versions",
    summary="Get policy version history",
    description="Returns all versions of a policy, ordered by version descending.",
)
async def get_policy_versions(
    policy_id: str,
    org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    service = PolicyVersionService(db)
    versions = await service.get_version_history(
        org_id=str(org.id),
        policy_id=policy_id,
    )

    return {
        "versions": [
            PolicyVersionResponse(
                id=str(v.id),
                name=v.name,
                version=v.version,
                enabled=v.enabled,
                parent_policy_id=str(v.parent_policy_id)
                if v.parent_policy_id
                else None,
                created_at=v.created_at.isoformat() if v.created_at else "",
            )
            for v in versions
        ]
    }
```

---

### 5.7 Update `services/delegation_service.py` — Schema Validation Enforcement

Add schema validation as a default step in the delegation flow. This replaces the optional validation from Phase 6 with mandatory validation.

```python
import jsonschema
from core.errors import NexraError


async def _validate_schemas(
    self,
    delegation: Delegation,
    callee: Agent,
    org: Organization,
) -> None:
    """Validate task payload against callee's input_schema.

    Called as part of the delegation flow (step 3).
    Skippable per-org via schema_validation_enabled flag.

    Raises:
        NexraError(422, 'SCHEMA_VALIDATION_FAILED') on validation failure
    """
    if not getattr(org, "schema_validation_enabled", True):
        return

    # Skip validation for passthrough schemas (A2A agents)
    if callee.input_schema == {"type": "object"}:
        return

    try:
        jsonschema.validate(
            instance=delegation.task.get("input", delegation.task),
            schema=callee.input_schema,
        )
    except jsonschema.ValidationError as e:
        raise NexraError(
            422,
            "SCHEMA_VALIDATION_FAILED",
            f"Task payload does not match callee's input_schema: {e.message}",
            details={
                "schema_path": list(e.absolute_schema_path),
                "validator": e.validator,
                "validator_value": str(e.validator_value),
            },
        )


async def _validate_output_schema(
    self,
    result: dict,
    callee: Agent,
    org: Organization,
) -> None:
    """Validate callee's result against registered output_schema.

    Called after receiving callee's response (step 11).

    Raises:
        NexraError(422, 'OUTPUT_SCHEMA_FAILED') on validation failure
    """
    if not getattr(org, "schema_validation_enabled", True):
        return

    if callee.output_schema == {"type": "object"}:
        return

    try:
        jsonschema.validate(instance=result, schema=callee.output_schema)
    except jsonschema.ValidationError as e:
        raise NexraError(
            422,
            "OUTPUT_SCHEMA_FAILED",
            f"Callee result does not match output_schema: {e.message}",
            details={
                "schema_path": list(e.absolute_schema_path),
                "validator": e.validator,
            },
        )
```

---

### 5.8 Update Discovery Service — Cross-Org Marketplace

Update `services/discovery_service.py` to include public agents from other orgs when `include_cross_org=True`.

```python
# In the discovery query builder, update the org filter:

if include_cross_org:
    # Include same-org agents AND public agents from other orgs
    filters.append(
        (Agent.org_id == org_id) | (Agent.is_public == True)
    )
else:
    # Same-org only (default)
    filters.append(Agent.org_id == org_id)

# In the response, flag cross-org matches:
for match in matches:
    match["is_cross_org"] = str(match["org_id"]) != str(org_id)
```

---

## 6. Integration Points

### 6.1 Delegation Flow — Cross-Org Settlement

After a cross-org delegation completes (callee_org_id != caller_org_id), trigger marketplace settlement:

```python
# In delegation_service.py, inside _settle_delegation():
if delegation.callee_org_id and delegation.callee_org_id != delegation.caller_org_id:
    callee_org = await self._get_org(delegation.callee_org_id)
    marketplace = MarketplaceService(self.db)
    await marketplace.settle_cross_org_delegation(
        delegation=delegation,
        callee_org=callee_org,
        actual_cost_usd=delegation.actual_cost_usd,
    )
```

### 6.2 Router Registration

Register new routers in `api/main.py`:

```python
from api.routers import compliance, siem

app.include_router(compliance.router, prefix="/v1")
app.include_router(siem.router, prefix="/v1")
```

---

## 7. Guardrails

1. **DO NOT** allow cross-org discovery without explicit `include_cross_org=true`. Default is org-scoped only.
2. **DO NOT** transfer funds to Stripe Connect accounts that have not completed KYC. Queue in `pending_payouts` instead.
3. **DO NOT** allow the platform fee percentage to be configurable per-org in P2. Hardcode at 20%. Per-org pricing is a v3 feature.
4. **DO NOT** include `api_key_hash`, `jwt_secret_enc`, or `webhook_secret` in any compliance report. These are security-sensitive fields.
5. **DO NOT** allow compliance reports to span more than 365 days in a single request. Large reports should be paginated or generated async.
6. **DO NOT** disable schema validation globally. The toggle is per-org only.
7. **DO NOT** delete old policy versions. They are referenced by audit entries and must be preserved for compliance.
8. **DO NOT** allow policy version rollback by re-enabling an old version. Create a new version with the old content instead.
9. **DO NOT** expose the `pending_payouts` table directly via API. It's internal bookkeeping for the marketplace service.

---

## 8. Verification Checklist

### Cross-Org Marketplace
- [ ] `is_public=true` agents appear in discovery with `include_cross_org=true`
- [ ] `is_public=true` agents do NOT appear without `include_cross_org=true`
- [ ] Cross-org delegation triggers Stripe Connect transfer (80% to callee)
- [ ] Callee without Stripe Connect → payout queued in `pending_payouts`
- [ ] `process_pending_payouts()` transfers all pending amounts after onboarding
- [ ] Platform fee (20%) retained in Nexra Stripe balance
- [ ] `marketplace_payout` audit entry written for each settlement

### Compliance Reports
- [ ] SOC 2 report contains access_controls, processing_integrity, incident_response, change_management sections
- [ ] GDPR report shows data access per agent with context_scope
- [ ] HIPAA report identifies PHI-related context scopes
- [ ] All reports support JSON and CSV output formats
- [ ] CSV export has correct headers and escaped values
- [ ] Reports are org-scoped (no cross-org data leakage)
- [ ] Reports handle empty data gracefully

### Schema Validation
- [ ] Schema validation enabled by default for new orgs
- [ ] Invalid task payload → 422 with `SCHEMA_VALIDATION_FAILED`
- [ ] Invalid callee result → 422 with `OUTPUT_SCHEMA_FAILED`
- [ ] Passthrough schemas (`type: object`) skip validation
- [ ] Per-org toggle disables validation when `schema_validation_enabled=false`

### Policy Version Control
- [ ] `PUT /policies/{id}` creates new version, disables old
- [ ] Version number auto-increments
- [ ] `parent_policy_id` links to root policy
- [ ] `GET /policies/{id}/versions` returns full history
- [ ] Audit entries reference correct `policy_version`
- [ ] Old versions are preserved (never deleted)

---

## 9. Test Cases

| Test ID | Category | Description | Assertion |
|---------|----------|-------------|-----------|
| T-MKT-001 | Marketplace | Public agent visible in cross-org discovery | Agent in matches with `is_cross_org=true` |
| T-MKT-002 | Marketplace | Public agent NOT visible without `include_cross_org` | Agent not in matches |
| T-MKT-003 | Marketplace | Cross-org settlement → 80% to callee | Stripe Transfer amount = 80% of cost |
| T-MKT-004 | Marketplace | Callee without Connect → pending payout | `pending_payouts` row created |
| T-MKT-005 | Marketplace | Process pending payouts after onboarding | All pending rows → status='paid' |
| T-MKT-006 | Marketplace | Stripe error → payout queued as pending | Graceful fallback to pending_payouts |
| T-COMP-001 | Compliance | SOC 2 report has all required sections | 4 sections present in report |
| T-COMP-002 | Compliance | GDPR report shows context_scope per delegation | `data_accessed` field populated |
| T-COMP-003 | Compliance | HIPAA report identifies PHI scopes | Only PHI-prefixed scopes in `phi_data_accessed` |
| T-COMP-004 | Compliance | CSV export has correct format | Parseable CSV with headers |
| T-COMP-005 | Compliance | Report org isolation | No cross-org data in report |
| T-COMP-006 | Compliance | Empty audit log → empty report (no error) | Report with `total_events: 0` |
| T-SCHEMA-001 | Schema | Valid payload passes validation | No error raised |
| T-SCHEMA-002 | Schema | Invalid payload → 422 | `SCHEMA_VALIDATION_FAILED` error |
| T-SCHEMA-003 | Schema | Passthrough schema skips validation | No validation performed |
| T-SCHEMA-004 | Schema | Per-org disable skips validation | No validation performed |
| T-SCHEMA-005 | Schema | Invalid output → 422 | `OUTPUT_SCHEMA_FAILED` error |
| T-POLV-001 | Policy Version | Update creates new version | `new_policy.version == old_version + 1` |
| T-POLV-002 | Policy Version | Old version disabled | `old_policy.enabled == False` |
| T-POLV-003 | Policy Version | Version history returns all versions | All versions in chain returned |
| T-POLV-004 | Policy Version | Audit entry references correct version | `details.new_version` matches |
| T-POLV-005 | Policy Version | Nonexistent policy → 404 | `NexraError(404)` raised |
