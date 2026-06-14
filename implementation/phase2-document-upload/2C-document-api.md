# Phase 2C: Document CRUD API — Implementation Plan

## Task
Implement REST API endpoints for document management.

## Dependencies
Phase 2A (model), Phase 2B (service)

## Files to Create/Update

### 1. `backend/app/api/v1/documents.py`
Endpoints:
- POST /api/v1/documents — multipart upload
  - Request: file (UploadFile)
  - Response: DocumentResponse (201)
  - Errors: 413 (too large), 415 (unsupported type), 422 (validation error)
  
- GET /api/v1/documents — paginated list
  - Query params: page, page_size, status, document_type, sort_by, sort_order
  - Response: PaginatedResponse[DocumentResponse]
  
- GET /api/v1/documents/{document_id} — document detail
  - Response: DocumentResponse with pages and chunks summary
  - Errors: 404 (not found)
  
- PATCH /api/v1/documents/{document_id} — update metadata
  - Request: DocumentUpdate
  - Response: DocumentResponse
  - Errors: 404, 422
  
- DELETE /api/v1/documents/{document_id} — soft delete
  - Response: 204
  - Errors: 404
  
- GET /api/v1/documents/{document_id}/download — presigned URL
  - Response: {"url": "...", "expires_in": 3600}
  - Errors: 404

### 2. Update `backend/app/api/v1/router.py`
- Include documents router

### 3. `backend/app/api/schemas/documents.py` (update)
- Add DownloadResponse schema

## API Design Rules
- All endpoints use async/await
- Proper HTTP status codes
- Pagination uses offset/limit with total count
- Request validation via Pydantic
- Response serialization via Pydantic model_dump
- Document ownership check on all operations

## Acceptance Criteria
- [ ] POST /documents creates document with 201
- [ ] GET /documents returns paginated list
- [ ] GET /documents/{id} returns document detail
- [ ] PATCH /documents/{id} updates metadata
- [ ] DELETE /documents/{id} soft deletes
- [ ] GET /documents/{id}/download returns presigned URL
- [ ] All endpoints return proper error responses

## Test Requirements
- `tests/api/test_documents.py` — integration tests for all CRUD endpoints
  - Happy path for each endpoint
  - Validation error cases
  - Not found cases
  - Ownership check cases
