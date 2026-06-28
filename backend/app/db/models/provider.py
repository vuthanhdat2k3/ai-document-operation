"""LLM Provider, Model, and Agent Model Configuration models.

Manages:
- llm_providers: Supported LLM backends (OpenAI, Anthropic, etc.)
- llm_models: Models per provider (gpt-4o, claude-3, etc.)
- agent_model_configs: Which model each agent uses
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class LLMProvider(Base, UUIDMixin, TimestampMixin):
    """An LLM provider (OpenAI, Anthropic, etc.)."""

    __tablename__ = "llm_providers"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    config_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    models = relationship(
        "LLMModel", back_populates="provider", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint("length(name) > 0", name="ck_llm_providers_name_not_empty"),
        CheckConstraint("length(slug) > 0", name="ck_llm_providers_slug_not_empty"),
        Index("idx_llm_providers_slug", "slug"),
        Index("idx_llm_providers_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<LLMProvider(id={self.id}, slug={self.slug!r})>"


class LLMModel(Base, UUIDMixin, TimestampMixin):
    """A specific model belonging to an LLM provider."""

    __tablename__ = "llm_models"

    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("llm_providers.id", ondelete="CASCADE", name="fk_llm_models_provider_id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_tokens: Mapped[int | None] = mapped_column(nullable=True)
    default_temperature: Mapped[float | None] = mapped_column(nullable=True)
    supports_streaming: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    supports_thinking: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    provider = relationship("LLMProvider", back_populates="models", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("provider_id", "slug", name="uq_llm_models_provider_slug"),
        CheckConstraint("length(name) > 0", name="ck_llm_models_name_not_empty"),
        CheckConstraint("length(slug) > 0", name="ck_llm_models_slug_not_empty"),
        Index("idx_llm_models_provider_id", "provider_id"),
        Index("idx_llm_models_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<LLMModel(id={self.id}, slug={self.slug!r})>"


class AgentModelConfig(Base, UUIDMixin, TimestampMixin):
    """Binding between an agent and its chosen model configuration."""

    __tablename__ = "agent_model_configs"

    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("llm_providers.id", ondelete="RESTRICT", name="fk_agent_model_configs_provider_id"),
        nullable=False,
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("llm_models.id", ondelete="RESTRICT", name="fk_agent_model_configs_model_id"),
        nullable=False,
    )
    temperature: Mapped[float | None] = mapped_column(nullable=True)
    max_tokens: Mapped[int | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    __table_args__ = (
        UniqueConstraint("agent_name", name="uq_agent_model_configs_agent_name"),
        CheckConstraint("length(agent_name) > 0", name="ck_agent_model_configs_agent_name_not_empty"),
        Index("idx_agent_model_configs_agent_name", "agent_name"),
        Index("idx_agent_model_configs_provider_id", "provider_id"),
        Index("idx_agent_model_configs_model_id", "model_id"),
    )

    def __repr__(self) -> str:
        return f"<AgentModelConfig(agent={self.agent_name!r}, provider={self.provider_id})>"
