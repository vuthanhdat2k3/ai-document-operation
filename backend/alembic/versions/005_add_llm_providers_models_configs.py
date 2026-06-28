"""add llm_providers, llm_models, agent_model_configs tables

Revision ID: 005
Revises: 004
Create Date: 2026-06-28 02:30:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- llm_providers ---
    op.create_table(
        "llm_providers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("api_base_url", sa.String(500), nullable=True),
        sa.Column("api_key", sa.String(500), nullable=True),
        sa.Column("config_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_check_constraint(
        "ck_llm_providers_name_not_empty",
        "llm_providers",
        "length(name) > 0",
    )
    op.create_check_constraint(
        "ck_llm_providers_slug_not_empty",
        "llm_providers",
        "length(slug) > 0",
    )
    op.create_index("idx_llm_providers_slug", "llm_providers", ["slug"])
    op.create_index("idx_llm_providers_active", "llm_providers", ["is_active"])

    # --- llm_models ---
    op.create_table(
        "llm_models",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("default_temperature", sa.Float(), nullable=True),
        sa.Column("supports_streaming", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("supports_thinking", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["llm_providers.id"],
            name="fk_llm_models_provider_id", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_id", "slug", name="uq_llm_models_provider_slug"),
    )
    op.create_check_constraint(
        "ck_llm_models_name_not_empty",
        "llm_models",
        "length(name) > 0",
    )
    op.create_check_constraint(
        "ck_llm_models_slug_not_empty",
        "llm_models",
        "length(slug) > 0",
    )
    op.create_index("idx_llm_models_provider_id", "llm_models", ["provider_id"])
    op.create_index("idx_llm_models_active", "llm_models", ["is_active"])

    # --- agent_model_configs ---
    op.create_table(
        "agent_model_configs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("provider_id", sa.UUID(), nullable=False),
        sa.Column("model_id", sa.UUID(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["llm_providers.id"],
            name="fk_agent_model_configs_provider_id", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"], ["llm_models.id"],
            name="fk_agent_model_configs_model_id", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_name", name="uq_agent_model_configs_agent_name"),
    )
    op.create_check_constraint(
        "ck_agent_model_configs_agent_name_not_empty",
        "agent_model_configs",
        "length(agent_name) > 0",
    )
    op.create_index("idx_agent_model_configs_agent_name", "agent_model_configs", ["agent_name"])
    op.create_index("idx_agent_model_configs_provider_id", "agent_model_configs", ["provider_id"])
    op.create_index("idx_agent_model_configs_model_id", "agent_model_configs", ["model_id"])


def downgrade() -> None:
    op.drop_table("agent_model_configs")
    op.drop_table("llm_models")
    op.drop_table("llm_providers")
