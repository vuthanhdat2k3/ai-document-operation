# Phase 3B: Background Worker + Parse API — Implementation Plan

## Task
Implement ARQ background worker for document processing and parse API endpoints.

## Dependencies
Phase 3A (parsers), Phase 1C (Redis)

## Files to Create

### 1. `backend/app/workers/__init__.py`
- Empty init

### 2. `backend/app/workers/task_queue.py`
- ARQ worker configuration
- Redis connection from settings
- Worker settings class

### 3. `backend/app/workers/tasks/__init__.py`
- Empty init

### 4. `backend/app/workers/tasks/process_document.py`
- process_document_task(ctx, document_id: str)
  - Load document from DB
  - Detect file type
  - Parse with appropriate parser
  - Quality scoring
  - Update document status
  - Save parsed pages to DB
  - Update document status to 'parsed'

### 5. `backend/app/services/parsing_service.py`
- ParsingService class
- enqueue_parse(document_id: UUID) -> str (task_id)
- get_parse_status(task_id: str) -> ParseStatus
- get_parsed_content(document_id: UUID) -> ParsedContent

### 6. Update `backend/app/api/v1/documents.py`
- POST /api/v1/documents/{document_id}/parse — enqueue parsing
- GET /api/v1/documents/{document_id}/parse-status — status polling
- GET /api/v1/documents/{document_id}/parsed — get parsed content

### 7. `backend/app/api/schemas/parsing.py`
- ParseRequest, ParseStatusResponse, ParsedContentResponse

## Acceptance Criteria
- [ ] POST /documents/{id}/parse enqueues background job
- [ ] Worker processes document and updates status
- [ ] Parse status is pollable
- [ ] Parsed content is retrievable
- [ ] Failed parsing updates status to 'failed' with error

## Test Requirements
- `tests/workers/test_process_document.py` — worker task tests
- `tests/api/test_parse.py` — parse endpoint integration tests
