"""Orchestration service for risk analysis pipeline."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.db.models.document import Document
from app.db.models.extraction import ExtractedField
from app.db.models.risk import RiskItem as RiskItemORM
from app.services.anomaly_detector import Anomaly, AnomalyDetector
from app.services.checklist_generator import ChecklistGenerator, ChecklistItem
from app.services.clause_detector import ClauseDetector, MissingClause
from app.services.risk_detector import RiskDetector, RiskItem

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Full result of a risk analysis pipeline run."""

    document_id: str
    risks: list[RiskItem]
    missing_clauses: list[MissingClause]
    anomalies: list[Anomaly]
    checklist: list[ChecklistItem]
    risk_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0

    def __post_init__(self) -> None:
        self.risk_count = len(self.risks)
        for r in self.risks:
            if r.severity == "critical":
                self.critical_count += 1
            elif r.severity == "high":
                self.high_count += 1
            elif r.severity == "medium":
                self.medium_count += 1
            elif r.severity in ("low", "info"):
                self.low_count += 1


class RiskServiceError(Exception):
    """Base exception for risk service operations."""


class DocumentNotFoundError(RiskServiceError):
    """Raised when a document cannot be located."""


class RiskService:
    """Coordinates the full risk analysis pipeline.

    Pipeline: load document → detect risks → detect missing clauses →
    detect anomalies → generate checklist → persist results.
    """

    def __init__(
        self,
        risk_detector: RiskDetector | None = None,
        clause_detector: ClauseDetector | None = None,
        anomaly_detector: AnomalyDetector | None = None,
        checklist_generator: ChecklistGenerator | None = None,
    ) -> None:
        self._risk_detector = risk_detector or RiskDetector()
        self._clause_detector = clause_detector or ClauseDetector()
        self._anomaly_detector = anomaly_detector or AnomalyDetector()
        self._checklist_generator = checklist_generator or ChecklistGenerator()

    async def analyze(
        self,
        document_id: str,
        db: AsyncSession,
    ) -> AnalysisResult:
        """Execute the full risk analysis pipeline for a document.

        Args:
            document_id: UUID string of the target document.
            db: Active async database session.

        Returns:
            ``AnalysisResult`` with all detected items.

        Raises:
            DocumentNotFoundError: If the document does not exist.
        """
        doc_uuid = self._parse_uuid(document_id)
        document = await self._get_document(doc_uuid, db)

        doc_type = document.document_type or "contract"

        pages = await self._get_document_pages(doc_uuid, db)
        text = self._concatenate_pages(pages)

        extracted_fields = await self._get_extracted_fields(doc_uuid, db)
        field_dicts = [self._field_to_dict(f) for f in extracted_fields]

        risks = self._risk_detector.detect(text, doc_type, field_dicts or None)
        missing = self._clause_detector.detect_missing(text, doc_type)
        anomalies = self._anomaly_detector.detect(field_dicts, doc_type)
        checklist = self._checklist_generator.generate(risks, missing, anomalies)

        await self._persist_risks(doc_uuid, risks, db)

        logger.info(
            "Risk analysis completed for document %s: %d risks, %d missing clauses, %d anomalies",
            document_id,
            len(risks),
            len(missing),
            len(anomalies),
        )

        return AnalysisResult(
            document_id=document_id,
            risks=risks,
            missing_clauses=missing,
            anomalies=anomalies,
            checklist=checklist,
        )

    async def get_risks(
        self,
        document_id: str,
        db: AsyncSession,
    ) -> list[dict]:
        """Retrieve persisted risk items for a document.

        Args:
            document_id: UUID string of the document.
            db: Active async database session.

        Returns:
            List of risk item dicts.
        """
        doc_uuid = self._parse_uuid(document_id)
        await self._assert_document_exists(doc_uuid, db)

        stmt = (
            select(RiskItemORM)
            .where(
                RiskItemORM.document_id == doc_uuid,
                RiskItemORM.deleted_at.is_(None),
            )
            .order_by(RiskItemORM.created_at.desc())
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "id": str(row.id),
                "category": row.category,
                "severity": row.severity,
                "title": row.title,
                "description": row.description,
                "evidence": row.evidence,
                "page_number": row.page_number,
                "status": row.status,
                "resolution": row.resolution,
                "detected_by": row.detected_by,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]

    async def get_checklist(
        self,
        document_id: str,
        db: AsyncSession,
    ) -> list[dict]:
        """Retrieve checklist by re-running analysis (stateless).

        Persists risks and returns the generated checklist.
        If risks already exist, re-derives checklist from persisted data.

        Args:
            document_id: UUID string of the document.
            db: Active async database session.

        Returns:
            List of checklist item dicts.
        """
        doc_uuid = self._parse_uuid(document_id)
        document = await self._get_document(doc_uuid, db)

        doc_type = document.document_type or "contract"

        pages = await self._get_document_pages(doc_uuid, db)
        text = self._concatenate_pages(pages)

        extracted_fields = await self._get_extracted_fields(doc_uuid, db)
        field_dicts = [self._field_to_dict(f) for f in extracted_fields]

        risks = self._risk_detector.detect(text, doc_type, field_dicts or None)
        missing = self._clause_detector.detect_missing(text, doc_type)
        anomalies = self._anomaly_detector.detect(field_dicts, doc_type)
        checklist = self._checklist_generator.generate(risks, missing, anomalies)

        return [
            {
                "description": item.description,
                "severity": item.severity,
                "category": item.category,
                "suggested_action": item.suggested_action,
                "due_days": item.due_days,
            }
            for item in checklist
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_uuid(document_id: str) -> uuid.UUID:
        try:
            return uuid.UUID(document_id)
        except ValueError as exc:
            raise DocumentNotFoundError(f"Invalid document ID: {document_id}") from exc

    @staticmethod
    async def _get_document(doc_uuid: uuid.UUID, db: AsyncSession) -> Document:
        stmt = select(Document).where(
            Document.id == doc_uuid,
            Document.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        document = result.scalar_one_or_none()
        if document is None:
            raise DocumentNotFoundError(f"Document {doc_uuid} not found.")
        return document

    @staticmethod
    async def _assert_document_exists(doc_uuid: uuid.UUID, db: AsyncSession) -> None:
        stmt = select(Document.id).where(
            Document.id == doc_uuid,
            Document.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise DocumentNotFoundError(f"Document {doc_uuid} not found.")

    @staticmethod
    async def _get_document_pages(doc_uuid: uuid.UUID, db: AsyncSession) -> list:
        from app.db.models.document_page import DocumentPage

        stmt = (
            select(DocumentPage)
            .where(DocumentPage.document_id == doc_uuid)
            .order_by(DocumentPage.page_number)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _concatenate_pages(pages: list) -> str:
        parts: list[str] = []
        for page in pages:
            text = getattr(page, "ocr_text", None) or getattr(page, "text_content", None) or ""
            if text:
                parts.append(text)
        return "\n\f\n".join(parts) if parts else ""

    @staticmethod
    async def _get_extracted_fields(doc_uuid: uuid.UUID, db: AsyncSession) -> list:
        stmt = (
            select(ExtractedField)
            .where(ExtractedField.document_id == doc_uuid)
            .order_by(ExtractedField.field_name)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _field_to_dict(field: ExtractedField) -> dict:
        return {
            "field_name": field.field_name,
            "field_value": field.field_value,
            "raw_text": field.raw_text,
            "confidence": field.confidence,
            "page_number": field.page_number,
        }

    @staticmethod
    async def _persist_risks(
        doc_uuid: uuid.UUID,
        risks: list[RiskItem],
        db: AsyncSession,
    ) -> None:
        for risk in risks:
            orm = RiskItemORM(
                document_id=doc_uuid,
                category=risk.category,
                severity=risk.severity,
                title=risk.title,
                description=risk.description,
                evidence=risk.evidence,
                page_number=risk.page_number,
                status="open",
                detected_by="rule_engine",
            )
            db.add(orm)

        await db.flush()
        logger.info("Persisted %d risk items for document %s", len(risks), doc_uuid)
