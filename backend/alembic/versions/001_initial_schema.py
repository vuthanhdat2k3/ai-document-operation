"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-11 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("preferences", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint("ck_users_role_valid", "users", "role IN ('admin', 'operator', 'analyst', 'viewer')")
    op.create_index("idx_users_email", "users", ["email"], postgresql_where="deleted_at IS NULL")
    op.create_index("idx_users_role_active", "users", ["role", "is_active"], postgresql_where="deleted_at IS NULL")
    op.create_index("idx_users_deleted_at", "users", ["deleted_at"], postgresql_where="deleted_at IS NOT NULL")

    # --- documents ---
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=False),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("storage_backend", sa.String(50), nullable=False, server_default="local"),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="uploaded"),
        sa.Column("document_type", sa.String(100), nullable=True),
        sa.Column("classification", JSONB, nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_documents_user_id", ondelete="RESTRICT"),
    )
    op.create_check_constraint(
        "ck_documents_status_valid", "documents",
        "status IN ('uploaded', 'queued', 'processing', 'ocr_complete', "
        "'extraction_complete', 'reviewed', 'completed', 'failed', 'archived')"
    )
    op.create_check_constraint("ck_documents_file_size_positive", "documents", "file_size_bytes > 0")
    op.create_check_constraint("ck_documents_page_count_positive", "documents", "page_count IS NULL OR page_count > 0")
    op.create_index("idx_documents_user_id", "documents", ["user_id"], postgresql_where="deleted_at IS NULL")
    op.create_index("idx_documents_user_id_status", "documents", ["user_id", "status"], postgresql_where="deleted_at IS NULL")
    op.create_index("idx_documents_status", "documents", ["status"], postgresql_where="deleted_at IS NULL")
    op.create_index("idx_documents_document_type", "documents", ["document_type"], postgresql_where="deleted_at IS NULL")
    op.create_index("idx_documents_uploaded_at", "documents", [sa.text("uploaded_at DESC")])
    op.create_index("idx_documents_checksum", "documents", ["checksum_sha256"])
    op.create_index("idx_documents_deleted_at", "documents", ["deleted_at"], postgresql_where="deleted_at IS NOT NULL")

    # --- document_pages ---
    op.create_table(
        "document_pages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("page_number", sa.Integer, nullable=False),
        sa.Column("ocr_text", sa.Text, nullable=True),
        sa.Column("ocr_confidence", sa.REAL, nullable=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("width_px", sa.Integer, nullable=True),
        sa.Column("height_px", sa.Integer, nullable=True),
        sa.Column("dpi", sa.Integer, nullable=True),
        sa.Column("image_storage_path", sa.String(1000), nullable=True),
        sa.Column("ocr_engine", sa.String(50), nullable=True),
        sa.Column("ocr_raw_output", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name="fk_document_pages_document_id", ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", "page_number", name="uq_document_pages_doc_page"),
    )
    op.create_check_constraint("ck_document_pages_page_number_positive", "document_pages", "page_number > 0")
    op.create_check_constraint(
        "ck_document_pages_confidence_range", "document_pages",
        "ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 1)"
    )
    op.create_check_constraint(
        "ck_document_pages_dimensions_positive", "document_pages",
        "(width_px IS NULL OR width_px > 0) AND (height_px IS NULL OR height_px > 0) AND (dpi IS NULL OR dpi > 0)"
    )
    op.create_index("idx_document_pages_document_id", "document_pages", ["document_id"])
    op.create_index("idx_document_pages_doc_page", "document_pages", ["document_id", "page_number"])
    op.create_index(
        "idx_document_pages_confidence", "document_pages", ["ocr_confidence"],
        postgresql_where="ocr_confidence IS NOT NULL AND ocr_confidence < 0.7"
    )

    # --- document_chunks ---
    op.create_table(
        "document_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("embedding_dim", sa.Integer, nullable=True),
        sa.Column("embedding_ref", sa.String(500), nullable=True),
        sa.Column("chunk_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name="fk_document_chunks_document_id", ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_doc_chunk"),
    )
    op.create_check_constraint("ck_document_chunks_chunk_index_positive", "document_chunks", "chunk_index >= 0")
    op.create_check_constraint("ck_document_chunks_token_count_positive", "document_chunks", "token_count IS NULL OR token_count > 0")
    op.create_check_constraint("ck_document_chunks_embedding_dim_positive", "document_chunks", "embedding_dim IS NULL OR embedding_dim > 0")
    op.create_index("idx_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("idx_document_chunks_doc_chunk", "document_chunks", ["document_id", "chunk_index"])
    op.create_index(
        "idx_document_chunks_embedding_model", "document_chunks", ["embedding_model"],
        postgresql_where="embedding_model IS NOT NULL"
    )

    # --- extraction_schemas ---
    op.create_table(
        "extraction_schemas",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("document_type", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("fields_schema", JSONB, nullable=False),
        sa.Column("prompt_template", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_extraction_schemas_created_by", ondelete="SET NULL"),
        sa.UniqueConstraint("name", "version", name="uq_extraction_schemas_name_version"),
    )
    op.create_check_constraint("ck_extraction_schemas_version_positive", "extraction_schemas", "version > 0")
    op.create_index("idx_extraction_schemas_document_type", "extraction_schemas", ["document_type"], postgresql_where="deleted_at IS NULL")
    op.create_index(
        "idx_extraction_schemas_active", "extraction_schemas", ["is_active"],
        postgresql_where="deleted_at IS NULL AND is_active = TRUE"
    )

    # --- extracted_fields ---
    op.create_table(
        "extracted_fields",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("schema_id", UUID(as_uuid=True), nullable=False),
        sa.Column("field_name", sa.String(255), nullable=False),
        sa.Column("field_value", JSONB, nullable=True),
        sa.Column("raw_text", sa.Text, nullable=True),
        sa.Column("confidence", sa.REAL, nullable=True),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("bounding_box", JSONB, nullable=True),
        sa.Column("extraction_model", sa.String(100), nullable=True),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("verified_by", UUID(as_uuid=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name="fk_extracted_fields_document_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["schema_id"], ["extraction_schemas.id"], name="fk_extracted_fields_schema_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], name="fk_extracted_fields_verified_by", ondelete="SET NULL"),
        sa.UniqueConstraint("document_id", "schema_id", "field_name", name="uq_extracted_fields_doc_schema_field"),
    )
    op.create_check_constraint(
        "ck_extracted_fields_confidence_range", "extracted_fields",
        "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)"
    )
    op.create_check_constraint(
        "ck_extracted_fields_verified_consistency", "extracted_fields",
        "(is_verified = FALSE AND verified_by IS NULL AND verified_at IS NULL) OR "
        "(is_verified = TRUE AND verified_by IS NOT NULL AND verified_at IS NOT NULL)"
    )
    op.create_index("idx_extracted_fields_document_id", "extracted_fields", ["document_id"])
    op.create_index("idx_extracted_fields_schema_id", "extracted_fields", ["schema_id"])
    op.create_index("idx_extracted_fields_doc_schema", "extracted_fields", ["document_id", "schema_id"])
    op.create_index(
        "idx_extracted_fields_unverified", "extracted_fields", ["document_id"],
        postgresql_where="is_verified = FALSE AND confidence < 0.8"
    )

    # --- risk_items ---
    op.create_table(
        "risk_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("evidence", JSONB, nullable=True),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="open"),
        sa.Column("resolution", sa.Text, nullable=True),
        sa.Column("resolved_by", UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("detected_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name="fk_risk_items_document_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], name="fk_risk_items_resolved_by", ondelete="SET NULL"),
    )
    op.create_check_constraint(
        "ck_risk_items_severity_valid", "risk_items",
        "severity IN ('critical', 'high', 'medium', 'low', 'info')"
    )
    op.create_check_constraint(
        "ck_risk_items_status_valid", "risk_items",
        "status IN ('open', 'in_review', 'resolved', 'dismissed', 'false_positive')"
    )
    op.create_index("idx_risk_items_document_id", "risk_items", ["document_id"], postgresql_where="deleted_at IS NULL")
    op.create_index(
        "idx_risk_items_severity", "risk_items", ["severity"],
        postgresql_where="deleted_at IS NULL AND status = 'open'"
    )
    op.create_index("idx_risk_items_status", "risk_items", ["status"], postgresql_where="deleted_at IS NULL")
    op.create_index(
        "idx_risk_items_doc_severity", "risk_items", ["document_id", "severity"],
        postgresql_where="deleted_at IS NULL"
    )
    op.create_index("idx_risk_items_category", "risk_items", ["category"], postgresql_where="deleted_at IS NULL")

    # --- tasks ---
    op.create_table(
        "tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", UUID(as_uuid=True), nullable=True),
        sa.Column("session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_to", UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("task_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name="fk_tasks_document_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], name="fk_tasks_assigned_to", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"], name="fk_tasks_session_id", ondelete="SET NULL"),
    )
    op.create_check_constraint(
        "ck_tasks_priority_valid", "tasks",
        "priority IN ('critical', 'high', 'medium', 'low')"
    )
    op.create_check_constraint(
        "ck_tasks_status_valid", "tasks",
        "status IN ('pending', 'in_progress', 'completed', 'cancelled', 'blocked')"
    )
    op.create_index(
        "idx_tasks_assigned_to", "tasks", ["assigned_to"],
        postgresql_where="deleted_at IS NULL AND status NOT IN ('completed', 'cancelled')"
    )
    op.create_index("idx_tasks_document_id", "tasks", ["document_id"], postgresql_where="deleted_at IS NULL")
    op.create_index("idx_tasks_status", "tasks", ["status"], postgresql_where="deleted_at IS NULL")
    op.create_index("idx_tasks_priority_status", "tasks", ["priority", "status"], postgresql_where="deleted_at IS NULL")
    op.create_index(
        "idx_tasks_due_date", "tasks", ["due_date"],
        postgresql_where="deleted_at IS NULL AND status NOT IN ('completed', 'cancelled')"
    )

    # --- reports ---
    op.create_table(
        "reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=True),
        sa.Column("session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("report_type", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("format", sa.String(20), nullable=False, server_default="json"),
        sa.Column("storage_path", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="generated"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_reports_user_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name="fk_reports_document_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"], name="fk_reports_session_id", ondelete="SET NULL"),
    )
    op.create_check_constraint(
        "ck_reports_format_valid", "reports",
        "format IN ('json', 'pdf', 'html', 'csv', 'markdown')"
    )
    op.create_check_constraint(
        "ck_reports_status_valid", "reports",
        "status IN ('generating', 'generated', 'failed', 'expired')"
    )
    op.create_index("idx_reports_user_id", "reports", ["user_id"], postgresql_where="deleted_at IS NULL")
    op.create_index("idx_reports_document_id", "reports", ["document_id"], postgresql_where="deleted_at IS NULL")
    op.create_index("idx_reports_session_id", "reports", ["session_id"], postgresql_where="deleted_at IS NULL")
    op.create_index("idx_reports_type", "reports", ["report_type"], postgresql_where="deleted_at IS NULL")
    op.create_index("idx_reports_generated_at", "reports", [sa.text("generated_at DESC")])

    # --- agent_sessions ---
    op.create_table(
        "agent_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=True),
        sa.Column("agent_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="running"),
        sa.Column("input_data", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output_data", JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("total_tokens", sa.Integer, nullable=True),
        sa.Column("total_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_agent_sessions_user_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name="fk_agent_sessions_document_id", ondelete="SET NULL"),
    )
    op.create_check_constraint(
        "ck_agent_sessions_status_valid", "agent_sessions",
        "status IN ('running', 'completed', 'failed', 'cancelled', 'timeout')"
    )
    op.create_check_constraint("ck_agent_sessions_tokens_positive", "agent_sessions", "total_tokens IS NULL OR total_tokens >= 0")
    op.create_check_constraint("ck_agent_sessions_cost_positive", "agent_sessions", "total_cost_usd IS NULL OR total_cost_usd >= 0")
    op.create_index("idx_agent_sessions_user_id", "agent_sessions", ["user_id"])
    op.create_index("idx_agent_sessions_document_id", "agent_sessions", ["document_id"])
    op.create_index("idx_agent_sessions_status", "agent_sessions", ["status"])
    op.create_index("idx_agent_sessions_agent_type", "agent_sessions", ["agent_type"])
    op.create_index("idx_agent_sessions_started_at", "agent_sessions", [sa.text("started_at DESC")])

    # --- agent_steps ---
    op.create_table(
        "agent_steps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("step_index", sa.Integer, nullable=False),
        sa.Column("step_type", sa.String(50), nullable=False),
        sa.Column("action", sa.String(255), nullable=True),
        sa.Column("input_data", JSONB, nullable=True),
        sa.Column("output_data", JSONB, nullable=True),
        sa.Column("reasoning", sa.Text, nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="completed"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"], name="fk_agent_steps_session_id", ondelete="CASCADE"),
        sa.UniqueConstraint("session_id", "step_index", name="uq_agent_steps_session_step"),
    )
    op.create_check_constraint("ck_agent_steps_step_index_positive", "agent_steps", "step_index >= 0")
    op.create_check_constraint(
        "ck_agent_steps_step_type_valid", "agent_steps",
        "step_type IN ('reasoning', 'tool_call', 'observation', 'planning', 'decision', 'error')"
    )
    op.create_check_constraint(
        "ck_agent_steps_status_valid", "agent_steps",
        "status IN ('completed', 'failed', 'skipped')"
    )
    op.create_check_constraint("ck_agent_steps_duration_positive", "agent_steps", "duration_ms IS NULL OR duration_ms >= 0")
    op.create_check_constraint("ck_agent_steps_tokens_positive", "agent_steps", "tokens_used IS NULL OR tokens_used >= 0")
    op.create_index("idx_agent_steps_session_id", "agent_steps", ["session_id"])
    op.create_index("idx_agent_steps_session_step", "agent_steps", ["session_id", "step_index"])
    op.create_index("idx_agent_steps_type", "agent_steps", ["step_type"])

    # --- tool_calls ---
    op.create_table(
        "tool_calls",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_step_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.String(255), nullable=False),
        sa.Column("tool_input", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("tool_output", JSONB, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["agent_step_id"], ["agent_steps.id"], name="fk_tool_calls_agent_step_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"], name="fk_tool_calls_session_id", ondelete="CASCADE"),
    )
    op.create_check_constraint(
        "ck_tool_calls_status_valid", "tool_calls",
        "status IN ('success', 'failed', 'timeout', 'skipped')"
    )
    op.create_check_constraint("ck_tool_calls_duration_positive", "tool_calls", "duration_ms IS NULL OR duration_ms >= 0")
    op.create_check_constraint("ck_tool_calls_retry_count_positive", "tool_calls", "retry_count >= 0")
    op.create_index("idx_tool_calls_agent_step_id", "tool_calls", ["agent_step_id"])
    op.create_index("idx_tool_calls_session_id", "tool_calls", ["session_id"])
    op.create_index("idx_tool_calls_tool_name", "tool_calls", ["tool_name"])
    op.create_index("idx_tool_calls_session_tool", "tool_calls", ["session_id", "tool_name"])

    # --- eval_datasets ---
    op.create_table(
        "eval_datasets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("task_type", sa.String(100), nullable=False),
        sa.Column("record_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("storage_path", sa.String(1000), nullable=True),
        sa.Column("schema_definition", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_eval_datasets_created_by", ondelete="SET NULL"),
        sa.UniqueConstraint("name", "version", name="uq_eval_datasets_name_version"),
    )
    op.create_check_constraint("ck_eval_datasets_version_positive", "eval_datasets", "version > 0")
    op.create_check_constraint("ck_eval_datasets_record_count_non_negative", "eval_datasets", "record_count >= 0")
    op.create_index("idx_eval_datasets_task_type", "eval_datasets", ["task_type"], postgresql_where="deleted_at IS NULL")
    op.create_index(
        "idx_eval_datasets_active", "eval_datasets", ["is_active"],
        postgresql_where="deleted_at IS NULL AND is_active = TRUE"
    )

    # --- eval_runs ---
    op.create_table(
        "eval_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("dataset_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("run_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="running"),
        sa.Column("metrics", JSONB, nullable=True),
        sa.Column("config", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_records", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["dataset_id"], ["eval_datasets.id"], name="fk_eval_runs_dataset_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"], name="fk_eval_runs_session_id", ondelete="SET NULL"),
    )
    op.create_check_constraint(
        "ck_eval_runs_status_valid", "eval_runs",
        "status IN ('running', 'completed', 'failed', 'cancelled')"
    )
    op.create_check_constraint("ck_eval_runs_error_count_non_negative", "eval_runs", "error_count >= 0")
    op.create_check_constraint("ck_eval_runs_total_records_non_negative", "eval_runs", "total_records >= 0")
    op.create_index("idx_eval_runs_dataset_id", "eval_runs", ["dataset_id"])
    op.create_index("idx_eval_runs_status", "eval_runs", ["status"])
    op.create_index("idx_eval_runs_started_at", "eval_runs", [sa.text("started_at DESC")])

    # --- audit_logs ---
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("old_values", JSONB, nullable=True),
        sa.Column("new_values", JSONB, nullable=True),
        sa.Column("ip_address", INET, nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("request_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_audit_logs_user_id", ondelete="SET NULL"),
    )
    op.create_check_constraint(
        "ck_audit_logs_action_valid", "audit_logs",
        "action IN ('create', 'read', 'update', 'delete', 'login', 'logout', "
        "'login_failed', 'upload', 'download', 'process', 'export', 'import', "
        "'approve', 'reject', 'execute', 'configure')"
    )
    op.create_index("idx_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("idx_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("idx_audit_logs_action", "audit_logs", ["action"])
    op.create_index("idx_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("idx_audit_logs_session_id", "audit_logs", ["session_id"], postgresql_where="session_id IS NOT NULL")
    op.create_index("idx_audit_logs_request_id", "audit_logs", ["request_id"], postgresql_where="request_id IS NOT NULL")


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("eval_runs")
    op.drop_table("eval_datasets")
    op.drop_table("tool_calls")
    op.drop_table("agent_steps")
    op.drop_table("agent_sessions")
    op.drop_table("reports")
    op.drop_table("tasks")
    op.drop_table("risk_items")
    op.drop_table("extracted_fields")
    op.drop_table("extraction_schemas")
    op.drop_table("document_chunks")
    op.drop_table("document_pages")
    op.drop_table("documents")
    op.drop_table("users")
