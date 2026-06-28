import uuid
from datetime import datetime

from sqlalchemy import text as sa_text
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class Document(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "documents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", name="fk_documents_user_id"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(50), nullable=False, server_default="local")
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="uploaded")
    document_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    classification: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="documents", lazy="noload")
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan", lazy="raise")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan", lazy="raise")
    extracted_fields = relationship("ExtractedField", back_populates="document", cascade="all, delete-orphan", lazy="raise")
    risk_items = relationship("RiskItem", back_populates="document", cascade="all, delete-orphan", lazy="raise")
    tasks = relationship("Task", back_populates="document", lazy="noload")
    reports = relationship("Report", back_populates="document", lazy="noload")
    agent_sessions = relationship("AgentSession", back_populates="document", lazy="noload")

    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded', 'queued', 'processing', 'ocr_complete', "
            "'extraction_complete', 'reviewed', 'completed', 'failed', 'archived')",
            name="ck_documents_status_valid",
        ),
        CheckConstraint("file_size_bytes > 0", name="ck_documents_file_size_positive"),
        CheckConstraint(
            "page_count IS NULL OR page_count > 0",
            name="ck_documents_page_count_positive",
        ),
        Index("idx_documents_user_id", "user_id", postgresql_where="deleted_at IS NULL"),
        Index("idx_documents_user_id_status", "user_id", "status", postgresql_where="deleted_at IS NULL"),
        Index("idx_documents_status", "status", postgresql_where="deleted_at IS NULL"),
        Index("idx_documents_document_type", "document_type", postgresql_where="deleted_at IS NULL"),
        Index("idx_documents_uploaded_at", uploaded_at.desc()),
        Index("idx_documents_created_at", "created_at"),
        Index("idx_documents_checksum", "checksum_sha256"),
        Index("idx_documents_deleted_at", "deleted_at", postgresql_where="deleted_at IS NOT NULL"),
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename={self.original_filename!r}, status={self.status!r})>"
