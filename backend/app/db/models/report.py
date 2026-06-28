import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class Report(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "reports"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_reports_user_id"),
        nullable=False,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL", name="fk_reports_document_id"),
        nullable=True,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_sessions.id", ondelete="SET NULL", name="fk_reports_session_id"),
        nullable=True,
    )
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False, server_default="json")
    storage_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="generated")
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="reports", lazy="selectin")
    document = relationship("Document", back_populates="reports", lazy="selectin")

    __table_args__ = (
        CheckConstraint(
            "format IN ('json', 'pdf', 'html', 'csv', 'markdown')",
            name="ck_reports_format_valid",
        ),
        CheckConstraint(
            "status IN ('generating', 'generated', 'failed', 'expired')",
            name="ck_reports_status_valid",
        ),
        Index("idx_reports_user_id", "user_id", postgresql_where="deleted_at IS NULL"),
        Index("idx_reports_document_id", "document_id", postgresql_where="deleted_at IS NULL"),
        Index("idx_reports_session_id", "session_id", postgresql_where="deleted_at IS NULL"),
        Index("idx_reports_type", "report_type", postgresql_where="deleted_at IS NULL"),
        Index("idx_reports_generated_at", generated_at.desc()),
    )

    def __repr__(self) -> str:
        return f"<Report(id={self.id}, report_type={self.report_type!r}, status={self.status!r})>"
