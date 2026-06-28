import uuid
from datetime import datetime

from sqlalchemy import text as sa_text
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class AgentSession(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agent_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_agent_sessions_user_id"),
        nullable=False,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL", name="fk_agent_sessions_document_id"),
        nullable=True,
    )
    agent_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="running")
    input_data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    output_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="agent_sessions", lazy="selectin")
    document = relationship("Document", back_populates="agent_sessions", lazy="selectin")
    steps = relationship("AgentStep", back_populates="session", cascade="all, delete-orphan", lazy="selectin")
    tool_calls = relationship("ToolCall", back_populates="session", cascade="all, delete-orphan", lazy="selectin")
    eval_runs = relationship("EvalRun", back_populates="session", lazy="selectin")

    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'paused', 'completed', 'failed', 'cancelled', 'timeout')",
            name="ck_agent_sessions_status_valid",
        ),
        CheckConstraint(
            "total_tokens IS NULL OR total_tokens >= 0",
            name="ck_agent_sessions_tokens_positive",
        ),
        CheckConstraint(
            "total_cost_usd IS NULL OR total_cost_usd >= 0",
            name="ck_agent_sessions_cost_positive",
        ),
        Index("idx_agent_sessions_user_id", "user_id"),
        Index("idx_agent_sessions_document_id", "document_id"),
        Index("idx_agent_sessions_status", "status"),
        Index("idx_agent_sessions_agent_type", "agent_type"),
        Index("idx_agent_sessions_started_at", started_at.desc()),
    )

    def __repr__(self) -> str:
        return f"<AgentSession(id={self.id}, agent_type={self.agent_type!r}, status={self.status!r})>"


class AgentStep(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agent_steps"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_sessions.id", ondelete="CASCADE", name="fk_agent_steps_session_id"),
        nullable=False,
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="completed")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    session = relationship("AgentSession", back_populates="steps", lazy="selectin")
    tool_calls = relationship("ToolCall", back_populates="agent_step", cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("session_id", "step_index", name="uq_agent_steps_session_step"),
        CheckConstraint("step_index >= 0", name="ck_agent_steps_step_index_positive"),
        CheckConstraint(
            "step_type IN ('retrieve', 'reason', 'tool_call', 'synthesize', 'plan', 'reflect')",
            name="ck_agent_steps_step_type_valid",
        ),
        CheckConstraint(
            "status IN ('completed', 'failed', 'skipped')",
            name="ck_agent_steps_status_valid",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_agent_steps_duration_positive",
        ),
        CheckConstraint(
            "tokens_used IS NULL OR tokens_used >= 0",
            name="ck_agent_steps_tokens_positive",
        ),
        Index("idx_agent_steps_session_id", "session_id"),
        Index("idx_agent_steps_session_step", "session_id", "step_index"),
        Index("idx_agent_steps_type", "step_type"),
    )

    def __repr__(self) -> str:
        return f"<AgentStep(id={self.id}, session_id={self.session_id}, step_index={self.step_index})>"


class ToolCall(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tool_calls"

    agent_step_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_steps.id", ondelete="CASCADE", name="fk_tool_calls_agent_step_id"),
        nullable=False,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_sessions.id", ondelete="CASCADE", name="fk_tool_calls_session_id"),
        nullable=False,
    )
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tool_input: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    tool_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="success")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    agent_step = relationship("AgentStep", back_populates="tool_calls", lazy="selectin")
    session = relationship("AgentSession", back_populates="tool_calls", lazy="selectin")

    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'failed', 'timeout', 'skipped')",
            name="ck_tool_calls_status_valid",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_tool_calls_duration_positive",
        ),
        CheckConstraint("retry_count >= 0", name="ck_tool_calls_retry_count_positive"),
        Index("idx_tool_calls_agent_step_id", "agent_step_id"),
        Index("idx_tool_calls_session_id", "session_id"),
        Index("idx_tool_calls_tool_name", "tool_name"),
        Index("idx_tool_calls_session_tool", "session_id", "tool_name"),
    )

    def __repr__(self) -> str:
        return f"<ToolCall(id={self.id}, tool_name={self.tool_name!r}, status={self.status!r})>"
