import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from services.audit_service import AuditService

logger = logging.getLogger("nexra.services.compliance")


class ComplianceService:
    """Compliance report generation for SOC 2, GDPR, HIPAA."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

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
