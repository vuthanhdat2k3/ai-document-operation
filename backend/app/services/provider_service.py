"""CRUD service for LLM Provider, Model, and Agent Model Configuration."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.provider import LLMProvider, LLMModel, AgentModelConfig

logger = logging.getLogger(__name__)

# ── Provider CRUD ───────────────────────────────────────────────────────────


async def list_providers(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    include_inactive: bool = False,
) -> tuple[list[LLMProvider], int]:
    """List LLM providers with pagination."""
    query = select(LLMProvider)
    if not include_inactive:
        query = query.where(LLMProvider.is_active.is_(True))
    query = query.order_by(LLMProvider.created_at.desc())

    # Count
    count_query = select(LLMProvider.id)
    if not include_inactive:
        count_query = count_query.where(LLMProvider.is_active.is_(True))
    total_result = await db.execute(count_query)
    total = len(total_result.all())

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    providers = list(result.scalars().all())
    return providers, total


async def get_provider(db: AsyncSession, provider_id: uuid.UUID) -> LLMProvider | None:
    """Get a single provider by ID."""
    result = await db.execute(select(LLMProvider).where(LLMProvider.id == provider_id))
    return result.scalar_one_or_none()


async def get_provider_by_slug(db: AsyncSession, slug: str) -> LLMProvider | None:
    """Get a single provider by slug."""
    result = await db.execute(select(LLMProvider).where(LLMProvider.slug == slug))
    return result.scalar_one_or_none()


async def create_provider(db: AsyncSession, data: dict[str, Any]) -> LLMProvider:
    """Create a new LLM provider."""
    provider = LLMProvider(
        id=uuid.uuid4(),
        name=data["name"],
        slug=data["slug"],
        description=data.get("description"),
        api_base_url=data.get("api_base_url"),
        api_key=data.get("api_key"),
        config_schema=data.get("config_schema"),
        is_active=data.get("is_active", True),
    )
    db.add(provider)
    await db.flush()
    logger.info("Created LLM provider: %s (slug=%s)", provider.name, provider.slug)
    return provider


async def update_provider(
    db: AsyncSession, provider_id: uuid.UUID, data: dict[str, Any]
) -> LLMProvider | None:
    """Update an existing LLM provider."""
    provider = await get_provider(db, provider_id)
    if provider is None:
        return None

    for field in ("name", "description", "api_base_url", "api_key", "config_schema", "is_active"):
        if field in data:
            setattr(provider, field, data[field])

    await db.flush()
    logger.info("Updated LLM provider: %s", provider.name)
    return provider


async def delete_provider(db: AsyncSession, provider_id: uuid.UUID) -> bool:
    """Delete an LLM provider (cascades to its models)."""
    provider = await get_provider(db, provider_id)
    if provider is None:
        return False
    await db.delete(provider)
    await db.flush()
    logger.info("Deleted LLM provider: %s", provider.name)
    return True


# ── Model CRUD ──────────────────────────────────────────────────────────────


async def list_models(
    db: AsyncSession,
    provider_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 50,
    include_inactive: bool = False,
) -> tuple[list[LLMModel], int]:
    """List LLM models with optional provider filter."""
    query = select(LLMModel)
    if provider_id is not None:
        query = query.where(LLMModel.provider_id == provider_id)
    if not include_inactive:
        query = query.where(LLMModel.is_active.is_(True))
    query = query.order_by(LLMModel.created_at.desc())

    # Count
    count_query = select(LLMModel.id)
    if provider_id is not None:
        count_query = count_query.where(LLMModel.provider_id == provider_id)
    if not include_inactive:
        count_query = count_query.where(LLMModel.is_active.is_(True))
    total_result = await db.execute(count_query)
    total = len(total_result.all())

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    models = list(result.scalars().all())
    return models, total


async def get_model(db: AsyncSession, model_id: uuid.UUID) -> LLMModel | None:
    """Get a single model by ID."""
    result = await db.execute(select(LLMModel).where(LLMModel.id == model_id))
    return result.scalar_one_or_none()


async def get_model_by_slug(db: AsyncSession, provider_id: uuid.UUID, slug: str) -> LLMModel | None:
    """Get a model by provider_id and slug."""
    result = await db.execute(
        select(LLMModel).where(
            LLMModel.provider_id == provider_id,
            LLMModel.slug == slug,
        )
    )
    return result.scalar_one_or_none()


async def create_model(db: AsyncSession, provider_id: uuid.UUID, data: dict[str, Any]) -> LLMModel:
    """Create a new model under a provider."""
    model = LLMModel(
        id=uuid.uuid4(),
        provider_id=provider_id,
        name=data["name"],
        slug=data["slug"],
        description=data.get("description"),
        max_tokens=data.get("max_tokens"),
        default_temperature=data.get("default_temperature"),
        supports_streaming=data.get("supports_streaming", True),
        supports_thinking=data.get("supports_thinking", False),
        is_active=data.get("is_active", True),
    )
    db.add(model)
    await db.flush()
    logger.info("Created LLM model: %s (slug=%s) for provider %s", model.name, model.slug, provider_id)
    return model


async def update_model(
    db: AsyncSession, model_id: uuid.UUID, data: dict[str, Any]
) -> LLMModel | None:
    """Update an existing model."""
    model = await get_model(db, model_id)
    if model is None:
        return None

    for field in (
        "name", "description", "max_tokens", "default_temperature",
        "supports_streaming", "supports_thinking", "is_active",
    ):
        if field in data:
            setattr(model, field, data[field])

    await db.flush()
    logger.info("Updated LLM model: %s", model.name)
    return model


async def delete_model(db: AsyncSession, model_id: uuid.UUID) -> bool:
    """Delete a model."""
    model = await get_model(db, model_id)
    if model is None:
        return False
    await db.delete(model)
    await db.flush()
    logger.info("Deleted LLM model: %s", model.name)
    return True


# ── Agent Model Config CRUD ─────────────────────────────────────────────────


async def get_agent_config(db: AsyncSession, agent_name: str) -> AgentModelConfig | None:
    """Get the active model config for an agent."""
    result = await db.execute(
        select(AgentModelConfig).where(
            AgentModelConfig.agent_name == agent_name,
            AgentModelConfig.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def set_agent_config(
    db: AsyncSession, agent_name: str, data: dict[str, Any]
) -> AgentModelConfig:
    """Create or update an agent's model configuration."""
    existing = await get_agent_config(db, agent_name)

    if existing:
        for field in ("provider_id", "model_id", "temperature", "max_tokens", "is_active"):
            if field in data:
                setattr(existing, field, data[field])
        await db.flush()
        logger.info("Updated agent model config: %s", agent_name)
        return existing

    config = AgentModelConfig(
        id=uuid.uuid4(),
        agent_name=agent_name,
        provider_id=data["provider_id"],
        model_id=data["model_id"],
        temperature=data.get("temperature"),
        max_tokens=data.get("max_tokens"),
        is_active=data.get("is_active", True),
    )
    db.add(config)
    await db.flush()
    logger.info("Created agent model config: %s", agent_name)
    return config


async def delete_agent_config(db: AsyncSession, agent_name: str) -> bool:
    """Delete an agent's model configuration."""
    existing = await get_agent_config(db, agent_name)
    if existing is None:
        return False
    await db.delete(existing)
    await db.flush()
    logger.info("Deleted agent model config: %s", agent_name)
    return True
