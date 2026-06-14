"""Default extraction schemas seeded on first startup."""

import logging
import uuid

from sqlalchemy import select

from app.db.models.extraction import ExtractionSchema
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
