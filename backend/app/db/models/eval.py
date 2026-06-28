import uuid
from datetime import datetime

from sqlalchemy import text as sa_text
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


class EvalDataset(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "eval_datasets"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    storage_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    schema_definition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", name="fk_eval_datasets_created_by"),
        nullable=True,
    )

    creator = relationship("User", lazy="selectin")
    eval_runs = relationship("EvalRun", back_populates="dataset", cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_eval_datasets_name_version"),
        CheckConstraint("version > 0", name="ck_eval_datasets_version_positive"),
        CheckConstraint("record_count >= 0", name="ck_eval_datasets_record_count_non_negative"),
        Index("idx_eval_datasets_task_type", "task_type", postgresql_where="deleted_at IS NULL"),
        Index(
            "idx_eval_datasets_active",
            "is_active",
            postgresql_where="deleted_at IS NULL AND is_active = TRUE",
        ),
    )

    def __repr__(self) -> str:
        return f"<EvalDataset(id={self.id}, name={self.name!r}, version={self.version})>"


class EvalRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "eval_runs"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("eval_datasets.id", ondelete="CASCADE", name="fk_eval_runs_dataset_id"),
        nullable=False,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_sessions.id", ondelete="SET NULL", name="fk_eval_runs_session_id"),
        nullable=True,
    )
    run_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="running")
    metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_records: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    dataset = relationship("EvalDataset", back_populates="eval_runs", lazy="selectin")
    session = relationship("AgentSession", back_populates="eval_runs", lazy="selectin")

    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'cancelled')",
            name="ck_eval_runs_status_valid",
        ),
        CheckConstraint("error_count >= 0", name="ck_eval_runs_error_count_non_negative"),
        CheckConstraint("total_records >= 0", name="ck_eval_runs_total_records_non_negative"),
        Index("idx_eval_runs_dataset_id", "dataset_id"),
        Index("idx_eval_runs_status", "status"),
        Index("idx_eval_runs_started_at", started_at.desc()),
    )

    def __repr__(self) -> str:
        return f"<EvalRun(id={self.id}, dataset_id={self.dataset_id}, status={self.status!r})>"
