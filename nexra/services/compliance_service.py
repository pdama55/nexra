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
            report["controls"] = {
                "CC6.1_logical_access": "API key authentication with bcrypt hashing",
                "CC6.3_role_based_access": "Organization-scoped access with agent identity verification",
                "CC7.2_monitoring": f"Continuous audit logging ({len(entries)} events in period)",
                "CC8.1_change_management": "Policy versioning with immutable audit trail",
            }
        elif report_type == "gdpr":
            report["data_processing"] = {
                "lawful_basis": "Legitimate interest (agent coordination)",
                "data_minimization": "Only task payloads and metadata stored",
                "retention": "Audit logs retained indefinitely (immutable)",
                "cross_border": "Data processed in deployment region",
            }
        elif report_type == "hipaa":
            report["safeguards"] = {
                "access_control": "API key + agent identity verification",
                "audit_controls": f"Immutable audit log with {len(entries)} entries",
                "integrity": "HMAC-SHA256 webhook signing, SHA-256 task hashing",
                "transmission_security": "HTTPS-only webhook delivery",
            }

        return report
