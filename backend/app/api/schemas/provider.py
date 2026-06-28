"""Pydantic schemas for LLM Provider, Model, and Agent Model Config API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.common import PaginatedResponse


# ── Provider ────────────────────────────────────────────────────────────────

class ProviderCreate(BaseModel):
    """Request schema for creating a new LLM provider."""

    name: str = Field(..., min_length=1, max_length=100, description="Display name")
    slug: str = Field(..., min_length=1, max_length=100, description="Unique slug identifier")
    description: str | None = Field(None, description="Optional description")
    api_base_url: str | None = Field(None, max_length=500, description="Default API base URL")
    api_key: str | None = Field(None, max_length=500, description="API key (stored encrypted in production)")
    config_schema: dict | None = Field(None, description="JSON Schema for provider-specific config")
    is_active: bool = Field(default=True)


class ProviderUpdate(BaseModel):
    """Request schema for updating an LLM provider."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    api_base_url: str | None = Field(None, max_length=500)
    api_key: str | None = Field(None, max_length=500)
    config_schema: dict | None = None
    is_active: bool | None = None


class ProviderTestRequest(BaseModel):
    """Request schema for testing a provider connection."""

    api_base_url: str = Field(..., min_length=1, description="Base URL to test")
    api_key: str | None = Field(None, description="Optional API key")
    provider_slug: str | None = Field(None, description="Hint for test method (openai-compatible, anthropic, etc.)")


class ProviderTestResponse(BaseModel):
    """Response from a provider connection test."""

    success: bool
    message: str
    latency_ms: int | None = None


class ProviderResponse(BaseModel):
    """Response schema for a single LLM provider."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    api_base_url: str | None = None
    config_schema: dict | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProviderDetailResponse(ProviderResponse):
    """Extended provider response with models."""

    models: list[ModelResponse] = Field(default_factory=list)


ProviderListResponse = PaginatedResponse[ProviderResponse]


# ── Model ───────────────────────────────────────────────────────────────────

class ModelCreate(BaseModel):
    """Request schema for creating a new model under a provider."""

    name: str = Field(..., min_length=1, max_length=200, description="Display name (e.g. GPT-4o)")
    slug: str = Field(..., min_length=1, max_length=200, description="API model identifier (e.g. gpt-4o)")
    description: str | None = Field(None, description="Optional description")
    max_tokens: int | None = Field(None, ge=1, description="Max output tokens supported")
    default_temperature: float | None = Field(None, ge=0.0, le=2.0)
    supports_streaming: bool = Field(default=True)
    supports_thinking: bool = Field(default=False)
    is_active: bool = Field(default=True)


class ModelUpdate(BaseModel):
    """Request schema for updating a model."""

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    max_tokens: int | None = Field(None, ge=1)
    default_temperature: float | None = Field(None, ge=0.0, le=2.0)
    supports_streaming: bool | None = None
    supports_thinking: bool | None = None
    is_active: bool | None = None


class ModelResponse(BaseModel):
    """Response schema for a single LLM model."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    provider_id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    max_tokens: int | None = None
    default_temperature: float | None = None
    supports_streaming: bool
    supports_thinking: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


ModelListResponse = PaginatedResponse[ModelResponse]


# ── Model Test ───────────────────────────────────────────────────────────────

class ModelTestRequest(BaseModel):
    """Request schema for testing a model slug on a provider."""

    provider_id: uuid.UUID = Field(..., description="Provider ID to test against")
    model_slug: str = Field(..., min_length=1, description="Model slug/ID to look for (e.g. gpt-4o)")


class ModelTestResponse(BaseModel):
    """Response from a model existence test."""

    success: bool
    message: str
    latency_ms: int | None = None
    available_models: list[str] | None = Field(None, description="List of available model IDs on the provider")


# ── Agent Model Config ──────────────────────────────────────────────────────

class AgentModelConfigCreate(BaseModel):
    """Request schema for setting an agent's model configuration."""

    provider_id: uuid.UUID = Field(..., description="Provider ID")
    model_id: uuid.UUID = Field(..., description="Model ID")
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=1)
    is_active: bool = Field(default=True)


class AgentModelConfigUpdate(BaseModel):
    """Request schema for updating an agent's model configuration."""

    provider_id: uuid.UUID | None = None
    model_id: uuid.UUID | None = None
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=1)
    is_active: bool | None = None


class AgentModelConfigResponse(BaseModel):
    """Response schema for an agent's model configuration."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    agent_name: str
    provider_id: uuid.UUID
    model_id: uuid.UUID
    temperature: float | None = None
    max_tokens: int | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AgentModelConfigDetailResponse(AgentModelConfigResponse):
    """Extended response with resolved provider and model names."""

    provider_name: str = ""
    model_name: str = ""
    model_slug: str = ""
