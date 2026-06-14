# Phase 1B: Database + Alembic — Implementation Plan

## Task
Setup SQLAlchemy async engine, Alembic migrations, and initial database schema.

## Dependencies
Phase 1A (backend scaffolding must exist)

## Files to Create

### 1. `backend/alembic.ini`
- sqlalchemy.url = driver://user:pass@localhost/dbname (overridden in env.py)
- script_location = alembic

### 2. `backend/alembic/env.py`
- Import all models for autogenerate
- Use async engine
- Configure target_metadata
- Run migrations in transaction

### 3. `backend/alembic/script.py.mako`
- Standard Alembic migration template

### 4. `backend/alembic/versions/001_initial_schema.py`
- Create tables: users, documents, document_pages, document_chunks, extraction_schemas, extracted_fields, risk_items, tasks, reports, agent_sessions, agent_steps, tool_calls, eval_datasets, eval_runs, audit_logs
- All columns, constraints, indexes per DATABASE_SCHEMA.md
- Proper downgrade() function

### 5. `backend/app/db/models/__init__.py`
- Import all models

### 6. `backend/app/db/models/user.py`
- User SQLAlchemy model

### 7. `backend/app/db/models/document.py`
- Document, DocumentPage, DocumentChunk models

### 8. `backend/app/db/models/extraction.py`
- ExtractionSchema, ExtractedField models

### 9. `backend/app/db/models/risk.py`
- RiskItem model

### 10. `backend/app/db/models/task.py`
- Task model

### 11. `backend/app/db/models/report.py`
- Report model

### 12. `backend/app/db/models/agent.py`
- AgentSession, AgentStep, ToolCall models

### 13. `backend/app/db/models/eval.py`
- EvalDataset, EvalRun models

### 14. `backend/app/db/models/audit.py`
- AuditLog model

## Model Requirements
- All models inherit from Base + UUIDMixin + TimestampMixin
- Soft delete where appropriate (users, documents, tasks)
- Proper relationships with foreign keys
- Proper indexes per DATABASE_SCHEMA.md
- Check constraints for status enums
- JSONB columns for flexible data (preferences, classification, metadata)

## Acceptance Criteria
- [ ] `alembic upgrade head` creates all tables
- [ ] `alembic downgrade base` drops all tables
- [ ] All models importable without circular dependencies
- [ ] Models match DATABASE_SCHEMA.md specification

## Test Requirements
- `tests/db/test_models.py` — model instantiation and validation
- `tests/db/test_migrations.py` — migration up/down cycle
