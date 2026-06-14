# Phase 2B: File Validation + Storage — Implementation Plan

## Task
Implement file validation (type, size, magic bytes) and storage service integration.

## Dependencies
Phase 1C (MinIO client), Phase 2A (Document model)

## Files to Create/Update

### 1. `backend/app/services/validation.py`
- FileValidator class
- validate_file(file: UploadFile) -> ValidationResult
- Checks:
  - File size (max 50MB from config)
  - MIME type whitelist (pdf, docx, xlsx, png, jpg, jpeg, tiff)
  - Magic byte verification (python-magic or manual checks)
  - Filename sanitization
- Returns ValidationResult with is_valid, errors, detected_type

### 2. `backend/app/services/storage.py`
- DocumentStorageService class
- upload_document(file: UploadFile, document_id: UUID) -> StorageResult
  - Generate storage path: {user_id}/{document_id}/{filename}
  - Upload to MinIO
  - Return storage_path, checksum, size
- download_document(document_id: UUID) -> bytes
- get_presigned_url(document_id: UUID, expiry: int) -> str
- delete_document(document_id: UUID) -> None

### 3. `backend/app/services/document_service.py`
- DocumentService class
- create_document(file: UploadFile, user_id: UUID) -> Document
  - Validate file
  - Upload to storage
  - Create DB record
  - Return document
- get_document(document_id: UUID) -> Document
- list_documents(user_id: UUID, filters: dict) -> PaginatedResponse
- update_document(document_id: UUID, updates: dict) -> Document
- delete_document(document_id: UUID) -> None (soft delete)

## File Validation Rules
| Extension | MIME Type | Magic Bytes |
|-----------|----------|-------------|
| .pdf | application/pdf | %PDF |
| .docx | application/vnd.openxmlformats-officedocument.wordprocessingml.document | PK (ZIP) |
| .xlsx | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet | PK (ZIP) |
| .png | image/png | \x89PNG |
| .jpg/.jpeg | image/jpeg | \xFF\xD8\xFF |
| .tiff | image/tiff | II or MM |

## Acceptance Criteria
- [ ] Valid files pass validation
- [ ] Invalid MIME types rejected with 415
- [ ] Oversized files rejected with 413
- [ ] Files stored in MinIO with correct path
- [ ] Checksums computed correctly
- [ ] Presigned URLs work for download

## Test Requirements
- `tests/services/test_validation.py` — file validation unit tests
- `tests/services/test_storage.py` — storage service unit tests (mocked MinIO)
- `tests/services/test_document_service.py` — document service unit tests
