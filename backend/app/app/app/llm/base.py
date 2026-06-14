"""Abstract LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class Message:
    """A chat message."""

    role: str  # "user" | "assistant" | "system"
    content: str


@dataclass
class LLMResponse:
    """Response from an LLM call."""

    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    thinking: str | None = None
    finish_reason: str | None = None
    raw: dict | None = None


@dataclass
class StreamEvent:
    """A streaming event from an LLM."""

    type: str  # "thinking" | "text" | "done"
    content: str = ""


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
        system: str | None = None,
    ) -> LLMResponse:
        """Send a chat request and return the full response."""
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[Message],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
        system: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Send a chat request and stream the response."""
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Return the default model name."""
        ...
