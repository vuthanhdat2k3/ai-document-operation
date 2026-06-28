import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class ExtractionSchema(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "extraction_schemas"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    fields_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", name="fk_extraction_schemas_created_by"),
        nullable=True,
    )

    creator = relationship("User", lazy="selectin")
    extracted_fields = relationship("ExtractedField", back_populates="schema", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_extraction_schemas_name_version"),
        CheckConstraint("version > 0", name="ck_extraction_schemas_version_positive"),
        Index("idx_extraction_schemas_document_type", "document_type", postgresql_where="deleted_at IS NULL"),
        Index(
            "idx_extraction_schemas_active",
            "is_active",
            postgresql_where="deleted_at IS NULL AND is_active = TRUE",
        ),
    )

    def __repr__(self) -> str:
        return f"<ExtractionSchema(id={self.id}, name={self.name!r}, version={self.version})>"


class ExtractedField(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "extracted_fields"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE", name="fk_extracted_fields_document_id"),
        nullable=False,
    )
    schema_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("extraction_schemas.id", ondelete="RESTRICT", name="fk_extracted_fields_schema_id"),
        nullable=False,
    )
    field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    field_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bounding_box: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extraction_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", name="fk_extracted_fields_verified_by"),
        nullable=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document = relationship("Document", back_populates="extracted_fields", lazy="selectin")
    schema = relationship("ExtractionSchema", back_populates="extracted_fields", lazy="selectin")
    verifier = relationship("User", lazy="selectin")

    __table_args__ = (
        UniqueConstraint(
            "document_id", "schema_id", "field_name",
            name="uq_extracted_fields_doc_schema_field",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_extracted_fields_confidence_range",
        ),
        CheckConstraint(
            "(is_verified = FALSE AND verified_by IS NULL AND verified_at IS NULL) OR "
            "(is_verified = TRUE AND verified_by IS NOT NULL AND verified_at IS NOT NULL)",
            name="ck_extracted_fields_verified_consistency",
        ),
        Index("idx_extracted_fields_document_id", "document_id"),
        Index("idx_extracted_fields_schema_id", "schema_id"),
        Index("idx_extracted_fields_doc_schema", "document_id", "schema_id"),
        Index(
            "idx_extracted_fields_unverified",
            "document_id",
            postgresql_where="is_verified = FALSE AND confidence < 0.8",
        ),
    )

    def __repr__(self) -> str:
        return f"<ExtractedField(id={self.id}, field_name={self.field_name!r}, confidence={self.confidence})>"
