"""Default extraction schemas and LLM providers/models seeded on first startup."""

import logging
import uuid

from sqlalchemy import select

from app.db.models.extraction import ExtractionSchema
from app.db.models.provider import LLMProvider, LLMModel
from app.db.session import get_session_factory

logger = logging.getLogger(__name__)

DEFAULT_SCHEMAS = [
    {
        "name": "contract",
        "document_type": "contract",
        "version": 1,
        "description": "Standard contract field extraction schema.",
        "fields_schema": {
            "fields": [
                {"name": "contract_title", "type": "string", "required": True},
                {"name": "effective_date", "type": "date", "required": True},
                {"name": "expiration_date", "type": "date", "required": False},
                {"name": "party_a", "type": "string", "required": True},
                {"name": "party_b", "type": "string", "required": True},
                {"name": "total_value", "type": "number", "required": False},
                {"name": "currency", "type": "string", "required": False},
                {"name": "governing_law", "type": "string", "required": False},
                {"name": "termination_clause", "type": "string", "required": False},
            ],
        },
    },
    {
        "name": "invoice",
        "document_type": "invoice",
        "version": 1,
        "description": "Standard invoice field extraction schema.",
        "fields_schema": {
            "fields": [
                {"name": "invoice_number", "type": "string", "required": True},
                {"name": "invoice_date", "type": "date", "required": True},
                {"name": "due_date", "type": "date", "required": False},
                {"name": "vendor_name", "type": "string", "required": True},
                {"name": "customer_name", "type": "string", "required": True},
                {"name": "total_amount", "type": "number", "required": True},
                {"name": "tax_amount", "type": "number", "required": False},
                {"name": "currency", "type": "string", "required": False},
                {"name": "line_items", "type": "array", "required": False},
            ],
        },
    },
    {
        "name": "general",
        "document_type": "general",
        "version": 1,
        "description": "General-purpose document field extraction schema.",
        "fields_schema": {
            "fields": [
                {"name": "title", "type": "string", "required": True},
                {"name": "date", "type": "date", "required": False},
                {"name": "author", "type": "string", "required": False},
                {"name": "summary", "type": "string", "required": False},
                {"name": "key_topics", "type": "array", "required": False},
            ],
        },
    },
]


