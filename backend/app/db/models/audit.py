import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class AuditLog(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", name="fk_audit_logs_user_id"),
        nullable=True,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    old_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    request_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    user = relationship("User", back_populates="audit_logs", lazy="selectin")

    __table_args__ = (
        CheckConstraint(
            "action IN ('create', 'read', 'update', 'delete', 'login', 'logout', "
            "'login_failed', 'upload', 'download', 'process', 'export', 'import', "
            "'approve', 'reject', 'execute', 'configure')",
            name="ck_audit_logs_action_valid",
        ),
        Index("idx_audit_logs_user_id", "user_id"),
        Index("idx_audit_logs_entity", "entity_type", "entity_id"),
        Index("idx_audit_logs_action", "action"),
        Index("idx_audit_logs_created_at", "created_at", postgresql_using="btree"),
        Index(
            "idx_audit_logs_session_id",
            "session_id",
            postgresql_where="session_id IS NOT NULL",
        ),
        Index(
            "idx_audit_logs_request_id",
            "request_id",
            postgresql_where="request_id IS NOT NULL",
        ),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action!r}, entity_type={self.entity_type!r})>"
