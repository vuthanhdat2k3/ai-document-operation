import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class RiskItem(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "risk_items"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE", name="fk_risk_items_document_id"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="open")
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", name="fk_risk_items_resolved_by"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    detected_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    document = relationship("Document", back_populates="risk_items", lazy="selectin")
    resolver = relationship("User", lazy="selectin")

    __table_args__ = (
        CheckConstraint(
            "severity IN ('critical', 'high', 'medium', 'low', 'info')",
            name="ck_risk_items_severity_valid",
        ),
        CheckConstraint(
            "status IN ('open', 'in_review', 'resolved', 'dismissed', 'false_positive')",
            name="ck_risk_items_status_valid",
        ),
        Index("idx_risk_items_document_id", "document_id", postgresql_where="deleted_at IS NULL"),
        Index(
            "idx_risk_items_severity",
            "severity",
            postgresql_where="deleted_at IS NULL AND status = 'open'",
        ),
        Index("idx_risk_items_status", "status", postgresql_where="deleted_at IS NULL"),
        Index(
            "idx_risk_items_doc_severity",
            "document_id",
            "severity",
            postgresql_where="deleted_at IS NULL",
        ),
        Index("idx_risk_items_category", "category", postgresql_where="deleted_at IS NULL"),
    )

    def __repr__(self) -> str:
        return f"<RiskItem(id={self.id}, category={self.category!r}, severity={self.severity!r})>"