DEFAULT_PROVIDERS = [
    {
        "slug": "openai",
        "name": "OpenAI",
        "description": "OpenAI API — GPT-4o, GPT-4-turbo, GPT-3.5-turbo, and more",
        "api_base_url": "https://api.openai.com/v1",
        "models": [
            {"name": "GPT-4o", "slug": "gpt-4o", "max_tokens": 16384, "default_temperature": 0.1, "supports_streaming": True, "supports_thinking": False},
            {"name": "GPT-4o Mini", "slug": "gpt-4o-mini", "max_tokens": 16384, "default_temperature": 0.1, "supports_streaming": True, "supports_thinking": False},
            {"name": "GPT-4 Turbo", "slug": "gpt-4-turbo", "max_tokens": 4096, "default_temperature": 0.1, "supports_streaming": True, "supports_thinking": False},
            {"name": "GPT-3.5 Turbo", "slug": "gpt-3.5-turbo", "max_tokens": 4096, "default_temperature": 0.1, "supports_streaming": True, "supports_thinking": False},
            {"name": "O1", "slug": "o1", "max_tokens": 32768, "default_temperature": 1.0, "supports_streaming": False, "supports_thinking": False},
            {"name": "O3 Mini", "slug": "o3-mini", "max_tokens": 32768, "default_temperature": 1.0, "supports_streaming": False, "supports_thinking": False},
        ],
    },
    {
        "slug": "anthropic",
        "name": "Anthropic",
        "description": "Anthropic Claude API — Claude 4 Sonnet, Claude 3.5 Sonnet, Claude 3 Haiku",
        "api_base_url": "https://api.anthropic.com",
        "models": [
            {"name": "Claude 4 Sonnet", "slug": "claude-sonnet-4-20250514", "max_tokens": 8192, "default_temperature": 0.1, "supports_streaming": True, "supports_thinking": True},
            {"name": "Claude 3.5 Sonnet", "slug": "claude-3-5-sonnet-20241022", "max_tokens": 8192, "default_temperature": 0.1, "supports_streaming": True, "supports_thinking": False},
            {"name": "Claude 3.5 Haiku", "slug": "claude-3-5-haiku-20241022", "max_tokens": 8192, "default_temperature": 0.1, "supports_streaming": True, "supports_thinking": False},
            {"name": "Claude 3 Opus", "slug": "claude-3-opus-20240229", "max_tokens": 4096, "default_temperature": 0.1, "supports_streaming": True, "supports_thinking": False},
        ],
    },
    {
        "slug": "xiaomi",
        "name": "Xiaomi MiMo",
        "description": "Xiaomi MiMo API (Anthropic-compatible) — mimo-v2.5-pro",
        "api_base_url": "https://token-plan-sgp.xiaomimimo.com/anthropic",
        "models": [
            {"name": "MiMo 2.5 Pro", "slug": "mimo-v2.5-pro", "max_tokens": 4096, "default_temperature": 0.1, "supports_streaming": True, "supports_thinking": True},
            {"name": "MiMo 2.5 Lite", "slug": "mimo-v2.5-lite", "max_tokens": 4096, "default_temperature": 0.1, "supports_streaming": True, "supports_thinking": False},
        ],
    },
    {
        "slug": "local",
        "name": "Local (Ollama / vLLM)",
        "description": "Local model via OpenAI-compatible API (Ollama, vLLM, LM Studio)",
        "api_base_url": "http://localhost:11434",
        "models": [
            {"name": "Llama 3", "slug": "llama3", "max_tokens": 4096, "default_temperature": 0.1, "supports_streaming": True, "supports_thinking": False},
            {"name": "Llama 3.1 8B", "slug": "llama3.1:8b", "max_tokens": 8192, "default_temperature": 0.1, "supports_streaming": True, "supports_thinking": False},
            {"name": "Llama 3.1 70B", "slug": "llama3.1:70b", "max_tokens": 8192, "default_temperature": 0.1, "supports_streaming": True, "supports_thinking": False},
            {"name": "Qwen 2.5 7B", "slug": "qwen2.5:7b", "max_tokens": 8192, "default_temperature": 0.1, "supports_streaming": True, "supports_thinking": False},
            {"name": "Mistral", "slug": "mistral", "max_tokens": 4096, "default_temperature": 0.1, "supports_streaming": True, "supports_thinking": False},
        ],
    },
    {
        "slug": "openai-compatible",
        "name": "OpenAI Compatible",
        "description": "Generic OpenAI-compatible API (Together AI, Groq, DeepSeek, OpenRouter, etc.)",
        "api_base_url": "",
        "models": [
            {"name": "DeepSeek V3", "slug": "deepseek-chat", "max_tokens": 8192, "default_temperature": 0.1, "supports_streaming": True, "supports_thinking": False},
            {"name": "DeepSeek R1", "slug": "deepseek-reasoner", "max_tokens": 8192, "default_temperature": 0.6, "supports_streaming": True, "supports_thinking": True},
        ],
    },
    {
        "slug": "google-gemini",
        "name": "Google Gemini",
        "description": "Google Gemini API via OpenAI-compatible endpoint",
        "api_base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models": [
            {"name": "Gemini 2.5 Pro", "slug": "gemini-2.5-pro", "max_tokens": 8192, "default_temperature": 0.1, "supports_streaming": True, "supports_thinking": False},
            {"name": "Gemini 2.0 Flash", "slug": "gemini-2.0-flash", "max_tokens": 8192, "default_temperature": 0.1, "supports_streaming": True, "supports_thinking": False},
        ],
    },
]


async def seed_providers_and_models() -> None:
    """Insert default LLM providers and their models if they don't already exist."""
    factory = get_session_factory()
    async with factory() as session:
        for prov_def in DEFAULT_PROVIDERS:
            stmt = select(LLMProvider).where(LLMProvider.slug == prov_def["slug"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing is not None:
                continue

            provider = LLMProvider(
                id=uuid.uuid4(),
                name=prov_def["name"],
                slug=prov_def["slug"],
                description=prov_def.get("description"),
                api_base_url=prov_def.get("api_base_url"),
                api_key=None,
                is_active=True,
            )
            session.add(provider)
            await session.flush()

            for m in prov_def.get("models", []):
                model = LLMModel(
                    id=uuid.uuid4(),
                    provider_id=provider.id,
                    name=m["name"],
                    slug=m["slug"],
                    max_tokens=m.get("max_tokens"),
                    default_temperature=m.get("default_temperature"),
                    supports_streaming=m.get("supports_streaming", True),
                    supports_thinking=m.get("supports_thinking", False),
                    is_active=True,
                )
                session.add(model)

            logger.info("Seeded LLM provider: %s (%d models)", prov_def["name"], len(prov_def.get("models", [])))

        await session.commit()
    logger.info("LLM provider and model seeding complete")


async def seed_extraction_schemas() -> None:
    """Insert default extraction schemas if they don't already exist."""
    factory = get_session_factory()
    async with factory() as session:
        for schema_def in DEFAULT_SCHEMAS:
            stmt = select(ExtractionSchema).where(
                ExtractionSchema.name == schema_def["name"],
                ExtractionSchema.version == schema_def["version"],
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing is None:
                schema = ExtractionSchema(
                    id=uuid.uuid4(),
                    name=schema_def["name"],
                    document_type=schema_def["document_type"],
                    version=schema_def["version"],
                    description=schema_def["description"],
                    fields_schema=schema_def["fields_schema"],
                    is_active=True,
                )
                session.add(schema)
                logger.info("Seeded extraction schema: %s", schema_def["name"])
        await session.commit()
    logger.info("Extraction schema seeding complete")
