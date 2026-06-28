import uuid

from sqlalchemy import text as sa_text
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import func

from app.db.base import Base, TimestampMixin, UUIDMixin


class DocumentPage(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "document_pages"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE", name="fk_document_pages_document_id"),
        nullable=False,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    width_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dpi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_storage_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    ocr_engine: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ocr_raw_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    document = relationship("Document", back_populates="pages", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_document_pages_doc_page"),
        CheckConstraint("page_number > 0", name="ck_document_pages_page_number_positive"),
        CheckConstraint(
            "ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 1)",
            name="ck_document_pages_confidence_range",
        ),
        CheckConstraint(
            "(width_px IS NULL OR width_px > 0) AND "
            "(height_px IS NULL OR height_px > 0) AND "
            "(dpi IS NULL OR dpi > 0)",
            name="ck_document_pages_dimensions_positive",
        ),
        Index("idx_document_pages_document_id", "document_id"),
        Index("idx_document_pages_doc_page", "document_id", "page_number"),
        Index(
            "idx_document_pages_confidence",
            "ocr_confidence",
            postgresql_where="ocr_confidence IS NOT NULL AND ocr_confidence < 0.7",
        ),
    )

    def __repr__(self) -> str:
        return f"<DocumentPage(id={self.id}, document_id={self.document_id}, page={self.page_number})>"


class DocumentChunk(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "document_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE", name="fk_document_chunks_document_id"),
        nullable=False,
    )
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    chunk_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))

    document = relationship("Document", back_populates="chunks", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_doc_chunk"),
        CheckConstraint("chunk_index >= 0", name="ck_document_chunks_chunk_index_positive"),
        CheckConstraint(
            "token_count IS NULL OR token_count > 0",
            name="ck_document_chunks_token_count_positive",
        ),
        CheckConstraint(
            "embedding_dim IS NULL OR embedding_dim > 0",
            name="ck_document_chunks_embedding_dim_positive",
        ),
        Index("idx_document_chunks_document_id", "document_id"),
        Index("idx_document_chunks_doc_chunk", "document_id", "chunk_index"),
        Index(
            "idx_document_chunks_embedding_model",
            "embedding_model",
            postgresql_where="embedding_model IS NOT NULL",
        ),
    )

    def __repr__(self) -> str:
        return f"<DocumentChunk(id={self.id}, document_id={self.document_id}, chunk_index={self.chunk_index})>"
