"""Xiaomi MiMo / Anthropic-compatible LLM provider.

Supports:
- Standard Anthropic API
- Xiaomi MiMo (Anthropic-compatible endpoint)
- Any Anthropic-compatible proxy with custom base_url
- Extended thinking (thinking blocks)
- Streaming with thinking + text deltas
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from app.llm.base import LLMProvider, LLMResponse, Message, StreamEvent

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic-compatible LLM provider (works with Xiaomi MiMo too).

    Args:
        api_key: API key for authentication.
        base_url: Base URL for the API (default: Anthropic, can be Xiaomi).
        model: Default model name.
        max_tokens: Default max tokens.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.anthropic.com",
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        timeout: int = 60,
        enable_thinking: bool = False,
        thinking_budget: int = 1024,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._max_tokens = max_tokens
        self._timeout = timeout
        self._enable_thinking = enable_thinking
        self._thinking_budget = thinking_budget
        self._client: object | None = None

    def _get_client(self) -> object:
        """Lazy-init the Anthropic client."""
        if self._client is None:
            try:
                import anthropic

                self._client = anthropic.AsyncAnthropic(
                    api_key=self._api_key,
                    base_url=self._base_url,
                    timeout=self._timeout,
                )
            except ImportError:
                raise ImportError(
                    "anthropic package is required. Install with: pip install anthropic"
                )
        return self._client

    async def chat(
        self,
        messages: list[Message],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
        system: str | None = None,
    ) -> LLMResponse:
        """Send a chat request to the Anthropic-compatible API."""
        client = self._get_client()
        model = model or self._model

        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }

        if system:
            kwargs["system"] = system

        if self._enable_thinking:
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": self._thinking_budget,
            }
            kwargs["temperature"] = 1.0  # Required when thinking is enabled

        try:
            response = await client.messages.create(**kwargs)  # type: ignore

            content = ""
            thinking = ""
            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "thinking":
                    thinking += block.thinking

            return LLMResponse(
                content=content,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                thinking=thinking if thinking else None,
                finish_reason=response.stop_reason,
            )
        except Exception as exc:
            logger.error("Anthropic API error: %s", exc)
            raise

    async def chat_stream(
        self,
        messages: list[Message],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
        system: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream a chat response from the Anthropic-compatible API."""
        client = self._get_client()
        model = model or self._model

        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }

        if system:
            kwargs["system"] = system

        if self._enable_thinking:
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": self._thinking_budget,
            }
            kwargs["temperature"] = 1.0

        try:
            async with client.messages.stream(**kwargs) as stream:  # type: ignore
                async for event in stream:
                    if event.type == "content_block_delta":
                        delta = event.delta
                        if delta.type == "thinking_delta":
                            yield StreamEvent(type="thinking", content=delta.thinking)
                        elif delta.type == "text_delta":
                            yield StreamEvent(type="text", content=delta.text)
                    elif event.type == "message_stop":
                        yield StreamEvent(type="done")
        except Exception as exc:
            logger.error("Anthropic streaming error: %s", exc)
            raise

    def count_tokens(self, text: str) -> int:
        """Estimate token count (rough: ~4 chars per token)."""
        return len(text) // 4

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def default_model(self) -> str:
        return self._model


class XiaomiProvider(AnthropicProvider):
    """Xiaomi MiMo provider (Anthropic-compatible).

    Usage::

        provider = XiaomiProvider(
            api_key="your-xiaomi-token",
            model="mimo-v2.5-pro",
        )
        response = await provider.chat([Message(role="user", content="Hello")])
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://token-plan-sgp.xiaomimimo.com/anthropic",
        model: str = "mimo-v2.5-pro",
        max_tokens: int = 4096,
        timeout: int = 60,
        enable_thinking: bool = True,
        thinking_budget: int = 1024,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            max_tokens=max_tokens,
            timeout=timeout,
            enable_thinking=enable_thinking,
            thinking_budget=thinking_budget,
        )

    @property
    def provider_name(self) -> str:
        return "xiaomi"
