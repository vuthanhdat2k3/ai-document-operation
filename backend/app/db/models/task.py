import uuid
from datetime import date, datetime

from sqlalchemy import text as sa_text
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class Task(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "tasks"

    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL", name="fk_tasks_document_id"),
        nullable=True,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_sessions.id", ondelete="SET NULL", name="fk_tasks_session_id"),
        nullable=True,
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", name="fk_tasks_assigned_to"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="pending")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    task_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))

    document = relationship("Document", back_populates="tasks", lazy="selectin")
    assignee = relationship("User", back_populates="assigned_tasks", foreign_keys=[assigned_to], lazy="selectin")

    __table_args__ = (
        CheckConstraint(
            "priority IN ('critical', 'high', 'medium', 'low')",
            name="ck_tasks_priority_valid",
        ),
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'cancelled', 'blocked')",
            name="ck_tasks_status_valid",
        ),
        Index(
            "idx_tasks_assigned_to",
            "assigned_to",
            postgresql_where="deleted_at IS NULL AND status NOT IN ('completed', 'cancelled')",
        ),
        Index("idx_tasks_document_id", "document_id", postgresql_where="deleted_at IS NULL"),
        Index("idx_tasks_status", "status", postgresql_where="deleted_at IS NULL"),
        Index("idx_tasks_priority_status", "priority", "status", postgresql_where="deleted_at IS NULL"),
        Index(
            "idx_tasks_due_date",
            "due_date",
            postgresql_where="deleted_at IS NULL AND status NOT IN ('completed', 'cancelled')",
        ),
    )

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, title={self.title!r}, status={self.status!r})>"
