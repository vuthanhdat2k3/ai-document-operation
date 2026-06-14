"""LLM provider abstraction layer.

Supports:
- OpenAI (gpt-4o, gpt-4-turbo, etc.)
- Anthropic (claude-3-opus, claude-3-sonnet, etc.)
- Xiaomi MiMo (Anthropic-compatible API)
- Local models (Ollama, vLLM via OpenAI-compatible API)
"""

from app.llm.base import LLMProvider, LLMResponse, Message
from app.llm.factory import get_llm_provider

__all__ = ["LLMProvider", "LLMResponse", "Message", "get_llm_provider"]
