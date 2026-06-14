"""Extraction service orchestrating the full field extraction pipeline."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.db.models.document import Document
from app.db.models.extraction import ExtractedField, ExtractionSchema
from app.services.classifier import ClassificationResult, DocumentClassifier
from app.services.field_extractor import ExtractedFieldValue, FieldExtractor
from app.services.field_normalizer import FieldNormalizer
from app.services.field_validator import FieldValidator, ValidationResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ExtractionServiceError(Exception):
    """Base exception for extraction service operations."""


class DocumentNotFoundError(ExtractionServiceError):
    """Raised when a document cannot be located."""


class SchemaNotFoundError(ExtractionServiceError):
    """Raised when an extraction schema cannot be located."""


class ExtractionFailedError(ExtractionServiceError):
    """Raised when the extraction pipeline fails."""


@dataclass
class ExtractionResult:
    """Result of the full extraction pipeline."""

    document_id: str
    document_type: str
    classification_confidence: float
    fields: list[ExtractedFieldValue]
    validation: ValidationResult
    schema_name: str
    schema_version: int
    total_fields: int
    extracted_count: int
    valid_count: int


@dataclass
class FieldUpdateResult:
    """Result of a manual field update."""

    field_id: str
    field_name: str
    old_value: dict[str, Any]
    new_value: dict[str, Any]
    is_verified: bool


class ExtractionService:
    """Orchestrates document field extraction: classify → extract → validate → normalize → save.

    Args:
        classifier: Optional DocumentClassifier override.
        extractor: Optional FieldExtractor override.
        validator: Optional FieldValidator override.
        normalizer: Optional FieldNormalizer override.
    """

    def __init__(
        self,
        classifier: DocumentClassifier | None = None,
        extractor: FieldExtractor | None = None,
        validator: FieldValidator | None = None,
        normalizer: FieldNormalizer | None = None,
    ) -> None:
        self._classifier = classifier or DocumentClassifier()
        self._extractor = extractor or FieldExtractor()
        self._validator = validator or FieldValidator()
        self._normalizer = normalizer or FieldNormalizer()

    async def extract_fields(
        self,
        document_id: str,
        schema_name: str,
        db: AsyncSession,
    ) -> ExtractionResult:
        """Run the full field extraction pipeline for a document.

        Pipeline: classify → extract → validate → normalize → save.

        Args:
            document_id: UUID string of the document.
            schema_name: Name of the extraction schema to use.
            db: Active async database session.

        Returns:
            ExtractionResult with all pipeline outputs.

        Raises:
            DocumentNotFoundError: If the document does not exist.
            SchemaNotFoundError: If the schema does not exist.
            ExtractionFailedError: If the pipeline fails.
        """
        doc_uuid = uuid.UUID(document_id)

        document = await self._get_document(doc_uuid, db)
        schema = await self._get_schema(schema_name, db)

        text = self._get_document_text(document)

        classification = self._classifier.classify(text)
        logger.info(
            "Document classified: id=%s type=%s confidence=%.3f",
            document_id,
            classification.document_type,
            classification.confidence,
        )

        fields = await self._extractor.extract(
            text=text,
            schema=schema.fields_schema,
            document_type=classification.document_type,
        )

        validation = self._validator.validate(fields, schema.fields_schema)
        logger.info(
            "Validation result: valid=%s errors=%d warnings=%d",
            validation.is_valid,
            len(validation.errors),
            len(validation.warnings),
        )

        normalized_fields = self._normalizer.normalize(fields)

        await self._save_extracted_fields(
            document_id=doc_uuid,
            schema_id=schema.id,
            fields=normalized_fields,
            db=db,
        )

        document.document_type = classification.document_type
        document.classification = {
            "type": classification.document_type,
            "confidence": classification.confidence,
            "subtypes": classification.subtypes,
            "scores": classification.scores,
        }
        document.status = "extraction_complete"
        document.processed_at = datetime.now(UTC)
        await db.flush()

        extracted_count = sum(
            1 for f in normalized_fields
            if f.field_value and f.field_value.get("value") is not None
        )

        return ExtractionResult(
            document_id=document_id,
            document_type=classification.document_type,
            classification_confidence=classification.confidence,
            fields=normalized_fields,
            validation=validation,
            schema_name=schema.name,
            schema_version=schema.version,
            total_fields=len(normalized_fields),
            extracted_count=extracted_count,
            valid_count=sum(1 for f in normalized_fields if f.confidence >= 0.5),
        )

    async def get_fields(
        self, document_id: str, db: AsyncSession
    ) -> list[dict[str, Any]]:
        """Get all extracted fields for a document.

        Args:
            document_id: UUID string of the document.
            db: Active async database session.

        Returns:
            List of field dictionaries.

        Raises:
            DocumentNotFoundError: If the document does not exist.
        """
        doc_uuid = uuid.UUID(document_id)

        stmt = select(Document).where(
            Document.id == doc_uuid,
            Document.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        document = result.scalar_one_or_none()
        if document is None:
            raise DocumentNotFoundError(f"Document {document_id} not found.")

        stmt = (
            select(ExtractedField)
            .where(ExtractedField.document_id == doc_uuid)
            .order_by(ExtractedField.field_name)
        )
        result = await db.execute(stmt)
        fields = list(result.scalars().all())

        return [
            {
                "id": str(f.id),
                "field_name": f.field_name,
                "field_value": f.field_value,
                "raw_text": f.raw_text,
                "confidence": f.confidence,
                "page_number": f.page_number,
                "extraction_model": f.extraction_model,
                "is_verified": f.is_verified,
                "verified_by": str(f.verified_by) if f.verified_by else None,
                "verified_at": f.verified_at.isoformat() if f.verified_at else None,
                "created_at": f.created_at.isoformat() if f.created_at else None,
                "updated_at": f.updated_at.isoformat() if f.updated_at else None,
            }
            for f in fields
        ]

    async def update_field(
        self,
        field_id: str,
        updates: dict[str, Any],
        user_id: str,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Manually correct an extracted field.

        Args:
            field_id: UUID string of the extracted field.
            updates: Dictionary with 'field_value' and/or 'raw_text'.
            user_id: UUID string of the user making the correction.
            db: Active async database session.

        Returns:
            Updated field dictionary.

        Raises:
            ExtractionServiceError: If the field does not exist.
        """
        f_uuid = uuid.UUID(field_id)
        u_uuid = uuid.UUID(user_id)

        stmt = select(ExtractedField).where(ExtractedField.id == f_uuid)
        result = await db.execute(stmt)
        field_obj = result.scalar_one_or_none()

        if field_obj is None:
            raise ExtractionServiceError(f"Extracted field {field_id} not found.")

        old_value = field_obj.field_value or {}

        if "field_value" in updates:
            field_obj.field_value = updates["field_value"]
        if "raw_text" in updates:
            field_obj.raw_text = updates["raw_text"]

        field_obj.is_verified = True
        field_obj.verified_by = u_uuid
        field_obj.verified_at = datetime.now(UTC)

        await db.flush()
        await db.refresh(field_obj)

        logger.info(
            "Field manually updated: field_id=%s user=%s",
            field_id,
            user_id,
        )

        return {
            "id": str(field_obj.id),
            "field_name": field_obj.field_name,
            "old_value": old_value,
            "new_value": field_obj.field_value,
            "is_verified": field_obj.is_verified,
            "verified_by": str(field_obj.verified_by),
            "verified_at": field_obj.verified_at.isoformat(),
        }

    async def _get_document(self, doc_uuid: uuid.UUID, db: AsyncSession) -> Document:
        """Retrieve a document by UUID."""
        stmt = select(Document).where(
            Document.id == doc_uuid,
            Document.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        document = result.scalar_one_or_none()
        if document is None:
            raise DocumentNotFoundError(f"Document {doc_uuid} not found.")
        return document

    async def _get_schema(
        self, schema_name: str, db: AsyncSession
    ) -> ExtractionSchema:
        """Retrieve the latest active extraction schema by name."""
        stmt = (
            select(ExtractionSchema)
            .where(
                ExtractionSchema.name == schema_name,
                ExtractionSchema.is_active.is_(True),
                ExtractionSchema.deleted_at.is_(None),
            )
            .order_by(ExtractionSchema.version.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        schema = result.scalar_one_or_none()
        if schema is None:
            raise SchemaNotFoundError(
                f"Active extraction schema '{schema_name}' not found."
            )
        return schema

    def _get_document_text(self, document: Document) -> str:
        """Extract text content from a document.

        Checks metadata for pre-extracted text (e.g., from OCR/parsing).
        Falls back to an empty string.
        """
        meta = document.metadata_ or {}

        if "text" in meta:
            return meta["text"]
        if "ocr_text" in meta:
            return meta["ocr_text"]
        if "parsed_text" in meta:
            return meta["parsed_text"]
        if "content" in meta:
            return meta["content"]

        pages = meta.get("pages", [])
        if isinstance(pages, list) and pages:
            page_texts = []
            for page in pages:
                if isinstance(page, dict) and "text" in page:
                    page_texts.append(page["text"])
            if page_texts:
                return "\n\n".join(page_texts)

        logger.warning("No text content found in document metadata for %s", document.id)
        return ""

    async def _save_extracted_fields(
        self,
        document_id: uuid.UUID,
        schema_id: uuid.UUID,
        fields: list[ExtractedFieldValue],
        db: AsyncSession,
    ) -> None:
        """Save or update extracted fields in the database.

        Uses upsert logic: if a field already exists for the same
        (document_id, schema_id, field_name), it updates; otherwise inserts.
        """
        stmt = select(ExtractedField).where(
            ExtractedField.document_id == document_id,
            ExtractedField.schema_id == schema_id,
        )
        result = await db.execute(stmt)
        existing = {f.field_name: f for f in result.scalars().all()}

        for fv in fields:
            if fv.field_name in existing:
                ef = existing[fv.field_name]
                ef.field_value = fv.field_value
                ef.raw_text = fv.raw_text
                ef.confidence = fv.confidence
                ef.page_number = fv.page_number
                ef.is_verified = False
                ef.verified_by = None
                ef.verified_at = None
            else:
                ef = ExtractedField(
                    id=uuid.uuid4(),
                    document_id=document_id,
                    schema_id=schema_id,
                    field_name=fv.field_name,
                    field_value=fv.field_value,
                    raw_text=fv.raw_text,
                    confidence=fv.confidence,
                    page_number=fv.page_number,
                    extraction_model="rule-based",
                    is_verified=False,
                )
                db.add(ef)

        await db.flush()
        logger.info(
            "Saved %d extracted fields for document %s",
            len(fields),
            document_id,
        )
