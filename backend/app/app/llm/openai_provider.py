"""OpenAI-compatible LLM provider.

Supports:
- OpenAI API (gpt-4o, gpt-4-turbo, etc.)
- Any OpenAI-compatible proxy (vLLM, Ollama, etc.)
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from app.llm.base import LLMProvider, LLMResponse, Message, StreamEvent

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible LLM provider.

    Args:
        api_key: API key for authentication.
        base_url: Base URL for the API.
        model: Default model name.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o",
        max_tokens: int = 4096,
        timeout: int = 60,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._max_tokens = max_tokens
        self._timeout = timeout
        self._client: object | None = None

    def _get_client(self) -> object:
        """Lazy-init the OpenAI client."""
        if self._client is None:
            try:
                import openai

                self._client = openai.AsyncOpenAI(
                    api_key=self._api_key,
                    base_url=self._base_url,
                    timeout=self._timeout,
                )
            except ImportError:
                raise ImportError(
                    "openai package is required. Install with: pip install openai"
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
        """Send a chat request to the OpenAI-compatible API."""
        client = self._get_client()
        model = model or self._model

        api_messages: list[dict] = []
        if system:
            api_messages.append({"role": "system", "content": system})
        for m in messages:
            api_messages.append({"role": m.role, "content": m.content})

        try:
            response = await client.chat.completions.create(  # type: ignore
                model=model,
                messages=api_messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            choice = response.choices[0]
            return LLMResponse(
                content=choice.message.content or "",
                model=response.model,
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
                finish_reason=choice.finish_reason,
            )
        except Exception as exc:
            logger.error("OpenAI API error: %s", exc)
            raise

    async def chat_stream(
        self,
        messages: list[Message],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
        system: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream a chat response from the OpenAI-compatible API."""
        client = self._get_client()
        model = model or self._model

        api_messages: list[dict] = []
        if system:
            api_messages.append({"role": "system", "content": system})
        for m in messages:
            api_messages.append({"role": m.role, "content": m.content})

        try:
            stream = await client.chat.completions.create(  # type: ignore
                model=model,
                messages=api_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield StreamEvent(
                        type="text", content=chunk.choices[0].delta.content
                    )
                if chunk.choices and chunk.choices[0].finish_reason:
                    yield StreamEvent(type="done")
        except Exception as exc:
            logger.error("OpenAI streaming error: %s", exc)
            raise

    def count_tokens(self, text: str) -> int:
        """Estimate token count (rough: ~4 chars per token)."""
        return len(text) // 4

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def default_model(self) -> str:
        return self._model
