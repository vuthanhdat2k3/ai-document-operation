"""Report generation service that assembles document data into structured reports."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document
from app.db.models.extraction import ExtractedField
from app.db.models.report import Report
from app.db.models.risk import RiskItem

logger = logging.getLogger(__name__)


class ReportGeneratorError(Exception):
    """Base exception for report generation."""


class DocumentNotFoundError(ReportGeneratorError):
    """Raised when the source document is not found."""


class InvalidReportTypeError(ReportGeneratorError):
    """Raised when an unsupported report type is requested."""


VALID_REPORT_TYPES = {"summary", "detailed", "risk_assessment"}


class ReportGenerator:
    """Generates structured reports from document data.

    Queries the document, its extracted fields, and risk items, then assembles
    the data into a structured content dict stored on the Report model.
    """

    async def generate(
        self,
        document_id: str,
        report_type: str,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> Report:
        """Generate a report for the given document.

        Args:
            document_id: UUID string of the source document.
            report_type: One of ``summary``, ``detailed``, ``risk_assessment``.
            user_id: UUID of the requesting user.
            db: Active async database session.

        Returns:
            The persisted ``Report`` ORM instance.

        Raises:
            DocumentNotFoundError: If the document does not exist.
            InvalidReportTypeError: If the report type is unsupported.
        """
        if report_type not in VALID_REPORT_TYPES:
            raise InvalidReportTypeError(
                f"Unsupported report type {report_type!r}. "
                f"Choose from: {', '.join(sorted(VALID_REPORT_TYPES))}"
            )

        doc_uuid = uuid.UUID(document_id)
        document = await self._get_document(doc_uuid, db)
        extracted_fields = await self._get_extracted_fields(doc_uuid, db)
        risk_items = await self._get_risk_items(doc_uuid, db)

        content = self._build_content(
            document=document,
            extracted_fields=extracted_fields,
            risk_items=risk_items,
            report_type=report_type,
        )

        title = self._build_title(document, report_type)

        report = Report(
            id=uuid.uuid4(),
            user_id=user_id,
            document_id=doc_uuid,
            report_type=report_type,
            title=title,
            content=content,
            format="json",
            status="generated",
            generated_at=datetime.now(UTC),
        )

        db.add(report)
        await db.flush()
        await db.refresh(report)

        logger.info(
            "Report generated: id=%s type=%s document=%s",
            report.id,
            report_type,
            document_id,
        )
        return report

    async def _get_document(self, doc_uuid: uuid.UUID, db: AsyncSession) -> Document:
        stmt = select(Document).where(
            Document.id == doc_uuid,
            Document.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        document = result.scalar_one_or_none()
        if document is None:
            raise DocumentNotFoundError(f"Document {doc_uuid} not found.")
        return document

    async def _get_extracted_fields(
        self, doc_uuid: uuid.UUID, db: AsyncSession
    ) -> list[ExtractedField]:
        stmt = (
            select(ExtractedField)
            .where(ExtractedField.document_id == doc_uuid)
            .order_by(ExtractedField.field_name)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _get_risk_items(
        self, doc_uuid: uuid.UUID, db: AsyncSession
    ) -> list[RiskItem]:
        stmt = (
            select(RiskItem)
            .where(
                RiskItem.document_id == doc_uuid,
                RiskItem.deleted_at.is_(None),
            )
            .order_by(RiskItem.severity.desc(), RiskItem.title)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    def _build_title(self, document: Document, report_type: str) -> str:
        type_labels = {
            "summary": "Summary Report",
            "detailed": "Detailed Analysis Report",
            "risk_assessment": "Risk Assessment Report",
        }
        label = type_labels.get(report_type, "Report")
        return f"{label} — {document.original_filename}"

    def _build_content(
        self,
        *,
        document: Document,
        extracted_fields: list[ExtractedField],
        risk_items: list[RiskItem],
        report_type: str,
    ) -> dict:
        overview = self._build_overview(document)
        key_findings = self._build_key_findings(extracted_fields, risk_items)
        extracted_fields_section = self._build_extracted_fields(extracted_fields)
        risks_section = self._build_risks(risk_items)
        checklist = self._build_checklist(document, extracted_fields, risk_items)
        recommendations = self._build_recommendations(risk_items, extracted_fields)

        content: dict = {
            "report_type": report_type,
            "generated_at": datetime.now(UTC).isoformat(),
            "document": {
                "id": str(document.id),
                "filename": document.original_filename,
                "mime_type": document.mime_type,
                "status": document.status,
                "page_count": document.page_count,
                "document_type": document.document_type,
            },
            "overview": overview,
            "key_findings": key_findings,
            "extracted_fields": extracted_fields_section,
            "risks": risks_section,
            "checklist": checklist,
            "recommendations": recommendations,
        }

        if report_type == "summary":
            content = self._trim_to_summary(content)
        elif report_type == "risk_assessment":
            content = self._emphasize_risks(content)

        return content

    def _build_overview(self, document: Document) -> dict:
        return {
            "filename": document.original_filename,
            "mime_type": document.mime_type,
            "file_size_bytes": document.file_size_bytes,
            "page_count": document.page_count,
            "document_type": document.document_type or "Unknown",
            "status": document.status,
            "uploaded_at": document.uploaded_at.isoformat() if document.uploaded_at else None,
            "processed_at": document.processed_at.isoformat() if document.processed_at else None,
        }

    def _build_key_findings(
        self,
        extracted_fields: list[ExtractedField],
        risk_items: list[RiskItem],
    ) -> list[str]:
        findings: list[str] = []

        if extracted_fields:
            verified = [f for f in extracted_fields if f.is_verified]
            high_conf = [f for f in extracted_fields if f.confidence is not None and f.confidence >= 0.8]
            findings.append(
                f"{len(extracted_fields)} fields extracted, "
                f"{len(verified)} verified, {len(high_conf)} high-confidence."
            )

            field_names = sorted({f.field_name for f in extracted_fields})
            if field_names:
                findings.append(
                    f"Extracted field types: {', '.join(field_names[:10])}"
                    + ("..." if len(field_names) > 10 else "")
                )
        else:
            findings.append("No fields have been extracted from this document.")

        if risk_items:
            by_severity: dict[str, int] = {}
            for r in risk_items:
                by_severity[r.severity] = by_severity.get(r.severity, 0) + 1
            severity_parts = [f"{count} {sev}" for sev, count in sorted(by_severity.items())]
            findings.append(
                f"{len(risk_items)} risk(s) identified: {', '.join(severity_parts)}."
            )

            critical_high = [r for r in risk_items if r.severity in ("critical", "high")]
            for r in critical_high[:3]:
                findings.append(f"[{r.severity.upper()}] {r.title}")
        else:
            findings.append("No risks identified.")

        return findings

    def _build_extracted_fields(
        self, extracted_fields: list[ExtractedField]
    ) -> list[dict]:
        return [
            {
                "field_name": f.field_name,
                "field_value": f.field_value,
                "raw_text": f.raw_text,
                "confidence": f.confidence,
                "page_number": f.page_number,
                "is_verified": f.is_verified,
            }
            for f in extracted_fields
        ]

    def _build_risks(self, risk_items: list[RiskItem]) -> list[dict]:
        return [
            {
                "id": str(r.id),
                "category": r.category,
                "severity": r.severity,
                "title": r.title,
                "description": r.description,
                "evidence": r.evidence,
                "page_number": r.page_number,
                "status": r.status,
                "resolution": r.resolution,
                "detected_by": r.detected_by,
            }
            for r in risk_items
        ]

    def _build_checklist(
        self,
        document: Document,
        extracted_fields: list[ExtractedField],
        risk_items: list[RiskItem],
    ) -> list[dict]:
        checklist: list[dict] = []

        checklist.append({
            "item": "Document uploaded",
            "status": "pass" if document else "fail",
        })
        checklist.append({
            "item": "Document processed",
            "status": "pass" if document.status in (
                "ocr_complete", "extraction_complete", "reviewed", "completed"
            ) else "pending",
        })
        checklist.append({
            "item": "Fields extracted",
            "status": "pass" if extracted_fields else "fail",
        })

        unverified = [f for f in extracted_fields if not f.is_verified]
        checklist.append({
            "item": "All fields verified",
            "status": "pass" if extracted_fields and not unverified else (
                "warning" if unverified else "pending"
            ),
        })

        low_conf = [f for f in extracted_fields if f.confidence is not None and f.confidence < 0.5]
        checklist.append({
            "item": "No low-confidence extractions",
            "status": "warning" if low_conf else "pass",
        })

        open_risks = [r for r in risk_items if r.status == "open"]
        critical_risks = [r for r in open_risks if r.severity in ("critical", "high")]
        checklist.append({
            "item": "Critical/high risks resolved",
            "status": "fail" if critical_risks else (
                "warning" if open_risks else "pass"
            ),
        })

        return checklist

    def _build_recommendations(
        self,
        risk_items: list[RiskItem],
        extracted_fields: list[ExtractedField],
    ) -> list[str]:
        recommendations: list[str] = []

        unverified = [f for f in extracted_fields if not f.is_verified]
        if unverified:
            recommendations.append(
                f"Review and verify {len(unverified)} extracted field(s) that have not been confirmed."
            )

        low_conf = [f for f in extracted_fields if f.confidence is not None and f.confidence < 0.5]
        if low_conf:
            names = sorted({f.field_name for f in low_conf})
            recommendations.append(
                f"Re-extract low-confidence fields: {', '.join(names[:5])}"
                + ("..." if len(names) > 5 else "")
            )

        open_risks = [r for r in risk_items if r.status == "open"]
        critical_high = [r for r in open_risks if r.severity in ("critical", "high")]
        if critical_high:
            recommendations.append(
                f"Address {len(critical_high)} critical/high severity risk(s) before proceeding."
            )
        if open_risks:
            recommendations.append(
                f"Review {len(open_risks)} open risk item(s) and update their resolution status."
            )

        if not extracted_fields:
            recommendations.append(
                "No fields extracted. Consider running the extraction pipeline on this document."
            )

        if not recommendations:
            recommendations.append(
                "Document analysis is complete. No immediate action items detected."
            )

        return recommendations

    def _trim_to_summary(self, content: dict) -> dict:
        fields = content.get("extracted_fields", [])
        content["extracted_fields"] = [
            {
                "field_name": f["field_name"],
                "field_value": f["field_value"],
                "confidence": f["confidence"],
            }
            for f in fields
        ]

        risks = content.get("risks", [])
        content["risks"] = [
            {
                "category": r["category"],
                "severity": r["severity"],
                "title": r["title"],
                "status": r["status"],
            }
            for r in risks
        ]
        return content

    def _emphasize_risks(self, content: dict) -> dict:
        risks = content.get("risks", [])
        content["risk_summary"] = {
            "total": len(risks),
            "critical": sum(1 for r in risks if r.get("severity") == "critical"),
            "high": sum(1 for r in risks if r.get("severity") == "high"),
            "medium": sum(1 for r in risks if r.get("severity") == "medium"),
            "low": sum(1 for r in risks if r.get("severity") == "low"),
            "info": sum(1 for r in risks if r.get("severity") == "info"),
            "open": sum(1 for r in risks if r.get("status") == "open"),
            "resolved": sum(1 for r in risks if r.get("status") == "resolved"),
        }
        return content
