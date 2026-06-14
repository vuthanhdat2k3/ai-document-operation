"""High-level report service orchestrating generation, retrieval, and export."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.config import get_settings
from app.db.models.report import Report
from app.services.markdown_export import MarkdownExporter
from app.services.pdf_export import PdfExporter
from app.services.report_generator import ReportGenerator
from app.storage.minio import MinioStorage

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ReportServiceError(Exception):
    """Base exception for report service operations."""


class ReportNotFoundError(ReportServiceError):
    """Raised when a report cannot be located."""


class InvalidExportFormatError(ReportServiceError):
    """Raised when an unsupported export format is requested."""


class ReportService:
    """Orchestrates report generation, retrieval, and multi-format export.

    Coordinates between:
    - ``ReportGenerator`` for assembling report content from document data.
    - ``MarkdownExporter`` for rendering to Markdown.
    - ``PdfExporter`` for rendering to PDF via HTML.
    - ``MinioStorage`` for persisting exported files.
    """

    def __init__(
        self,
        generator: ReportGenerator | None = None,
        markdown_exporter: MarkdownExporter | None = None,
        pdf_exporter: PdfExporter | None = None,
        storage: MinioStorage | None = None,
    ) -> None:
        self._generator = generator or ReportGenerator()
        self._markdown_exporter = markdown_exporter or MarkdownExporter()
        self._pdf_exporter = pdf_exporter or PdfExporter()
        settings = get_settings()
        self._storage = storage or MinioStorage(settings)
        self._bucket = settings.MINIO_BUCKET

    async def create_report(
        self,
        document_id: str,
        report_type: str,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> Report:
        """Generate and persist a new report.

        Args:
            document_id: UUID string of the source document.
            report_type: One of ``summary``, ``detailed``, ``risk_assessment``.
            user_id: UUID of the requesting user.
            db: Active async database session.

        Returns:
            The newly created ``Report`` ORM instance.
        """
        report = await self._generator.generate(
            document_id=document_id,
            report_type=report_type,
            user_id=user_id,
            db=db,
        )

        await self._store_export(report, "markdown", db)

        logger.info("Report created and stored: id=%s type=%s", report.id, report_type)
        return report

    async def get_report(
        self,
        report_id: str,
        db: AsyncSession,
    ) -> Report:
        """Retrieve a report by ID.

        Args:
            report_id: UUID string of the report.
            db: Active async database session.

        Returns:
            The ``Report`` ORM instance.

        Raises:
            ReportNotFoundError: If the report does not exist.
        """
        report_uuid = uuid.UUID(report_id)
        stmt = select(Report).where(
            Report.id == report_uuid,
            Report.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        report = result.scalar_one_or_none()

        if report is None:
            raise ReportNotFoundError(f"Report {report_id} not found.")

        return report

    async def export_report(
        self,
        report_id: str,
        export_format: str,
        db: AsyncSession,
    ) -> tuple[bytes, str, str]:
        """Export a report in the specified format.

        Args:
            report_id: UUID string of the report.
            export_format: ``markdown`` or ``pdf``.
            db: Active async database session.

        Returns:
            Tuple of (file_bytes, content_type, filename).

        Raises:
            ReportNotFoundError: If the report does not exist.
            InvalidExportFormatError: If the format is unsupported.
        """
        if export_format not in ("markdown", "pdf"):
            raise InvalidExportFormatError(
                f"Unsupported export format {export_format!r}. Use 'markdown' or 'pdf'."
            )

        report = await self.get_report(report_id, db)
        report_uuid = str(report.id)

        if export_format == "markdown":
            md_content = self._markdown_exporter.export(report)
            storage_path = f"reports/{report_uuid}/{report_uuid}.md"
            content_bytes = md_content.encode("utf-8")
            content_type = "text/markdown"
            filename = f"{self._safe_filename(report.title)}.md"

            try:
                await self._storage.upload_file(
                    object_name=storage_path,
                    data=content_bytes,
                    length=len(content_bytes),
                    content_type=content_type,
                    bucket_name=self._bucket,
                )
            except Exception:
                logger.exception("Failed to store markdown export in MinIO: %s", storage_path)

            return content_bytes, content_type, filename

        md_content = self._markdown_exporter.export(report)
        pdf_bytes = self._pdf_exporter.export(md_content)
        is_pdf = pdf_bytes[:4] == b"%PDF"

        if is_pdf:
            storage_path = f"reports/{report_uuid}/{report_uuid}.pdf"
            content_type = "application/pdf"
            filename = f"{self._safe_filename(report.title)}.pdf"
        else:
            storage_path = f"reports/{report_uuid}/{report_uuid}.html"
            content_type = "text/html"
            filename = f"{self._safe_filename(report.title)}.html"

        try:
            await self._storage.upload_file(
                object_name=storage_path,
                data=pdf_bytes,
                length=len(pdf_bytes),
                content_type=content_type,
                bucket_name=self._bucket,
            )
        except Exception:
            logger.exception("Failed to store PDF/HTML export in MinIO: %s", storage_path)

        return pdf_bytes, content_type, filename

    async def _store_export(
        self,
        report: Report,
        export_format: str,
        db: AsyncSession,
    ) -> None:
        """Generate and store an export, updating the report record."""
        report_uuid = str(report.id)

        if export_format == "markdown":
            md_content = self._markdown_exporter.export(report)
            storage_path = f"reports/{report_uuid}/{report_uuid}.md"
            content_bytes = md_content.encode("utf-8")
            content_type = "text/markdown"
        else:
            raise InvalidExportFormatError(f"Initial export format {export_format!r} not supported.")

        try:
            await self._storage.upload_file(
                object_name=storage_path,
                data=content_bytes,
                length=len(content_bytes),
                content_type=content_type,
                bucket_name=self._bucket,
            )
            report.storage_path = storage_path
            report.format = export_format
            await db.flush()
            logger.info("Report export stored: %s", storage_path)
        except Exception:
            logger.exception("Failed to store report export: %s", storage_path)

    @staticmethod
    def _safe_filename(title: str, max_length: int = 100) -> str:
        """Sanitize a report title into a filesystem-safe filename."""
        safe = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in title)
        safe = "_".join(safe.split())
        return safe[:max_length].rstrip("_")
