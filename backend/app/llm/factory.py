"""LLM provider factory.

Creates the appropriate provider based on database configuration only.
If no provider/model is configured in the database, returns a fallback
that indicates no LLM is available.

Supports providers: openai, anthropic, xiaomi, local, google-gemini, openai-compatible
"""

from __future__ import annotations

import logging

from app.llm.anthropic_provider import AnthropicProvider, XiaomiProvider
from app.llm.base import LLMProvider
from app.llm.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class _FallbackLLM(LLMProvider):
    """Deterministic stub when no real LLM is configured."""

    async def chat(self, messages, model=None, max_tokens=4096, temperature=0.1, system=None):
        from app.llm.base import LLMResponse
        return LLMResponse(
            content="No LLM provider configured. Please add a provider and model in the Providers page.",
            model="fallback",
        )

    async def chat_stream(self, messages, model=None, max_tokens=4096, temperature=0.1, system=None):
        from app.llm.base import StreamEvent
        yield StreamEvent(type="text", content="No LLM provider configured.")
        yield StreamEvent(type="done")

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    @property
    def provider_name(self) -> str:
        return "fallback"

    @property
    def default_model(self) -> str:
        return "fallback"


async def get_llm_provider_from_db(
    agent_name: str | None = None,
) -> LLMProvider:
    """Create an LLM provider using database configuration.

    Resolves the provider and model from the database exclusively.
    If no DB config is found or the config is incomplete, returns
    ``_FallbackLLM`` — no env var fallback.

    Args:
        agent_name: Agent name to look up model config in ``agent_model_configs``.

    Returns:
        Configured LLMProvider instance, or ``_FallbackLLM`` if unavailable.
    """
    provider_slug: str | None = None
    model_slug: str | None = None
    api_key: str | None = None
    api_base: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None

    # 1. Try to resolve from DB via agent config
    if agent_name:
        try:
            from sqlalchemy import select

            from app.db.models.provider import AgentModelConfig, LLMModel, LLMProvider
            from app.db.session import get_session_factory

            factory = get_session_factory()
            async with factory() as session:
                stmt = (
                    select(AgentModelConfig)
                    .where(
                        AgentModelConfig.agent_name == agent_name,
                        AgentModelConfig.is_active.is_(True),
                    )
                )
                result = await session.execute(stmt)
                config = result.scalar_one_or_none()

                if config:
                    # Resolve provider
                    prov_result = await session.execute(
                        select(LLMProvider).where(LLMProvider.id == config.provider_id)
                    )
                    provider = prov_result.scalar_one_or_none()
                    if provider and provider.is_active:
                        provider_slug = provider.slug
                        api_key = provider.api_key
                        api_base = provider.api_base_url

                        # Resolve model
                        mod_result = await session.execute(
                            select(LLMModel).where(LLMModel.id == config.model_id)
                        )
                        model = mod_result.scalar_one_or_none()
                        if model and model.is_active:
                            model_slug = model.slug
                            max_tokens = config.max_tokens or model.max_tokens
                            temperature = config.temperature or model.default_temperature

        except Exception:
            logger.warning("Failed to resolve LLM from DB for agent '%s'", agent_name)

    # 2. No DB config → fallback
    if not provider_slug or not model_slug:
        return _FallbackLLM()

    # 3. Create provider from DB config with hardcoded defaults
    resolved_max_tokens = max_tokens or 4096
    resolved_timeout = 60

    if provider_slug == "xiaomi":
        if not api_key:
            logger.warning("No API key for xiaomi provider '%s'", provider_slug)
            return _FallbackLLM()
        return XiaomiProvider(
            api_key=api_key,
            base_url=api_base or "",
            model=model_slug,
            max_tokens=resolved_max_tokens,
            timeout=resolved_timeout,
            enable_thinking=True,
            thinking_budget=1024,
        )

    elif provider_slug == "anthropic":
        if not api_key:
            logger.warning("No API key for anthropic provider '%s'", provider_slug)
            return _FallbackLLM()
        return AnthropicProvider(
            api_key=api_key,
            base_url=api_base or "",
            model=model_slug,
            max_tokens=resolved_max_tokens,
            timeout=resolved_timeout,
        )

    elif provider_slug in ("openai", "google-gemini"):
        if not api_key:
            logger.warning("No API key for provider '%s'", provider_slug)
            return _FallbackLLM()
        base_url = api_base
        if not base_url and provider_slug == "google-gemini":
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
        return OpenAIProvider(
            api_key=api_key,
            base_url=base_url or "",
            model=model_slug,
            max_tokens=resolved_max_tokens,
            timeout=resolved_timeout,
        )

    elif provider_slug == "local":
        return OpenAIProvider(
            api_key="not-needed",
            base_url=api_base or "",
            model=model_slug,
            max_tokens=resolved_max_tokens,
            timeout=resolved_timeout,
        )

    elif provider_slug == "openai-compatible":
        api_key_value = api_key or "not-needed"
        return OpenAIProvider(
            api_key=api_key_value,
            base_url=api_base or "",
            model=model_slug,
            max_tokens=resolved_max_tokens,
            timeout=resolved_timeout,
        )

    else:
        logger.info("Unknown provider slug '%s' — treating as openai-compatible", provider_slug)
        api_key_value = api_key or "not-needed"
        return OpenAIProvider(
            api_key=api_key_value,
            base_url=api_base or "",
            model=model_slug,
            max_tokens=resolved_max_tokens,
            timeout=resolved_timeout,
        )


def get_llm_provider(settings=None) -> LLMProvider:
    """Synchronous fallback — always returns _FallbackLLM.

    LLM providers are now resolved exclusively from the database.
    This function exists only for backward compatibility with code
    that has not yet been migrated to ``get_llm_provider_from_db()``.
    """
    return _FallbackLLM()
