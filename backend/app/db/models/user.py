import uuid
from datetime import datetime

from sqlalchemy import text as sa_text
from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class User(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, server_default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    preferences: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))

    documents = relationship("Document", back_populates="user", lazy="selectin")
    agent_sessions = relationship("AgentSession", back_populates="user", lazy="selectin")
    assigned_tasks = relationship("Task", back_populates="assignee", foreign_keys="Task.assigned_to", lazy="selectin")
    reports = relationship("Report", back_populates="user", lazy="selectin")
    audit_logs = relationship("AuditLog", back_populates="user", lazy="selectin")

    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'user', 'operator', 'analyst', 'viewer')",
            name="ck_users_role_valid",
        ),
        Index("idx_users_email", "email", postgresql_where="deleted_at IS NULL"),
        Index("idx_users_role_active", "role", "is_active", postgresql_where="deleted_at IS NULL"),
        Index("idx_users_deleted_at", "deleted_at", postgresql_where="deleted_at IS NOT NULL"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email!r}, role={self.role!r})>"
