"""Field extraction API endpoints."""

import logging
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.error_handler import NotFoundError, ValidationErrorDetail
from app.api.schemas.extraction import (
    ExtractRequest,
    ExtractedFieldResponse,
    ExtractionResultResponse,
    FieldUpdateRequest,
    FieldUpdateResponse,
    ValidationResultResponse,
)
from app.auth.dependencies import get_current_user_id
from app.db.session import get_db
from app.services.extraction_service import (
    DocumentNotFoundError,
    ExtractionFailedError,
    ExtractionService,
    SchemaNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["extraction"])


async def _get_extraction_service() -> ExtractionService:
    """Dependency that provides an ExtractionService instance."""
    return ExtractionService()

@router.post("/{document_id}/extract", response_model=ExtractionResultResponse)
async def extract_fields(
    document_id: uuid.UUID,
    body: ExtractRequest,
    service: ExtractionService = Depends(_get_extraction_service),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ExtractionResultResponse:
    """Run the field extraction pipeline on a document.

    Performs: classify → extract → validate → normalize → save.

    Args:
        document_id: UUID of the document to extract from.
        body: Request body specifying the extraction schema name.
        service: Injected ExtractionService.
        db: Injected async database session.

    Returns:
        Extraction result with all extracted fields and validation.

    Raises:
        404: Document or schema not found.
        422: Extraction pipeline failed.
    """
    try:
        result = await service.extract_fields(
            document_id=str(document_id),
            schema_name=body.schema_name,
            db=db,
        )
        await db.commit()
    except DocumentNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    except SchemaNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    except ExtractionFailedError as exc:
        raise ValidationErrorDetail(str(exc)) from exc

    field_responses = []
    for f in result.fields:
        field_responses.append(
            ExtractedFieldResponse(
                id="",
                field_name=f.field_name,
                field_value=f.field_value,
                raw_text=f.raw_text,
                confidence=f.confidence,
                page_number=f.page_number,
                extraction_model="rule-based",
                is_verified=False,
            )
        )

    return ExtractionResultResponse(
        document_id=result.document_id,
        document_type=result.document_type,
        classification_confidence=result.classification_confidence,
        schema_name=result.schema_name,
        schema_version=result.schema_version,
        total_fields=result.total_fields,
        extracted_count=result.extracted_count,
        valid_count=result.valid_count,
        validation=ValidationResultResponse(
            is_valid=result.validation.is_valid,
            errors=result.validation.errors,
            warnings=result.validation.warnings,
        ),
        fields=field_responses,
    )


@router.get("/{document_id}/fields", response_model=list[ExtractedFieldResponse])
async def get_extracted_fields(
    document_id: uuid.UUID,
    service: ExtractionService = Depends(_get_extraction_service),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[ExtractedFieldResponse]:
    """Get all extracted fields for a document.

    Args:
        document_id: UUID of the document.
        service: Injected ExtractionService.
        db: Injected async database session.

    Returns:
        List of extracted field responses.

    Raises:
        404: Document not found.
    """
    try:
        fields = await service.get_fields(
            document_id=str(document_id),
            db=db,
        )
    except DocumentNotFoundError as exc:
        raise NotFoundError(str(exc)) from exc

    return [
        ExtractedFieldResponse(
            id=f["id"],
            field_name=f["field_name"],
            field_value=f["field_value"],
            raw_text=f["raw_text"],
            confidence=f["confidence"],
            page_number=f["page_number"],
            extraction_model=f["extraction_model"],
            is_verified=f["is_verified"],
            verified_by=f["verified_by"],
            verified_at=f["verified_at"],
            created_at=f["created_at"],
            updated_at=f["updated_at"],
        )
        for f in fields
    ]


@router.put(
    "/{document_id}/fields/{field_id}",
    response_model=FieldUpdateResponse,
)
async def update_extracted_field(
    document_id: uuid.UUID,
    field_id: uuid.UUID,
    body: FieldUpdateRequest,
    service: ExtractionService = Depends(_get_extraction_service),  # noqa: B008
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> FieldUpdateResponse:
    """Manually correct an extracted field value.

    Marks the field as verified by the current user.

    Args:
        document_id: UUID of the document (used for URL scoping).
        field_id: UUID of the extracted field to update.
        body: Request body with new field_value and/or raw_text.
        service: Injected ExtractionService.
        user_id: Current authenticated user ID.
        db: Injected async database session.

    Returns:
        Updated field information.

    Raises:
        404: Field not found.
        422: Update failed.
    """
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise ValidationErrorDetail("No fields provided for update.")

    try:
        result = await service.update_field(
            field_id=str(field_id),
            updates=updates,
            user_id=str(user_id),
            db=db,
        )
        await db.commit()
    except Exception as exc:
        if "not found" in str(exc).lower():
            raise NotFoundError(str(exc)) from exc
        raise ValidationErrorDetail(str(exc)) from exc

    return FieldUpdateResponse(
        id=result["id"],
        field_name=result["field_name"],
        old_value=result.get("old_value"),
        new_value=result.get("new_value"),
        is_verified=result["is_verified"],
        verified_by=result["verified_by"],
        verified_at=result["verified_at"],
    )
