# Phase 2A: Document Model + Migration — Implementation Plan

## Task
Create Document SQLAlchemy model, Pydantic schemas, and Alembic migration.

## Dependencies
Phase 1B (database setup)

## Files to Create/Update

### 1. `backend/app/db/models/document.py`
- Document model with all columns from DATABASE_SCHEMA.md
- Relationships: user, pages, chunks, extracted_fields, risk_items, tasks
- Status enum: uploaded, parsing, parsed, failed, deleted

### 2. `backend/app/db/models/document_page.py`
- DocumentPage model
- Columns: document_id (FK), page_number, ocr_text, raw_text, confidence, width, height, metadata

### 3. `backend/app/db/models/document_chunk.py`
- DocumentChunk model
- Columns: document_id (FK), page_number, chunk_index, text, token_count, embedding_id (Qdrant point ID), metadata

### 4. `backend/app/api/schemas/documents.py`
- DocumentCreate (filename, mime_type, file_size_bytes)
- DocumentResponse (all fields + timestamps)
- DocumentListResponse (paginated)
- DocumentUpdate (filename, metadata)
- DocumentStatus enum

### 5. `backend/alembic/versions/002_document_tables.py`
- Migration for documents, document_pages, document_chunks
- All indexes and constraints

## Acceptance Criteria
- [ ] Document model matches DATABASE_SCHEMA.md
- [ ] Pydantic schemas validate correctly
- [ ] Migration runs successfully
- [ ] Model relationships work (document.pages, document.chunks)

## Test Requirements
- `tests/db/models/test_document.py` — model instantiation
- `tests/api/schemas/test_documents.py` — schema validation
