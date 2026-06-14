"""Risk analysis API endpoints."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.error_handler import NotFoundError
from app.api.schemas.risks import (
    AnalysisResultResponse,
    AnomalyResponse,
    ChecklistItemResponse,
    MissingClauseResponse,
    RiskItemResponse,
)
from app.db.session import get_db
from app.services.risk_service import (
    DocumentNotFoundError,
    RiskService,
)

router = APIRouter(prefix="/documents", tags=["risks"])


async def _get_risk_service() -> RiskService:
    """Dependency that provides a RiskService instance."""
    return RiskService()


@router.post("/{document_id}/analyze", response_model=AnalysisResultResponse)
async def analyze_document(
    document_id: uuid.UUID,
    service: RiskService = Depends(_get_risk_service),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> AnalysisResultResponse:
    """Run full risk analysis on a document.

    Executes the detection pipeline (risks, missing clauses, anomalies),
    generates a checklist, and persists risk items.
    """
    try:
        result = await service.analyze(str(document_id), db)
        await db.commit()
    except DocumentNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc

    return AnalysisResultResponse(
        document_id=result.document_id,
        risk_count=result.risk_count,
        critical_count=result.critical_count,
        high_count=result.high_count,
        medium_count=result.medium_count,
        low_count=result.low_count,
        risks=[
            RiskItemResponse(
                id=uuid.uuid4(),
                category=r.category,
                severity=r.severity,
                title=r.title,
                description=r.description,
                evidence=r.evidence,
                page_number=r.page_number,
                status="open",
                detected_by="rule_engine",
            )
            for r in result.risks
        ],
        missing_clauses=[
            MissingClauseResponse(
                clause_name=mc.clause_name,
                description=mc.description,
                severity=mc.severity,
                suggestion=mc.suggestion,
            )
            for mc in result.missing_clauses
        ],
        anomalies=[
            AnomalyResponse(
                field_name=a.field_name,
                value=a.value,
                expected_range=a.expected_range,
                deviation=a.deviation,
                severity=a.severity,
            )
            for a in result.anomalies
        ],
        checklist=[
            ChecklistItemResponse(
                description=c.description,
                severity=c.severity,
                category=c.category,
                suggested_action=c.suggested_action,
                due_days=c.due_days,
            )
            for c in result.checklist
        ],
    )


@router.get("/{document_id}/risks", response_model=list[RiskItemResponse])
async def get_risks(
    document_id: uuid.UUID,
    service: RiskService = Depends(_get_risk_service),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[RiskItemResponse]:
    """Retrieve persisted risk items for a document."""
    try:
        rows = await service.get_risks(str(document_id), db)
    except DocumentNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc

    return [RiskItemResponse(**row) for row in rows]


@router.get("/{document_id}/checklist", response_model=list[ChecklistItemResponse])
async def get_checklist(
    document_id: uuid.UUID,
    service: RiskService = Depends(_get_risk_service),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[ChecklistItemResponse]:
    """Retrieve the generated checklist for a document."""
    try:
        rows = await service.get_checklist(str(document_id), db)
    except DocumentNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc

    return [ChecklistItemResponse(**row) for row in rows]
