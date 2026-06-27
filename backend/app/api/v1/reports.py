"""Report generation and export API endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.error_handler import NotFoundError, ForbiddenError, ValidationErrorDetail
from app.api.schemas.reports import (
    ExportFormat,
    ReportCreateRequest,
    ReportDownloadResponse,
    ReportResponse,
    ReportType,
)
from app.auth.dependencies import get_current_user_id
from app.db.session import get_db
from app.services.report_generator import (
    DocumentNotFoundError as ReportDocNotFoundError,
    InvalidReportTypeError,
    ReportGenerator,
)
from app.services.report_service import (
    InvalidExportFormatError,
    ReportNotFoundError,
    ReportService,
)

router = APIRouter(prefix="/reports", tags=["reports"])


async def _get_report_service() -> ReportService:
    """Dependency that provides a ReportService instance."""
    return ReportService()


@router.post(
    "/documents/{document_id}/report",
    response_model=ReportResponse,
    status_code=201,
)
async def generate_report(
    document_id: uuid.UUID,
    body: ReportCreateRequest | None = None,
    service: ReportService = Depends(_get_report_service),  # noqa: B008
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ReportResponse:
    """Generate a report for a document.

    Supported report types: ``summary``, ``detailed``, ``risk_assessment``.
    """
    report_type = (body.report_type if body else None) or "summary"

    if report_type not in set(ReportType):
        raise ValidationErrorDetail(
            f"Invalid report type {report_type!r}. "
            f"Choose from: {', '.join(t.value for t in ReportType)}"
        )

    try:
        report = await service.create_report(
            document_id=str(document_id),
            report_type=report_type,
            user_id=user_id,
            db=db,
        )
        await db.commit()
        await db.refresh(report)
    except ReportDocNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    except InvalidReportTypeError as exc:
        raise ValidationErrorDetail(str(exc)) from exc

    return ReportResponse.model_validate(report)


@router.get("/")
async def list_reports(
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    """List all reports for the current user."""
    from sqlalchemy import select
    from app.db.models.report import Report

    result = await db.execute(
        select(Report)
        .where(Report.user_id == user_id)
        .order_by(Report.created_at.desc())
        .limit(50)
    )
    reports = result.scalars().all()
    return {
        "items": [
            {
                "id": str(r.id),
                "document_id": str(r.document_id) if r.document_id else None,
                "report_type": r.report_type,
                "title": r.title,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reports
        ],
        "total": len(reports),
    }


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    service: ReportService = Depends(_get_report_service),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ReportResponse:
    """Retrieve report metadata by ID (must own the report)."""
    from app.db.models.report import Report
    from sqlalchemy import select

    result = await db.execute(
        select(Report).where(Report.id == report_id, Report.user_id == user_id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise NotFoundError(f"Report {report_id} not found")

    return ReportResponse.model_validate(report)


@router.get("/{report_id}/download")
async def download_report(
    report_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    format: str = Query(default="markdown", description="Export format: markdown or pdf"),  # noqa: A002
    service: ReportService = Depends(_get_report_service),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Response:
    """Download a report in the specified format (must own the report).

    Supported formats: ``markdown``, ``pdf``.
    Returns the file content directly with appropriate Content-Type and
    Content-Disposition headers.
    """
    from app.db.models.report import Report
    from sqlalchemy import select

    result = await db.execute(
        select(Report).where(Report.id == report_id, Report.user_id == user_id)
    )
    if result.scalar_one_or_none() is None:
        raise NotFoundError(f"Report {report_id} not found")

    if format not in set(ExportFormat):
        raise ValidationErrorDetail(
            f"Invalid export format {format!r}. Choose from: markdown, pdf"
        )

    try:
        file_bytes, content_type, filename = await service.export_report(
            report_id=str(report_id),
            export_format=format,
            db=db,
        )
    except ReportNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    except InvalidExportFormatError as exc:
        raise ValidationErrorDetail(str(exc)) from exc

    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
