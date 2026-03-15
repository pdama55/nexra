from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_authenticated_org
from core.errors import NexraError, INVALID_REQUEST
from db.session import get_db
from models.organization import Organization
from services.audit_service import AuditService
from services.compliance_service import ComplianceService

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/report/{report_type}")
async def generate_compliance_report(
    request: Request,
    report_type: str,
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Generate a compliance report (soc2, gdpr, hipaa)."""
    if report_type not in ("soc2", "gdpr", "hipaa"):
        raise NexraError(400, INVALID_REQUEST, "report_type must be soc2, gdpr, or hipaa")

    service = ComplianceService(db)
    report = await service.generate_report(str(org.id), report_type, date_from, date_to)
    return {"data": report}


@router.get("/export/csv")
async def export_audit_csv(
    request: Request,
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Export full audit log as CSV for compliance."""
    service = AuditService(db)
    csv_data = await service.export_csv(str(org.id), date_from, date_to)
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=compliance_audit.csv"},
    )
