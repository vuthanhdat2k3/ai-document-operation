"""LLM provider factory.

Creates the appropriate provider based on settings.
Supported providers: openai, anthropic, xiaomi, local
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.llm.anthropic_provider import AnthropicProvider, XiaomiProvider
from app.llm.base import LLMProvider
from app.llm.openai_provider import OpenAIProvider

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class _FallbackLLM(LLMProvider):
    """Deterministic stub when no real LLM is configured."""

    async def chat(self, messages, model=None, max_tokens=4096, temperature=0.1, system=None):
        from app.llm.base import LLMResponse
        return LLMResponse(
            content="No LLM provider configured. Please set LLM_PROVIDER and API keys in .env",
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


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    """Create an LLM provider based on application settings.

    Args:
        settings: Application settings. Loaded from env if not provided.

    Returns:
        Configured LLMProvider instance.

    Supported providers:
        - ``openai``: OpenAI API (gpt-4o, etc.)
        - ``anthropic``: Anthropic API (claude-3, etc.)
        - ``xiaomi``: Xiaomi MiMo (Anthropic-compatible)
        - ``local``: Local model via OpenAI-compatible API (Ollama, vLLM)
    """
    if settings is None:
        from app.config import get_settings
        settings = get_settings()

    provider = settings.LLM_PROVIDER.lower()
    model = settings.LLM_MODEL
    max_tokens = settings.LLM_MAX_TOKENS
    timeout = settings.LLM_TIMEOUT

    if provider == "xiaomi":
        api_key = settings.XIAOMI_API_KEY or settings.ANTHROPIC_API_KEY or ""
        if not api_key:
            logger.warning("XIAOMI_API_KEY not set, using fallback LLM")
            return _FallbackLLM()
        return XiaomiProvider(
            api_key=api_key,
            base_url=settings.XIAOMI_BASE_URL,
            model=settings.XIAOMI_MODEL,
            max_tokens=max_tokens,
            timeout=timeout,
            enable_thinking=True,
            thinking_budget=1024,
        )

    elif provider == "anthropic":
        api_key = settings.ANTHROPIC_API_KEY or ""
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set, using fallback LLM")
            return _FallbackLLM()
        return AnthropicProvider(
            api_key=api_key,
            base_url=settings.ANTHROPIC_BASE_URL,
            model=model,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    elif provider == "openai":
        api_key = settings.OPENAI_API_KEY or ""
        if not api_key:
            logger.warning("OPENAI_API_KEY not set, using fallback LLM")
            return _FallbackLLM()
        return OpenAIProvider(
            api_key=api_key,
            base_url=settings.OPENAI_API_BASE,
            model=model,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    elif provider == "local":
        return OpenAIProvider(
            api_key="not-needed",
            base_url=settings.LOCAL_LLM_BASE_URL,
            model=model,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    else:
        logger.warning("Unknown LLM_PROVIDER '%s', using fallback", provider)
        return _FallbackLLM()
