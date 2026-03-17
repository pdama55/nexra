import logging
import csv
import io
import json
import zipfile
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.agent import Agent
from models.delegation import Delegation
from models.policy import Policy
from services.audit_service import AuditService

logger = logging.getLogger("nexra.services.compliance")


class ComplianceService:
    """Compliance report generation for SOC 2, GDPR, HIPAA."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _csv_from_rows(headers: list[str], rows: list[dict[str, object]]) -> str:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in headers})
        return output.getvalue()

    async def generate_report(
        self,
        org_id: str,
        report_type: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict:
        audit = AuditService(self.db)
        entries, _ = await audit.query(
            org_id, date_from=date_from, date_to=date_to, limit=10000
        )

        total_delegations = sum(1 for e in entries if e.event_type == "delegation_completed")
        total_blocked = sum(1 for e in entries if e.event_type == "delegation_blocked")
        anomalies = sum(1 for e in entries if e.event_type == "anomaly_detected")

        report = {
            "report_type": report_type,
            "org_id": org_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period": {
                "from": date_from.isoformat() if date_from else None,
                "to": date_to.isoformat() if date_to else None,
            },
            "summary": {
                "total_audit_entries": len(entries),
                "total_delegations_completed": total_delegations,
                "total_delegations_blocked": total_blocked,
                "anomalies_detected": anomalies,
            },
        }

        if report_type == "soc2":
            report["access_controls"] = {
                "authentication": "API key + agent identity verification",
                "org_scoping": "All queries are org-scoped by auth dependency",
                "evidence_count": len(entries),
            }
            report["processing_integrity"] = {
                "delegations_completed": total_delegations,
                "delegations_blocked": total_blocked,
                "anomaly_events": anomalies,
            }
            report["incident_response"] = {
                "failed_or_timeout_events": sum(
                    1 for e in entries if e.event_type in ("delegation_failed", "delegation_timeout")
                ),
                "quarantine_events": sum(
                    1 for e in entries if e.event_type == "agent_quarantined"
                ),
            }
            report["change_management"] = {
                "policy_evaluations": sum(
                    1 for e in entries if e.event_type == "policy_evaluated"
                ),
                "versioned_policy_references": sum(
                    1
                    for e in entries
                    if e.details.get("policy_version") is not None
                ),
            }
        elif report_type == "gdpr":
            by_agent: dict[str, dict[str, object]] = {}
            for e in entries:
                actor = e.actor_agent_id or "system"
                item = by_agent.setdefault(
                    actor,
                    {
                        "event_count": 0,
                        "context_scopes": set(),
                        "last_accessed_at": None,
                    },
                )
                item["event_count"] = int(item["event_count"]) + 1
                detail_scope = e.details.get("context_scope")
                if isinstance(detail_scope, list):
                    cast_scope = item["context_scopes"]
                    for scope in detail_scope:
                        if isinstance(scope, str):
                            cast_scope.add(scope)
                item["last_accessed_at"] = e.created_at.isoformat()
            report["data_access"] = [
                {
                    "agent_id": agent_id,
                    "event_count": payload["event_count"],
                    "context_scope": sorted(payload["context_scopes"]),
                    "last_accessed_at": payload["last_accessed_at"],
                }
                for agent_id, payload in by_agent.items()
            ]
            report["data_processing"] = {
                "lawful_basis": "Legitimate interest (agent coordination)",
                "retention": "Audit logs retained as immutable evidence",
            }
        elif report_type == "hipaa":
            phi_scopes = {"phi", "medical_records", "patient_data", "diagnosis", "treatment"}
            phi_related_events = []
            for e in entries:
                detail_scope = e.details.get("context_scope")
                if not isinstance(detail_scope, list):
                    continue
                scopes = [s for s in detail_scope if isinstance(s, str)]
                if any(scope in phi_scopes for scope in scopes):
                    phi_related_events.append(
                        {
                            "event_id": str(e.id),
                            "agent_id": e.actor_agent_id,
                            "context_scope": scopes,
                            "created_at": e.created_at.isoformat(),
                        }
                    )
            report["phi_access"] = phi_related_events
            report["safeguards"] = {
                "access_control": "API key + agent identity verification",
                "audit_controls": f"Immutable audit log with {len(entries)} entries",
                "integrity": "HMAC-SHA256 webhook signing, SHA-256 task hashing",
                "transmission_security": "HTTPS-only webhook delivery",
            }

        return report

    async def generate_soc2_core_package(
        self,
        org_id: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> bytes:
        org_uuid = uuid.UUID(org_id)
        audit = AuditService(self.db)
        entries, _ = await audit.query(
            org_id,
            date_from=date_from,
            date_to=date_to,
            limit=10000,
        )

        audit_rows = [
            {
                "id": str(entry.id),
                "delegation_id": str(entry.delegation_id) if entry.delegation_id else "",
                "event_type": entry.event_type,
                "actor": entry.actor_agent_id or "",
                "target": entry.target_agent_id or "",
                "cost_usd": float(entry.cost_usd) if isinstance(entry.cost_usd, Decimal) else (entry.cost_usd or 0),
                "created_at": entry.created_at.isoformat(),
                "details": json.dumps(entry.details, sort_keys=True),
            }
            for entry in entries
        ]
        audit_csv = self._csv_from_rows(
            ["id", "delegation_id", "event_type", "actor", "target", "cost_usd", "created_at", "details"],
            audit_rows,
        )

        policy_rows: dict[str, dict[str, object]] = {}
        for entry in entries:
            details = entry.details if isinstance(entry.details, dict) else {}
            policy_id = str(details.get("policy_id") or "")
            if not policy_id:
                continue
            row = policy_rows.setdefault(
                policy_id,
                {
                    "policy_id": policy_id,
                    "evaluations": 0,
                    "allow_count": 0,
                    "block_count": 0,
                    "pause_count": 0,
                    "last_seen_at": "",
                },
            )
            row["evaluations"] = int(row["evaluations"]) + (1 if entry.event_type == "policy_evaluated" else 0)
            decision = str(details.get("policy_decision") or details.get("decision") or "").lower()
            if decision == "allow":
                row["allow_count"] = int(row["allow_count"]) + 1
            elif decision == "block":
                row["block_count"] = int(row["block_count"]) + 1
            elif decision == "pause":
                row["pause_count"] = int(row["pause_count"]) + 1
            row["last_seen_at"] = entry.created_at.isoformat()

        policy_meta_result = await self.db.execute(select(Policy).where(Policy.org_id == org_uuid))
        for policy in policy_meta_result.scalars().all():
            pid = str(policy.id)
            row = policy_rows.setdefault(
                pid,
                {
                    "policy_id": pid,
                    "evaluations": 0,
                    "allow_count": 0,
                    "block_count": 0,
                    "pause_count": 0,
                    "last_seen_at": "",
                },
            )
            row["policy_name"] = policy.name
            row["policy_version"] = policy.version
            row["enabled"] = policy.enabled
        policy_coverage_csv = self._csv_from_rows(
            [
                "policy_id",
                "policy_name",
                "policy_version",
                "enabled",
                "evaluations",
                "allow_count",
                "block_count",
                "pause_count",
                "last_seen_at",
            ],
            sorted(policy_rows.values(), key=lambda item: str(item.get("policy_id", ""))),
        )

        delegation_query = (
            select(Delegation, Agent.team)
            .select_from(Delegation)
            .outerjoin(
                Agent,
                and_(
                    Agent.org_id == Delegation.caller_org_id,
                    Agent.agent_id == Delegation.caller_agent_id,
                ),
            )
            .where(Delegation.caller_org_id == org_uuid, Delegation.status == "completed")
            .order_by(Delegation.created_at.asc())
        )
        if date_from:
            delegation_query = delegation_query.where(Delegation.created_at >= date_from)
        if date_to:
            delegation_query = delegation_query.where(Delegation.created_at <= date_to)
        delegation_result = await self.db.execute(delegation_query)
        spend_rows = []
        for delegation, team in delegation_result.fetchall():
            spend_rows.append(
                {
                    "delegation_id": str(delegation.id),
                    "caller_agent_id": delegation.caller_agent_id,
                    "callee_agent_id": delegation.callee_agent_id,
                    "team": team or "unassigned",
                    "workflow": delegation.workflow or "unclassified",
                    "policy_decision": delegation.policy_decision or "",
                    "actual_cost_usd": float(delegation.actual_cost_usd or 0),
                    "created_at": delegation.created_at.isoformat(),
                    "completed_at": delegation.completed_at.isoformat() if delegation.completed_at else "",
                }
            )
        spend_governance_csv = self._csv_from_rows(
            [
                "delegation_id",
                "caller_agent_id",
                "callee_agent_id",
                "team",
                "workflow",
                "policy_decision",
                "actual_cost_usd",
                "created_at",
                "completed_at",
            ],
            spend_rows,
        )

        status_rows = []
        for entry in entries:
            if entry.event_type not in {"agent_quarantined", "agent_activated"}:
                continue
            status_rows.append(
                {
                    "event_id": str(entry.id),
                    "agent_id": entry.target_agent_id or "",
                    "status": "quarantined" if entry.event_type == "agent_quarantined" else "active",
                    "actor": entry.actor_agent_id or "",
                    "reason": str((entry.details or {}).get("reason") or ""),
                    "trigger": str((entry.details or {}).get("trigger") or ""),
                    "created_at": entry.created_at.isoformat(),
                }
            )
        agent_status_history_csv = self._csv_from_rows(
            ["event_id", "agent_id", "status", "actor", "reason", "trigger", "created_at"],
            status_rows,
        )

        hitl_rows = []
        for entry in entries:
            details = entry.details if isinstance(entry.details, dict) else {}
            is_hitl = (
                entry.event_type in {"hil_triggered", "hil_approved", "hil_expired"}
                or (entry.event_type == "delegation_blocked" and details.get("trigger") == "hil_rejected")
            )
            if not is_hitl:
                continue
            if entry.event_type == "hil_triggered":
                outcome = "triggered"
            elif entry.event_type == "hil_approved":
                outcome = "approved"
            elif entry.event_type == "hil_expired":
                outcome = "expired"
            else:
                outcome = "rejected"
            hitl_rows.append(
                {
                    "event_id": str(entry.id),
                    "delegation_id": str(entry.delegation_id) if entry.delegation_id else "",
                    "trigger": str(details.get("trigger") or "policy_pause"),
                    "approver_or_rejector": str(
                        details.get("approver_email")
                        or details.get("rejector_email")
                        or entry.actor_agent_id
                        or ""
                    ),
                    "role": str(details.get("approver_role") or details.get("rejector_role") or ""),
                    "deadline": str(details.get("approval_deadline") or ""),
                    "outcome": outcome,
                    "reason": str(details.get("reason") or ""),
                    "created_at": entry.created_at.isoformat(),
                }
            )
        hitl_decision_log_csv = self._csv_from_rows(
            [
                "event_id",
                "delegation_id",
                "trigger",
                "approver_or_rejector",
                "role",
                "deadline",
                "outcome",
                "reason",
                "created_at",
            ],
            hitl_rows,
        )

        manifest = {
            "schema_version": "2026-03-17.soc2_core.v1",
            "set": "soc2_core",
            "org_id": org_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "files": [
                "audit_log.csv",
                "policy_coverage.csv",
                "spend_governance.csv",
                "agent_status_history.csv",
                "hitl_decision_log.csv",
            ],
            "counts": {
                "audit_rows": len(audit_rows),
                "policy_rows": len(policy_rows),
                "spend_rows": len(spend_rows),
                "agent_status_rows": len(status_rows),
                "hitl_rows": len(hitl_rows),
            },
        }

        output = io.BytesIO()
        with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("audit_log.csv", audit_csv)
            zf.writestr("policy_coverage.csv", policy_coverage_csv)
            zf.writestr("spend_governance.csv", spend_governance_csv)
            zf.writestr("agent_status_history.csv", agent_status_history_csv)
            zf.writestr("hitl_decision_log.csv", hitl_decision_log_csv)
            zf.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))

        output.seek(0)
        return output.getvalue()
