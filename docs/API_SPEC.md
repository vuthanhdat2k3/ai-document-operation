# AI Document Operations Agent — API Specification

**Version:** 1.0.0  
**Base URL:** `https://api.example.com/api/v1`  
**Protocol:** HTTPS  
**Format:** JSON  
**Framework:** FastAPI (OpenAPI 3.1)

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Rate Limiting](#2-rate-limiting)
3. [Pagination](#3-pagination)
4. [Error Response Format](#4-error-response-format)
5. [Request ID Tracking](#5-request-id-tracking)
6. [API Versioning Strategy](#6-api-versioning-strategy)
7. [OpenAPI Schema Reference](#7-openapi-schema-reference)
8. [Document Management APIs](#8-document-management-apis)
9. [RAG Q&A APIs](#9-rag-qa-apis)
10. [Risk & Checklist APIs](#10-risk--checklist-apis)
11. [Task APIs](#11-task-apis)
12. [Report APIs](#12-report-apis)
13. [Agent APIs](#13-agent-apis)
14. [Evaluation APIs](#14-evaluation-apis)
15. [System APIs](#15-system-apis)
16. [Common Models](#16-common-models)
17. [Test Cases Summary](#17-test-cases-summary)

---

## 1. Authentication

All endpoints (except `/api/v1/health`) require JWT Bearer authentication.

**Header Format:**

```
Authorization: Bearer <access_token>
```

**Token Claims:**

```json
{
  "sub": "user_id_string",
  "iss": "ai-doc-ops-agent",
  "aud": "ai-doc-ops-api",
  "exp": 1700000000,
  "iat": 1699996400,
  "roles": ["user", "admin"],
  "org_id": "org_abc123"
}
```

**Token Lifetime:** 3600 seconds (1 hour)  
**Refresh Token Lifetime:** 86400 seconds (24 hours)  
**Algorithm:** RS256

**Error Response (401):**

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Missing or invalid authentication token",
    "request_id": "req_abc123"
  }
}
```

---

## 2. Rate Limiting

Rate limits are applied per API key/user.

| Tier       | Requests/min | Requests/hour | Burst |
|------------|-------------|---------------|-------|
| Free       | 10          | 100           | 5     |
| Pro        | 60          | 2000          | 20    |
| Enterprise | 300         | 10000         | 100   |

**Response Headers:**

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 58
X-RateLimit-Reset: 1700000060
Retry-After: 30
```

**Error Response (429):**

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Retry after 30 seconds.",
    "request_id": "req_abc123",
    "retry_after": 30
  }
}
```

---

## 3. Pagination

Cursor-based pagination is used for all list endpoints.

**Query Parameters:**

| Parameter   | Type    | Default | Max | Description                        |
|-------------|---------|---------|-----|------------------------------------|
| `cursor`    | string  | null    | —   | Opaque cursor from previous page   |
| `limit`     | integer | 20      | 100 | Number of items per page           |

**Response Envelope:**

```json
{
  "data": [],
  "pagination": {
    "next_cursor": "eyJpZCI6MTAwfQ==",
    "prev_cursor": null,
    "has_more": true,
    "total_count": 1523
  }
}
```

**Validation Rules:**
- `limit` must be between 1 and 100 inclusive
- `cursor` must be a valid base64-encoded string
- Invalid cursor returns `400 BAD_REQUEST`

---

## 4. Error Response Format

All errors follow a consistent structure:

```json
{
  "error": {
    "code": "ERROR_CODE_CONSTANT",
    "message": "Human-readable description",
    "request_id": "req_abc123",
    "details": [
      {
        "field": "title",
        "issue": "Field is required",
        "value": null
      }
    ],
    "timestamp": "2025-01-15T10:30:00Z"
  }
}
```

**Standard Error Codes:**

| HTTP Status | Code                    | Description                          |
|-------------|-------------------------|--------------------------------------|
| 400         | `BAD_REQUEST`           | Malformed request or validation fail |
| 401         | `UNAUTHORIZED`          | Missing or invalid auth token        |
| 403         | `FORBIDDEN`             | Insufficient permissions             |
| 404         | `NOT_FOUND`             | Resource does not exist              |
| 409         | `CONFLICT`              | Resource state conflict              |
| 413         | `PAYLOAD_TOO_LARGE`     | Request body exceeds limit           |
| 415         | `UNSUPPORTED_MEDIA_TYPE`| Invalid content type                 |
| 422         | `UNPROCESSABLE_ENTITY`  | Semantic validation failure          |
| 429         | `RATE_LIMIT_EXCEEDED`   | Too many requests                    |
| 500         | `INTERNAL_ERROR`        | Unexpected server error              |
| 503         | `SERVICE_UNAVAILABLE`   | Dependency unavailable               |

---

## 5. Request ID Tracking

Every request is assigned a unique request ID for tracing and debugging.

**Generation:** UUID v7 format (time-ordered)

**Behavior:**
- If client sends `X-Request-Id` header, that value is used
- If omitted, the server generates one
- The ID is returned in the `X-Request-Id` response header
- The ID is included in all error responses and log entries

**Header:**

```
X-Request-Id: 01946e5a-7b3a-7c00-8d4f-123456789abc
```

---

## 6. API Versioning Strategy

**URL path versioning:** `/api/v1/`, `/api/v2/`, etc.

**Policy:**
- Breaking changes require a new version
- Non-breaking additions (new fields, new endpoints) stay in current version
- Deprecated versions receive 6 months notice before removal
- Sunset header sent for deprecated versions: `Sunset: Sat, 01 Jul 2026 00:00:00 GMT`

**Deprecation Header:**

```
Deprecation: true
Sunset: Sat, 01 Jul 2026 00:00:00 GMT
Link: <https://api.example.com/api/v2/docs>; rel="successor-version"
```

---

## 7. OpenAPI Schema Reference

**Live Schema:** `GET /api/v1/openapi.json`  
**Swagger UI:** `GET /api/v1/docs`  
**ReDoc:** `GET /api/v1/redoc`

FastAPI auto-generates the OpenAPI 3.1 schema from route decorators and Pydantic models. The schema includes:

- All request/response models
- Authentication requirements
- Example values
- Validation constraints
- Error response definitions

---

## 8. Document Management APIs

### 8.1 POST /api/v1/documents/upload

**Purpose:** Upload a new document for processing.

**Method:** `POST`  
**URL:** `/api/v1/documents/upload`  
**Content-Type:** `multipart/form-data`

**Request Body:**

| Field      | Type   | Required | Description                         |
|------------|--------|----------|-------------------------------------|
| `file`     | binary | Yes      | Document file (PDF, DOCX, TXT, PNG) |
| `title`    | string | No       | Custom title (max 255 chars)        |
| `tags`     | string | No       | Comma-separated tags                |
| `metadata` | string | No       | JSON string of key-value metadata   |

**Validation Rules:**
- File size must not exceed 50 MB
- Allowed MIME types: `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `text/plain`, `image/png`, `image/jpeg`
- `title` max length 255 characters, alphanumeric + spaces + hyphens
- `tags` max 10 tags, each max 50 characters
- `metadata` must be valid JSON if provided, max 10 keys

**Response (201 Created):**

```json
{
  "data": {
    "document_id": "doc_a1b2c3d4e5",
    "title": "Contract Agreement 2025",
    "filename": "contract_2025.pdf",
    "mime_type": "application/pdf",
    "size_bytes": 2048576,
    "status": "uploaded",
    "tags": ["contract", "legal"],
    "metadata": {"department": "legal", "priority": "high"},
    "created_at": "2025-01-15T10:30:00Z",
    "updated_at": "2025-01-15T10:30:00Z",
    "uploaded_by": "user_xyz789"
  }
}
```

**Status Codes:**
| Code | Description              |
|------|--------------------------|
| 201  | Document uploaded        |
| 400  | Invalid file or metadata |
| 401  | Unauthorized             |
| 413  | File too large           |
| 415  | Unsupported file type    |
| 429  | Rate limit exceeded      |
| 500  | Internal error           |

**Error Responses:**

```json
// 413 Payload Too Large
{
  "error": {
    "code": "PAYLOAD_TOO_LARGE",
    "message": "File size exceeds 50 MB limit",
    "request_id": "req_abc123"
  }
}

// 415 Unsupported Media Type
{
  "error": {
    "code": "UNSUPPORTED_MEDIA_TYPE",
    "message": "File type 'application/zip' is not supported",
    "request_id": "req_abc123"
  }
}
```

**Test Cases:**

| # | Description                           | Input                                    | Expected Status | Expected Result              |
|---|---------------------------------------|------------------------------------------|-----------------|------------------------------|
| 1 | Valid PDF upload                      | 1 MB PDF file                            | 201             | Document created             |
| 2 | Valid DOCX upload with title and tags | DOCX + title="Test" + tags="a,b"         | 201             | Document created with fields |
| 3 | File exceeds 50 MB                    | 60 MB PDF                                | 413             | Payload too large error      |
| 4 | Unsupported file type                 | .zip file                                | 415             | Unsupported media type error |
| 5 | Missing file field                    | multipart with no `file`                 | 400             | Validation error             |
| 6 | Title exceeds 255 chars               | PDF + 300-char title                     | 400             | Validation error             |
| 7 | Invalid metadata JSON                 | PDF + metadata="not-json"                | 400             | Validation error             |
| 8 | More than 10 tags                     | PDF + 12 comma-separated tags            | 400             | Validation error             |
| 9 | Upload without auth token             | Valid PDF, no Authorization header       | 401             | Unauthorized error           |
| 10| Empty file (0 bytes)                  | Empty file                               | 400             | Validation error             |

---

### 8.2 GET /api/v1/documents

**Purpose:** List documents with filtering and pagination.

**Method:** `GET`  
**URL:** `/api/v1/documents`

**Query Parameters:**

| Parameter   | Type    | Required | Description                              |
|-------------|---------|----------|------------------------------------------|
| `cursor`    | string  | No       | Pagination cursor                        |
| `limit`     | integer | No       | Items per page (1-100, default 20)       |
| `status`    | string  | No       | Filter by status: uploaded, parsed, failed |
| `tag`       | string  | No       | Filter by tag                            |
| `sort_by`   | string  | No       | Sort field: created_at, updated_at, title |
| `sort_order`| string  | No       | asc or desc (default desc)               |
| `search`    | string  | No       | Full-text search in title and content    |

**Validation Rules:**
- `limit` must be integer between 1 and 100
- `status` must be one of: `uploaded`, `parsing`, `parsed`, `extraction_pending`, `extracted`, `failed`
- `sort_by` must be one of: `created_at`, `updated_at`, `title`
- `sort_order` must be `asc` or `desc`
- `search` max 200 characters

**Response (200 OK):**

```json
{
  "data": [
    {
      "document_id": "doc_a1b2c3d4e5",
      "title": "Contract Agreement 2025",
      "filename": "contract_2025.pdf",
      "mime_type": "application/pdf",
      "size_bytes": 2048576,
      "status": "parsed",
      "tags": ["contract", "legal"],
      "created_at": "2025-01-15T10:30:00Z",
      "updated_at": "2025-01-15T10:35:00Z"
    }
  ],
  "pagination": {
    "next_cursor": "eyJpZCI6MTAwfQ==",
    "prev_cursor": null,
    "has_more": true,
    "total_count": 1523
  }
}
```

**Status Codes:**
| Code | Description         |
|------|---------------------|
| 200  | Success             |
| 400  | Invalid parameters  |
| 401  | Unauthorized        |
| 500  | Internal error      |

**Test Cases:**

| # | Description                    | Input                       | Expected Status | Expected Result                   |
|---|--------------------------------|-----------------------------|-----------------|-----------------------------------|
| 1 | Default list                   | No params                   | 200             | Returns first 20 documents        |
| 2 | Custom limit                   | limit=5                     | 200             | Returns 5 documents               |
| 3 | Filter by status               | status=parsed               | 200             | Only parsed documents returned    |
| 4 | Filter by tag                  | tag=legal                   | 200             | Only documents with "legal" tag   |
| 5 | Full-text search               | search=contract             | 200             | Documents matching "contract"     |
| 6 | Pagination forward             | cursor=eyJpZCI6MTAwfQ==     | 200             | Next page of results              |
| 7 | Invalid limit (0)              | limit=0                     | 400             | Validation error                  |
| 8 | Invalid limit (101)            | limit=101                   | 400             | Validation error                  |
| 9 | Invalid status filter          | status=invalid              | 400             | Validation error                  |
| 10| Invalid cursor                 | cursor=not-valid-base64!!!  | 400             | Bad request error                 |

---

### 8.3 GET /api/v1/documents/{document_id}

**Purpose:** Retrieve a single document's details.

**Method:** `GET`  
**URL:** `/api/v1/documents/{document_id}`

**Path Parameters:**

| Parameter      | Type   | Required | Description         |
|----------------|--------|----------|---------------------|
| `document_id`  | string | Yes      | Document identifier |

**Validation Rules:**
- `document_id` must match pattern `^doc_[a-zA-Z0-9]{10}$`

**Response (200 OK):**

```json
{
  "data": {
    "document_id": "doc_a1b2c3d4e5",
    "title": "Contract Agreement 2025",
    "filename": "contract_2025.pdf",
    "mime_type": "application/pdf",
    "size_bytes": 2048576,
    "status": "parsed",
    "tags": ["contract", "legal"],
    "metadata": {"department": "legal"},
    "content_preview": "This agreement is entered into...",
    "page_count": 15,
    "chunk_count": 42,
    "embedding_status": "completed",
    "created_at": "2025-01-15T10:30:00Z",
    "updated_at": "2025-01-15T10:35:00Z",
    "uploaded_by": "user_xyz789",
    "parsed_at": "2025-01-15T10:32:00Z",
    "extracted_at": "2025-01-15T10:35:00Z"
  }
}
```

**Status Codes:**
| Code | Description    |
|------|----------------|
| 200  | Success        |
| 400  | Invalid ID     |
| 401  | Unauthorized   |
| 404  | Not found      |
| 500  | Internal error |

**Test Cases:**

| # | Description              | Input                 | Expected Status | Expected Result          |
|---|--------------------------|-----------------------|-----------------|--------------------------|
| 1 | Valid document retrieval | doc_a1b2c3d4e5       | 200             | Full document details    |
| 2 | Non-existent document    | doc_nonexistent00     | 404             | Not found error          |
| 3 | Invalid document ID format | doc_123             | 400             | Validation error         |
| 4 | Empty document ID        | (empty path segment)  | 404             | Route not found          |
| 5 | Other user's document    | doc_other_user_doc    | 403             | Forbidden error          |

---

### 8.4 DELETE /api/v1/documents/{document_id}

**Purpose:** Delete a document and all associated data (chunks, embeddings, tasks).

**Method:** `DELETE`  
**URL:** `/api/v1/documents/{document_id}`

**Path Parameters:**

| Parameter      | Type   | Required | Description         |
|----------------|--------|----------|---------------------|
| `document_id`  | string | Yes      | Document identifier |

**Response (200 OK):**

```json
{
  "data": {
    "document_id": "doc_a1b2c3d4e5",
    "deleted": true,
    "deleted_at": "2025-01-15T11:00:00Z"
  }
}
```

**Status Codes:**
| Code | Description            |
|------|------------------------|
| 200  | Document deleted       |
| 400  | Invalid ID             |
| 401  | Unauthorized           |
| 403  | Forbidden (not owner)  |
| 404  | Not found              |
| 409  | Document is processing |
| 500  | Internal error         |

**Error Response (409):**

```json
{
  "error": {
    "code": "CONFLICT",
    "message": "Cannot delete document while parsing is in progress",
    "request_id": "req_abc123"
  }
}
```

**Test Cases:**

| # | Description                      | Input                  | Expected Status | Expected Result                |
|---|----------------------------------|------------------------|-----------------|--------------------------------|
| 1 | Delete existing document         | doc_a1b2c3d4e5        | 200             | Document deleted               |
| 2 | Delete non-existent document     | doc_nonexistent00      | 404             | Not found error                |
| 3 | Delete document in processing    | doc_processing12       | 409             | Conflict error                 |
| 4 | Delete already deleted document  | doc_deleted00000       | 404             | Not found error                |
| 5 | Delete another user's document   | doc_other_user_doc     | 403             | Forbidden error                |

---

### 8.5 POST /api/v1/documents/{document_id}/parse

**Purpose:** Trigger document parsing (text extraction, chunking, embedding generation).

**Method:** `POST`  
**URL:** `/api/v1/documents/{document_id}/parse`

**Path Parameters:**

| Parameter      | Type   | Required | Description         |
|----------------|--------|----------|---------------------|
| `document_id`  | string | Yes      | Document identifier |

**Request Body (optional):**

```json
{
  "chunk_size": 1000,
  "chunk_overlap": 200,
  "embedding_model": "text-embedding-3-small",
  "ocr_enabled": true,
  "language": "en"
}
```

**Schema:**

| Field             | Type    | Required | Default                | Description                       |
|-------------------|---------|----------|------------------------|-----------------------------------|
| `chunk_size`      | integer | No       | 1000                   | Tokens per chunk (100-4000)       |
| `chunk_overlap`   | integer | No       | 200                    | Overlap tokens (0-chunk_size/2)   |
| `embedding_model` | string  | No       | text-embedding-3-small | Embedding model identifier        |
| `ocr_enabled`     | boolean | No       | true                   | Enable OCR for images/scanned PDFs|
| `language`        | string  | No       | en                     | ISO 639-1 language code           |

**Validation Rules:**
- `chunk_size` must be between 100 and 4000
- `chunk_overlap` must be between 0 and `chunk_size / 2`
- `embedding_model` must be one of: `text-embedding-3-small`, `text-embedding-3-large`, `text-embedding-ada-002`
- `language` must be valid ISO 639-1 code

**Response (202 Accepted):**

```json
{
  "data": {
    "document_id": "doc_a1b2c3d4e5",
    "task_id": "task_parse_f1g2h3",
    "status": "parsing",
    "estimated_duration_seconds": 30,
    "started_at": "2025-01-15T10:30:00Z"
  }
}
```

**Status Codes:**
| Code | Description                |
|------|----------------------------|
| 202  | Parsing started            |
| 400  | Invalid parameters         |
| 401  | Unauthorized               |
| 404  | Document not found         |
| 409  | Already parsing/parsed     |
| 500  | Internal error             |
| 503  | Parsing service unavailable|

**Test Cases:**

| # | Description                     | Input                               | Expected Status | Expected Result          |
|---|---------------------------------|---------------------------------------|-----------------|--------------------------|
| 1 | Parse with defaults             | Valid document_id, empty body        | 202             | Parsing started          |
| 2 | Parse with custom chunk size    | chunk_size=500                       | 202             | Parsing started          |
| 3 | Parse with OCR disabled         | ocr_enabled=false                    | 202             | Parsing started          |
| 4 | Invalid chunk_size (too small)  | chunk_size=50                        | 400             | Validation error         |
| 5 | Invalid chunk_size (too large)  | chunk_size=5000                      | 400             | Validation error         |
| 6 | Overlap exceeds half chunk_size | chunk_size=1000, chunk_overlap=600   | 400             | Validation error         |
| 7 | Document already parsing        | Document in "parsing" status         | 409             | Conflict error           |
| 8 | Non-existent document           | doc_nonexistent00                    | 404             | Not found error          |
| 9 | Invalid embedding model         | embedding_model="gpt-4"              | 400             | Validation error         |

---

### 8.6 POST /api/v1/documents/{document_id}/extract

**Purpose:** Extract structured data from a parsed document using AI.

**Method:** `POST`  
**URL:** `/api/v1/documents/{document_id}/extract`

**Path Parameters:**

| Parameter      | Type   | Required | Description         |
|----------------|--------|----------|---------------------|
| `document_id`  | string | Yes      | Document identifier |

**Request Body:**

```json
{
  "extraction_type": "contract",
  "fields": [
    {"name": "parties", "type": "list", "description": "All parties to the contract"},
    {"name": "effective_date", "type": "date", "description": "Contract effective date"},
    {"name": "total_value", "type": "currency", "description": "Total contract value"},
    {"name": "termination_clause", "type": "text", "description": "Termination conditions"}
  ],
  "model": "gpt-4o",
  "confidence_threshold": 0.8
}
```

**Schema:**

| Field                   | Type    | Required | Default | Description                            |
|-------------------------|---------|----------|---------|----------------------------------------|
| `extraction_type`       | string  | No       | generic | Type: generic, contract, invoice, resume |
| `fields`                | array   | Yes      | —       | Fields to extract (1-50)               |
| `fields[].name`         | string  | Yes      | —       | Field name (snake_case, max 100 chars) |
| `fields[].type`         | string  | Yes      | —       | Type: text, number, date, currency, list, boolean |
| `fields[].description`  | string  | No       | —       | Description for AI (max 500 chars)     |
| `model`                 | string  | No       | gpt-4o  | LLM model to use                      |
| `confidence_threshold`  | number  | No       | 0.7     | Minimum confidence (0.0-1.0)          |

**Validation Rules:**
- `fields` array must have 1-50 items
- `fields[].name` must be snake_case, alphanumeric and underscores only
- `fields[].type` must be one of: `text`, `number`, `date`, `currency`, `list`, `boolean`
- `confidence_threshold` must be between 0.0 and 1.0
- Document must be in `parsed` status

**Response (202 Accepted):**

```json
{
  "data": {
    "document_id": "doc_a1b2c3d4e5",
    "task_id": "task_extract_j4k5l6",
    "status": "extraction_pending",
    "fields_requested": 4,
    "started_at": "2025-01-15T10:40:00Z"
  }
}
```

**Status Codes:**
| Code | Description                  |
|------|------------------------------|
| 202  | Extraction started           |
| 400  | Invalid parameters           |
| 401  | Unauthorized                 |
| 404  | Document not found           |
| 409  | Document not yet parsed      |
| 500  | Internal error               |
| 503  | AI service unavailable       |

**Test Cases:**

| # | Description                     | Input                                      | Expected Status | Expected Result          |
|---|---------------------------------|--------------------------------------------|-----------------|--------------------------|
| 1 | Valid extraction request        | 4 fields, valid document                   | 202             | Extraction started       |
| 2 | Single field extraction         | 1 field                                    | 202             | Extraction started       |
| 3 | Empty fields array              | fields=[]                                  | 400             | Validation error         |
| 4 | Too many fields (>50)           | 51 fields                                  | 400             | Validation error         |
| 5 | Invalid field type              | type="array"                               | 400             | Validation error         |
| 6 | Invalid field name (spaces)     | name="my field"                            | 400             | Validation error         |
| 7 | Confidence out of range         | confidence_threshold=1.5                   | 400             | Validation error         |
| 8 | Document not parsed yet         | Document in "uploaded" status              | 409             | Conflict error           |
| 9 | Non-existent document           | doc_nonexistent00                          | 404             | Not found error          |

---

## 9. RAG Q&A APIs

### 9.1 POST /api/v1/documents/{document_id}/ask

**Purpose:** Ask a question about a document using RAG (Retrieval-Augmented Generation).

**Method:** `POST`  
**URL:** `/api/v1/documents/{document_id}/ask`

**Path Parameters:**

| Parameter      | Type   | Required | Description         |
|----------------|--------|----------|---------------------|
| `document_id`  | string | Yes      | Document identifier |

**Request Body:**

```json
{
  "question": "What are the termination conditions in this contract?",
  "max_chunks": 5,
  "model": "gpt-4o",
  "temperature": 0.1,
  "include_sources": true,
  "stream": false
}
```

**Schema:**

| Field              | Type    | Required | Default | Description                        |
|--------------------|---------|----------|---------|------------------------------------|
| `question`         | string  | Yes      | —       | Question text (10-2000 chars)      |
| `max_chunks`       | integer | No       | 5       | Max context chunks (1-20)          |
| `model`            | string  | No       | gpt-4o  | LLM model                          |
| `temperature`      | number  | No       | 0.1     | Sampling temperature (0.0-1.0)     |
| `include_sources`  | boolean | No       | true    | Include source chunk references    |
| `stream`           | boolean | No       | false   | Enable SSE streaming               |

**Validation Rules:**
- `question` must be between 10 and 2000 characters
- `max_chunks` must be between 1 and 20
- `temperature` must be between 0.0 and 1.0
- Document must be in `parsed` status with completed embeddings

**Response (200 OK) — Non-streaming:**

```json
{
  "data": {
    "answer": "The contract may be terminated under the following conditions: (1) By either party with 30 days written notice, (2) Immediately upon material breach that remains uncured for 15 days, (3) Upon insolvency of either party.",
    "confidence": 0.92,
    "sources": [
      {
        "chunk_id": "chunk_m1n2o3",
        "page_number": 8,
        "text_excerpt": "...termination of this Agreement may be effected by either party upon thirty (30) days written notice...",
        "relevance_score": 0.95
      },
      {
        "chunk_id": "chunk_p4q5r6",
        "page_number": 9,
        "text_excerpt": "...material breach of any provision hereof that remains uncured for a period of fifteen (15) days...",
        "relevance_score": 0.88
      }
    ],
    "model": "gpt-4o",
    "tokens_used": {"prompt": 2500, "completion": 350, "total": 2850},
    "latency_ms": 3200
  }
}
```

**Response (200 OK) — Streaming (SSE):**

```
data: {"type": "chunk", "content": "The contract "}
data: {"type": "chunk", "content": "may be terminated "}
data: {"type": "chunk", "content": "under the following conditions..."}
data: {"type": "sources", "sources": [...]}
data: {"type": "done", "tokens_used": {...}, "latency_ms": 3200}
```

**Status Codes:**
| Code | Description               |
|------|---------------------------|
| 200  | Answer generated          |
| 400  | Invalid parameters        |
| 401  | Unauthorized              |
| 404  | Document not found        |
| 409  | Document not parsed       |
| 500  | Internal error            |
| 503  | AI service unavailable    |

**Test Cases:**

| # | Description                      | Input                                     | Expected Status | Expected Result            |
|---|----------------------------------|--------------------------------------------|-----------------|----------------------------|
| 1 | Valid question                   | question="What is the total value?"        | 200             | Answer with sources        |
| 2 | Question with sources disabled   | include_sources=false                      | 200             | Answer without sources     |
| 3 | Streaming request                | stream=true                                | 200             | SSE stream                 |
| 4 | Question too short (<10 chars)   | question="What?"                           | 400             | Validation error           |
| 5 | Question too long (>2000 chars)  | 2001-char question                         | 400             | Validation error           |
| 6 | Invalid max_chunks (0)           | max_chunks=0                               | 400             | Validation error           |
| 7 | Document not parsed              | Document in "uploaded" status              | 409             | Conflict error             |
| 8 | Non-existent document            | doc_nonexistent00                          | 404             | Not found error            |
| 9 | AI service timeout               | (service unavailable)                      | 503             | Service unavailable error  |

---

## 10. Risk & Checklist APIs

### 10.1 POST /api/v1/documents/{document_id}/risks

**Purpose:** Analyze a document for potential risks using AI.

**Method:** `POST`  
**URL:** `/api/v1/documents/{document_id}/risks`

**Path Parameters:**

| Parameter      | Type   | Required | Description         |
|----------------|--------|----------|---------------------|
| `document_id`  | string | Yes      | Document identifier |

**Request Body:**

```json
{
  "risk_categories": ["legal", "financial", "compliance", "operational"],
  "severity_levels": ["high", "critical"],
  "model": "gpt-4o",
  "max_risks": 20,
  "include_mitigations": true
}
```

**Schema:**

| Field                  | Type    | Required | Default                              | Description                  |
|------------------------|---------|----------|--------------------------------------|------------------------------|
| `risk_categories`      | array   | No       | ["legal","financial","compliance"]   | Categories to analyze        |
| `severity_levels`      | array   | No       | ["medium","high","critical"]         | Minimum severity to report   |
| `model`                | string  | No       | gpt-4o                               | LLM model                    |
| `max_risks`            | integer | No       | 20                                   | Maximum risks to return (1-50) |
| `include_mitigations`  | boolean | No       | true                                 | Include mitigation suggestions |

**Validation Rules:**
- `risk_categories` items must be one of: `legal`, `financial`, `compliance`, `operational`, `reputational`, `technical`
- `severity_levels` items must be one of: `low`, `medium`, `high`, `critical`
- `max_risks` must be between 1 and 50
- Document must be in `parsed` status

**Response (202 Accepted):**

```json
{
  "data": {
    "document_id": "doc_a1b2c3d4e5",
    "task_id": "task_risks_s7t8u9",
    "status": "analyzing",
    "started_at": "2025-01-15T10:45:00Z"
  }
}
```

**Async Result (available via task polling or webhook):**

```json
{
  "risks": [
    {
      "risk_id": "risk_v1w2x3",
      "category": "legal",
      "severity": "high",
      "title": "Unlimited liability clause",
      "description": "Section 8.2 contains an uncapped liability clause that exposes the company to unlimited damages.",
      "page_reference": 12,
      "clause_excerpt": "The Provider shall be liable for all damages arising from...",
      "confidence": 0.91,
      "mitigation": "Negotiate a liability cap of 2x the annual contract value.",
      "related_risks": ["risk_y4z5a6"]
    },
    {
      "risk_id": "risk_y4z5a6",
      "category": "financial",
      "severity": "critical",
      "title": "Missing payment milestone definitions",
      "description": "Payment schedule references milestones but does not define deliverables for each milestone.",
      "page_reference": 5,
      "clause_excerpt": "Payments shall be made upon completion of each milestone as defined in Schedule B...",
      "confidence": 0.87,
      "mitigation": "Add a detailed Schedule B with clear deliverables and acceptance criteria for each milestone."
    }
  ],
  "summary": {
    "total_risks": 8,
    "by_severity": {"critical": 2, "high": 3, "medium": 3},
    "by_category": {"legal": 3, "financial": 2, "compliance": 2, "operational": 1},
    "overall_risk_score": 7.2
  }
}
```

**Status Codes:**
| Code | Description               |
|------|---------------------------|
| 202  | Analysis started          |
| 400  | Invalid parameters        |
| 401  | Unauthorized              |
| 404  | Document not found        |
| 409  | Document not parsed       |
| 500  | Internal error            |
| 503  | AI service unavailable    |

**Test Cases:**

| # | Description                    | Input                                    | Expected Status | Expected Result          |
|---|--------------------------------|------------------------------------------|-----------------|--------------------------|
| 1 | Analyze with defaults          | Valid document_id, empty body            | 202             | Analysis started         |
| 2 | Custom risk categories         | risk_categories=["legal"]                | 202             | Analysis started         |
| 3 | Custom severity filter         | severity_levels=["critical"]             | 202             | Analysis started         |
| 4 | Mitigations disabled           | include_mitigations=false                | 202             | Analysis started         |
| 5 | Invalid risk category          | risk_categories=["unknown"]              | 400             | Validation error         |
| 6 | Invalid severity level         | severity_levels=["extreme"]              | 400             | Validation error         |
| 7 | max_risks out of range         | max_risks=100                            | 400             | Validation error         |
| 8 | Document not parsed            | Document in "uploaded" status            | 409             | Conflict error           |

---

### 10.2 POST /api/v1/documents/{document_id}/checklist

**Purpose:** Generate a compliance/operations checklist from a document.

**Method:** `POST`  
**URL:** `/api/v1/documents/{document_id}/checklist`

**Path Parameters:**

| Parameter      | Type   | Required | Description         |
|----------------|--------|----------|---------------------|
| `document_id`  | string | Yes      | Document identifier |

**Request Body:**

```json
{
  "checklist_type": "compliance",
  "framework": "ISO 27001",
  "model": "gpt-4o",
  "include_references": true,
  "max_items": 30
}
```

**Schema:**

| Field                | Type    | Required | Default     | Description                           |
|----------------------|---------|----------|-------------|---------------------------------------|
| `checklist_type`     | string  | No       | compliance  | Type: compliance, operations, onboarding, due_diligence |
| `framework`          | string  | No       | null        | Compliance framework reference        |
| `model`              | string  | No       | gpt-4o      | LLM model                             |
| `include_references` | boolean | No       | true        | Include document section references   |
| `max_items`          | integer | No       | 30          | Max checklist items (1-100)           |

**Validation Rules:**
- `checklist_type` must be one of: `compliance`, `operations`, `onboarding`, `due_diligence`, `audit`
- `max_items` must be between 1 and 100
- Document must be in `parsed` status

**Response (202 Accepted):**

```json
{
  "data": {
    "document_id": "doc_a1b2c3d4e5",
    "task_id": "task_check_b1c2d3",
    "status": "generating",
    "started_at": "2025-01-15T10:50:00Z"
  }
}
```

**Async Result:**

```json
{
  "checklist": {
    "checklist_id": "chk_e4f5g6",
    "type": "compliance",
    "framework": "ISO 27001",
    "items": [
      {
        "item_id": "item_h7i8j9",
        "category": "Access Control",
        "title": "Verify access control provisions are defined",
        "description": "Ensure the contract specifies access control requirements for sensitive data.",
        "priority": "required",
        "status": "pending",
        "page_reference": 14,
        "clause_excerpt": "Access to confidential information shall be restricted to...",
        "notes": null
      },
      {
        "item_id": "item_k0l1m2",
        "category": "Data Protection",
        "title": "Confirm data retention policy is specified",
        "description": "Check that data retention and deletion timelines are clearly stated.",
        "priority": "required",
        "status": "pending",
        "page_reference": 16,
        "clause_excerpt": "Data shall be retained for a period not exceeding...",
        "notes": null
      }
    ],
    "summary": {
      "total_items": 18,
      "by_priority": {"required": 10, "recommended": 5, "optional": 3},
      "by_category": {"Access Control": 4, "Data Protection": 5, "Incident Management": 3, "Audit": 6},
      "compliance_score": null
    }
  }
}
```

**Status Codes:**
| Code | Description               |
|------|---------------------------|
| 202  | Generation started        |
| 400  | Invalid parameters        |
| 401  | Unauthorized              |
| 404  | Document not found        |
| 409  | Document not parsed       |
| 500  | Internal error            |
| 503  | AI service unavailable    |

**Test Cases:**

| # | Description                    | Input                                  | Expected Status | Expected Result          |
|---|--------------------------------|----------------------------------------|-----------------|--------------------------|
| 1 | Generate with defaults         | Valid document_id, empty body          | 202             | Generation started       |
| 2 | Custom framework               | framework="SOC 2"                      | 202             | Generation started       |
| 3 | Custom checklist type          | checklist_type="due_diligence"         | 202             | Generation started       |
| 4 | References disabled            | include_references=false               | 202             | Generation started       |
| 5 | Invalid checklist type         | checklist_type="unknown"               | 400             | Validation error         |
| 6 | max_items out of range         | max_items=200                          | 400             | Validation error         |
| 7 | Document not parsed            | Document in "uploaded" status          | 409             | Conflict error           |

---

## 11. Task APIs

### 11.1 GET /api/v1/tasks

**Purpose:** List async tasks with filtering and pagination.

**Method:** `GET`  
**URL:** `/api/v1/tasks`

**Query Parameters:**

| Parameter      | Type    | Required | Description                                        |
|----------------|---------|----------|----------------------------------------------------|
| `cursor`       | string  | No       | Pagination cursor                                  |
| `limit`        | integer | No       | Items per page (1-100, default 20)                 |
| `status`       | string  | No       | Filter: pending, running, completed, failed        |
| `type`         | string  | No       | Filter: parse, extract, risks, checklist, report   |
| `document_id`  | string  | No       | Filter by document                                 |

**Response (200 OK):**

```json
{
  "data": [
    {
      "task_id": "task_parse_f1g2h3",
      "type": "parse",
      "document_id": "doc_a1b2c3d4e5",
      "status": "completed",
      "progress": 100,
      "result": {
        "chunks_created": 42,
        "pages_processed": 15
      },
      "error": null,
      "created_at": "2025-01-15T10:30:00Z",
      "started_at": "2025-01-15T10:30:05Z",
      "completed_at": "2025-01-15T10:30:35Z",
      "duration_ms": 30000
    }
  ],
  "pagination": {
    "next_cursor": "eyJ0YXNrX2lkIjoiMTAwIn0=",
    "prev_cursor": null,
    "has_more": false,
    "total_count": 5
  }
}
```

**Status Codes:**
| Code | Description         |
|------|---------------------|
| 200  | Success             |
| 400  | Invalid parameters  |
| 401  | Unauthorized        |
| 500  | Internal error      |

**Test Cases:**

| # | Description            | Input                        | Expected Status | Expected Result              |
|---|------------------------|------------------------------|-----------------|------------------------------|
| 1 | List all tasks         | No params                    | 200             | All tasks for user           |
| 2 | Filter by status       | status=completed             | 200             | Only completed tasks         |
| 3 | Filter by type         | type=parse                   | 200             | Only parse tasks             |
| 4 | Filter by document     | document_id=doc_a1b2c3d4e5   | 200             | Tasks for that document      |
| 5 | Combined filters       | status=running&type=extract  | 200             | Running extract tasks        |
| 6 | Invalid status filter  | status=unknown               | 400             | Validation error             |

---

### 11.2 PATCH /api/v1/tasks/{task_id}

**Purpose:** Update a task (cancel, retry).

**Method:** `PATCH`  
**URL:** `/api/v1/tasks/{task_id}`

**Path Parameters:**

| Parameter | Type   | Required | Description    |
|-----------|--------|----------|----------------|
| `task_id` | string | Yes      | Task identifier|

**Request Body:**

```json
{
  "action": "cancel"
}
```

**Schema:**

| Field    | Type   | Required | Description               |
|----------|--------|----------|---------------------------|
| `action` | string | Yes      | Action: cancel, retry     |

**Validation Rules:**
- `action` must be one of: `cancel`, `retry`
- Cancel only allowed for tasks in `pending` or `running` status
- Retry only allowed for tasks in `failed` status

**Response (200 OK):**

```json
{
  "data": {
    "task_id": "task_parse_f1g2h3",
    "status": "cancelled",
    "action_performed": "cancel",
    "updated_at": "2025-01-15T10:32:00Z"
  }
}
```

**Status Codes:**
| Code | Description                   |
|------|-------------------------------|
| 200  | Task updated                  |
| 400  | Invalid parameters            |
| 401  | Unauthorized                  |
| 404  | Task not found                |
| 409  | Invalid state for action      |
| 500  | Internal error                |

**Test Cases:**

| # | Description                   | Input                              | Expected Status | Expected Result          |
|---|-------------------------------|------------------------------------|-----------------|--------------------------|
| 1 | Cancel running task           | action="cancel", running task      | 200             | Task cancelled           |
| 2 | Cancel pending task           | action="cancel", pending task      | 200             | Task cancelled           |
| 3 | Retry failed task             | action="retry", failed task        | 200             | Task retried             |
| 4 | Cancel completed task         | action="cancel", completed task    | 409             | Conflict error           |
| 5 | Retry running task            | action="retry", running task       | 409             | Conflict error           |
| 6 | Invalid action                | action="delete"                    | 400             | Validation error         |
| 7 | Non-existent task             | task_nonexistent00                 | 404             | Not found error          |

---

## 12. Report APIs

### 12.1 POST /api/v1/reports

**Purpose:** Generate a report combining document analysis results.

**Method:** `POST`  
**URL:** `/api/v1/reports`

**Request Body:**

```json
{
  "document_ids": ["doc_a1b2c3d4e5", "doc_f6g7h8i9j0"],
  "report_type": "comprehensive",
  "sections": ["summary", "risks", "checklist", "key_terms", "recommendations"],
  "format": "pdf",
  "model": "gpt-4o",
  "language": "en",
  "custom_instructions": "Focus on data privacy compliance gaps"
}
```

**Schema:**

| Field                 | Type    | Required | Default      | Description                               |
|-----------------------|---------|----------|--------------|-------------------------------------------|
| `document_ids`        | array   | Yes      | —            | Document IDs (1-10)                       |
| `report_type`         | string  | No       | comprehensive| Type: summary, comprehensive, executive, technical |
| `sections`            | array   | No       | all          | Sections to include                       |
| `format`              | string  | No       | pdf          | Output: pdf, markdown, html, json         |
| `model`               | string  | No       | gpt-4o       | LLM model                                 |
| `language`            | string  | No       | en           | ISO 639-1 language code                   |
| `custom_instructions` | string  | No       | null         | Additional instructions (max 2000 chars)  |

**Validation Rules:**
- `document_ids` must contain 1-10 valid document IDs
- All documents must be in `parsed` or `extracted` status
- `sections` items must be one of: `summary`, `risks`, `checklist`, `key_terms`, `recommendations`, `extraction_data`, `compliance_matrix`
- `format` must be one of: `pdf`, `markdown`, `html`, `json`
- `report_type` must be one of: `summary`, `comprehensive`, `executive`, `technical`
- `custom_instructions` max 2000 characters

**Response (202 Accepted):**

```json
{
  "data": {
    "report_id": "rpt_n3o4p5",
    "task_id": "task_report_q6r7s8",
    "status": "generating",
    "document_count": 2,
    "estimated_duration_seconds": 60,
    "created_at": "2025-01-15T11:00:00Z"
  }
}
```

**Status Codes:**
| Code | Description               |
|------|---------------------------|
| 202  | Report generation started |
| 400  | Invalid parameters        |
| 401  | Unauthorized              |
| 404  | One or more docs not found|
| 409  | Document(s) not parsed    |
| 500  | Internal error            |
| 503  | AI service unavailable    |

**Test Cases:**

| # | Description                    | Input                                        | Expected Status | Expected Result          |
|---|--------------------------------|----------------------------------------------|-----------------|--------------------------|
| 1 | Single document report         | 1 document, defaults                         | 202             | Report started           |
| 2 | Multi-document report          | 3 documents, comprehensive                   | 202             | Report started           |
| 3 | Custom sections                | sections=["summary","risks"]                 | 202             | Report started           |
| 4 | PDF format                     | format="pdf"                                 | 202             | Report started           |
| 5 | Empty document_ids             | document_ids=[]                              | 400             | Validation error         |
| 6 | Too many documents (>10)       | 11 document IDs                              | 400             | Validation error         |
| 7 | Invalid section                | sections=["unknown"]                         | 400             | Validation error         |
| 8 | Non-existent document          | One invalid doc ID                           | 404             | Not found error          |
| 9 | Document not parsed            | Unparsed document ID                         | 409             | Conflict error           |

---

### 12.2 GET /api/v1/reports/{report_id}

**Purpose:** Retrieve report details and content.

**Method:** `GET`  
**URL:** `/api/v1/reports/{report_id}`

**Path Parameters:**

| Parameter   | Type   | Required | Description     |
|-------------|--------|----------|-----------------|
| `report_id` | string | Yes      | Report identifier|

**Response (200 OK):**

```json
{
  "data": {
    "report_id": "rpt_n3o4p5",
    "report_type": "comprehensive",
    "status": "completed",
    "document_ids": ["doc_a1b2c3d4e5"],
    "sections": ["summary", "risks", "checklist"],
    "format": "pdf",
    "content": {
      "summary": "This contract establishes a SaaS licensing agreement...",
      "risks": [...],
      "checklist": [...]
    },
    "file_url": "/api/v1/reports/rpt_n3o4p5/export",
    "file_size_bytes": 524288,
    "created_at": "2025-01-15T11:00:00Z",
    "completed_at": "2025-01-15T11:01:00Z",
    "generated_by": "user_xyz789"
  }
}
```

**Status Codes:**
| Code | Description    |
|------|----------------|
| 200  | Success        |
| 401  | Unauthorized   |
| 404  | Not found      |
| 500  | Internal error |

**Test Cases:**

| # | Description            | Input              | Expected Status | Expected Result          |
|---|------------------------|--------------------|-----------------|--------------------------|
| 1 | Get completed report   | rpt_n3o4p5        | 200             | Full report data         |
| 2 | Get generating report  | rpt_generating01   | 200             | Status "generating"      |
| 3 | Non-existent report    | rpt_nonexistent    | 404             | Not found error          |

---

### 12.3 GET /api/v1/reports/{report_id}/export

**Purpose:** Download the report file.

**Method:** `GET`  
**URL:** `/api/v1/reports/{report_id}/export`

**Query Parameters:**

| Parameter | Type   | Required | Description                               |
|-----------|--------|----------|-------------------------------------------|
| `format`  | string | No       | Override format: pdf, markdown, html, json |

**Response (200 OK):**
- Returns the file with appropriate `Content-Type` header
- `Content-Disposition: attachment; filename="report_rpt_n3o4p5.pdf"`

| Format     | Content-Type                          |
|------------|---------------------------------------|
| pdf        | `application/pdf`                     |
| markdown   | `text/markdown`                       |
| html       | `text/html`                           |
| json       | `application/json`                    |

**Status Codes:**
| Code | Description            |
|------|------------------------|
| 200  | File download          |
| 401  | Unauthorized           |
| 404  | Report not found       |
| 409  | Report not completed   |
| 500  | Internal error         |

**Test Cases:**

| # | Description            | Input                             | Expected Status | Expected Result              |
|---|------------------------|-----------------------------------|-----------------|------------------------------|
| 1 | Download PDF           | Valid report_id, format=pdf       | 200             | PDF file returned            |
| 2 | Download Markdown      | Valid report_id, format=markdown  | 200             | Markdown file returned       |
| 3 | Download JSON          | Valid report_id, format=json      | 200             | JSON file returned           |
| 4 | Report not completed   | Report in "generating" status     | 409             | Conflict error               |
| 5 | Non-existent report    | rpt_nonexistent                   | 404             | Not found error              |

---

## 13. Agent APIs

### 13.1 POST /api/v1/agent/run

**Purpose:** Run an autonomous agent task on one or more documents.

**Method:** `POST`  
**URL:** `/api/v1/agent/run`

**Request Body:**

```json
{
  "document_ids": ["doc_a1b2c3d4e5"],
  "goal": "Perform a full compliance review against GDPR requirements and generate a remediation plan",
  "model": "gpt-4o",
  "max_steps": 20,
  "max_tokens": 50000,
  "tools_enabled": ["web_search", "calculator", "document_reader"],
  "auto_approve": false,
  "callback_url": "https://webhook.example.com/agent-complete"
}
```

**Schema:**

| Field             | Type    | Required | Default                | Description                      |
|-------------------|---------|----------|------------------------|----------------------------------|
| `document_ids`    | array   | Yes      | —                      | Document IDs (1-5)               |
| `goal`            | string  | Yes      | —                      | Task description (20-5000 chars) |
| `model`           | string  | No       | gpt-4o                 | LLM model                        |
| `max_steps`       | integer | No       | 20                     | Max agent steps (1-50)           |
| `max_tokens`      | integer | No       | 50000                  | Max token budget (1000-200000)   |
| `tools_enabled`   | array   | No       | ["document_reader"]    | Available tools                  |
| `auto_approve`    | boolean | No       | false                  | Skip human approval steps        |
| `callback_url`    | string  | No       | null                   | Webhook URL for completion       |

**Validation Rules:**
- `document_ids` must contain 1-5 valid document IDs
- `goal` must be between 20 and 5000 characters
- `max_steps` must be between 1 and 50
- `max_tokens` must be between 1000 and 200000
- `tools_enabled` items must be one of: `document_reader`, `web_search`, `calculator`, `code_executor`, `knowledge_base`
- `callback_url` must be a valid HTTPS URL if provided
- All documents must be in `parsed` or `extracted` status

**Response (202 Accepted):**

```json
{
  "data": {
    "session_id": "sess_t9u0v1",
    "status": "running",
    "goal": "Perform a full compliance review against GDPR requirements...",
    "document_ids": ["doc_a1b2c3d4e5"],
    "max_steps": 20,
    "tools_enabled": ["web_search", "calculator", "document_reader"],
    "created_at": "2025-01-15T11:10:00Z"
  }
}
```

**Status Codes:**
| Code | Description               |
|------|---------------------------|
| 202  | Agent session started     |
| 400  | Invalid parameters        |
| 401  | Unauthorized              |
| 404  | Document(s) not found     |
| 409  | Document(s) not parsed    |
| 500  | Internal error            |
| 503  | AI service unavailable    |

**Test Cases:**

| # | Description                      | Input                                    | Expected Status | Expected Result          |
|---|----------------------------------|------------------------------------------|-----------------|--------------------------|
| 1 | Valid agent run                  | 1 doc, valid goal                        | 202             | Session started          |
| 2 | Multi-document run               | 3 docs, valid goal                       | 202             | Session started          |
| 3 | With callback URL                | callback_url="https://webhook.example.com" | 202          | Session started          |
| 4 | Goal too short (<20 chars)       | goal="Check doc"                         | 400             | Validation error         |
| 5 | Too many documents (>5)          | 6 document IDs                           | 400             | Validation error         |
| 6 | max_steps out of range           | max_steps=100                            | 400             | Validation error         |
| 7 | Invalid tool                     | tools_enabled=["hacker_tool"]            | 400             | Validation error         |
| 8 | Invalid callback URL             | callback_url="http://insecure.com"       | 400             | Validation error         |
| 9 | Document not parsed              | Unparsed document                        | 409             | Conflict error           |

---

### 13.2 GET /api/v1/agent/sessions/{session_id}

**Purpose:** Get agent session status and result.

**Method:** `GET`  
**URL:** `/api/v1/agent/sessions/{session_id}`

**Path Parameters:**

| Parameter    | Type   | Required | Description       |
|--------------|--------|----------|-------------------|
| `session_id` | string | Yes      | Session identifier|

**Response (200 OK):**

```json
{
  "data": {
    "session_id": "sess_t9u0v1",
    "status": "completed",
    "goal": "Perform a full compliance review against GDPR requirements...",
    "document_ids": ["doc_a1b2c3d4e5"],
    "total_steps": 12,
    "tokens_used": {
      "prompt": 35000,
      "completion": 12000,
      "total": 47000
    },
    "result": {
      "summary": "The document has several GDPR compliance gaps...",
      "output": "## GDPR Compliance Review\n\n### Findings\n...",
      "artifacts": [
        {"type": "report", "id": "rpt_x1y2z3", "name": "GDPR Compliance Report"},
        {"type": "checklist", "id": "chk_a4b5c6", "name": "Remediation Checklist"}
      ]
    },
    "cost_estimate_usd": 0.85,
    "created_at": "2025-01-15T11:10:00Z",
    "started_at": "2025-01-15T11:10:05Z",
    "completed_at": "2025-01-15T11:12:30Z",
    "duration_ms": 145000
  }
}
```

**Status Codes:**
| Code | Description    |
|------|----------------|
| 200  | Success        |
| 401  | Unauthorized   |
| 404  | Not found      |
| 500  | Internal error |

**Test Cases:**

| # | Description                | Input              | Expected Status | Expected Result              |
|---|----------------------------|--------------------|-----------------|------------------------------|
| 1 | Get completed session      | Valid session_id   | 200             | Full session with result     |
| 2 | Get running session        | Running session    | 200             | Status "running", no result  |
| 3 | Non-existent session       | sess_nonexistent   | 404             | Not found error              |

---

### 13.3 GET /api/v1/agent/sessions/{session_id}/steps

**Purpose:** List all steps (thoughts and actions) in an agent session.

**Method:** `GET`  
**URL:** `/api/v1/agent/sessions/{session_id}/steps`

**Path Parameters:**

| Parameter    | Type   | Required | Description       |
|--------------|--------|----------|-------------------|
| `session_id` | string | Yes      | Session identifier|

**Query Parameters:**

| Parameter | Type    | Required | Description                    |
|-----------|---------|----------|--------------------------------|
| `cursor`  | string  | No       | Pagination cursor              |
| `limit`   | integer | No       | Items per page (1-100, def 50) |

**Response (200 OK):**

```json
{
  "data": [
    {
      "step_id": "step_1",
      "step_number": 1,
      "type": "thought",
      "content": "I need to first read the document to understand its structure and identify GDPR-related clauses.",
      "timestamp": "2025-01-15T11:10:10Z",
      "tokens_used": 150
    },
    {
      "step_id": "step_2",
      "step_number": 2,
      "type": "action",
      "tool": "document_reader",
      "input": {"document_id": "doc_a1b2c3d4e5", "query": "data protection personal information"},
      "output": {"chunks_found": 8, "excerpts": ["...personal data shall be processed..."]},
      "timestamp": "2025-01-15T11:10:15Z",
      "tokens_used": 200,
      "duration_ms": 3000
    },
    {
      "step_id": "step_3",
      "step_number": 3,
      "type": "thought",
      "content": "I found references to data protection in sections 12 and 15. Let me analyze these against GDPR Article 6 requirements.",
      "timestamp": "2025-01-15T11:10:20Z",
      "tokens_used": 180
    }
  ],
  "pagination": {
    "next_cursor": "eyJzdGVwX251bWJlciI6MTB9",
    "has_more": true,
    "total_count": 24
  }
}
```

**Status Codes:**
| Code | Description    |
|------|----------------|
| 200  | Success        |
| 401  | Unauthorized   |
| 404  | Session not found |
| 500  | Internal error |

**Test Cases:**

| # | Description            | Input              | Expected Status | Expected Result          |
|---|------------------------|--------------------|-----------------|--------------------------|
| 1 | List all steps         | Valid session_id   | 200             | Steps array              |
| 2 | Paginated steps        | limit=5            | 200             | 5 steps                  |
| 3 | Non-existent session   | sess_nonexistent   | 404             | Not found error          |

---

## 14. Evaluation APIs

### 14.1 POST /api/v1/eval/runs

**Purpose:** Run an evaluation benchmark on the AI pipeline.

**Method:** `POST`  
**URL:** `/api/v1/eval/runs`

**Request Body:**

```json
{
  "eval_type": "qa_accuracy",
  "dataset_id": "dataset_legal_v2",
  "model": "gpt-4o",
  "config": {
    "num_samples": 50,
    "metrics": ["accuracy", "f1", "latency"],
    "chunk_size": 1000,
    "embedding_model": "text-embedding-3-small"
  },
  "tags": ["baseline", "v2.1"]
}
```

**Schema:**

| Field          | Type    | Required | Default | Description                         |
|----------------|---------|----------|---------|-------------------------------------|
| `eval_type`    | string  | Yes      | —       | Type: qa_accuracy, extraction_f1, risk_detection |
| `dataset_id`   | string  | Yes      | —       | Evaluation dataset identifier       |
| `model`        | string  | No       | gpt-4o  | LLM model to evaluate               |
| `config`       | object  | No       | {}      | Evaluation configuration            |
| `tags`         | array   | No       | []      | Tags for this run (max 10)          |

**Validation Rules:**
- `eval_type` must be one of: `qa_accuracy`, `extraction_f1`, `risk_detection`, `end_to_end`
- `dataset_id` must reference an existing dataset
- `config.num_samples` must be between 1 and 1000
- `config.metrics` items must be one of: `accuracy`, `precision`, `recall`, `f1`, `latency`, `cost`
- `tags` max 10 items, each max 50 characters

**Response (202 Accepted):**

```json
{
  "data": {
    "run_id": "eval_d7e8f9",
    "eval_type": "qa_accuracy",
    "status": "running",
    "dataset_id": "dataset_legal_v2",
    "total_samples": 50,
    "processed_samples": 0,
    "created_at": "2025-01-15T11:30:00Z"
  }
}
```

**Status Codes:**
| Code | Description               |
|------|---------------------------|
| 202  | Evaluation started        |
| 400  | Invalid parameters        |
| 401  | Unauthorized              |
| 403  | Forbidden (admin only)    |
| 404  | Dataset not found         |
| 500  | Internal error            |
| 503  | AI service unavailable    |

**Test Cases:**

| # | Description                 | Input                                  | Expected Status | Expected Result          |
|---|-----------------------------|----------------------------------------|-----------------|--------------------------|
| 1 | Valid eval run              | qa_accuracy + valid dataset            | 202             | Eval started             |
| 2 | Custom config               | config with num_samples=100            | 202             | Eval started             |
| 3 | Invalid eval_type           | eval_type="unknown"                    | 400             | Validation error         |
| 4 | Non-existent dataset        | dataset_id="missing"                   | 404             | Not found error          |
| 5 | num_samples out of range    | num_samples=2000                       | 400             | Validation error         |
| 6 | Invalid metric              | metrics=["bleu"]                       | 400             | Validation error         |
| 7 | Non-admin user              | (user without admin role)              | 403             | Forbidden error          |

---

### 14.2 GET /api/v1/eval/runs/{run_id}

**Purpose:** Get evaluation run results.

**Method:** `GET`  
**URL:** `/api/v1/eval/runs/{run_id}`

**Path Parameters:**

| Parameter | Type   | Required | Description       |
|-----------|--------|----------|-------------------|
| `run_id`  | string | Yes      | Eval run identifier|

**Response (200 OK):**

```json
{
  "data": {
    "run_id": "eval_d7e8f9",
    "eval_type": "qa_accuracy",
    "status": "completed",
    "dataset_id": "dataset_legal_v2",
    "model": "gpt-4o",
    "config": {
      "num_samples": 50,
      "metrics": ["accuracy", "f1", "latency"],
      "chunk_size": 1000,
      "embedding_model": "text-embedding-3-small"
    },
    "results": {
      "accuracy": 0.87,
      "f1": 0.84,
      "latency": {
        "mean_ms": 3200,
        "p50_ms": 2800,
        "p95_ms": 5500,
        "p99_ms": 8200
      },
      "total_samples": 50,
      "correct_samples": 43,
      "failed_samples": 2
    },
    "tags": ["baseline", "v2.1"],
    "cost_estimate_usd": 4.25,
    "created_at": "2025-01-15T11:30:00Z",
    "completed_at": "2025-01-15T11:45:00Z",
    "duration_ms": 900000,
    "created_by": "user_xyz789"
  }
}
```

**Status Codes:**
| Code | Description    |
|------|----------------|
| 200  | Success        |
| 401  | Unauthorized   |
| 404  | Not found      |
| 500  | Internal error |

**Test Cases:**

| # | Description              | Input             | Expected Status | Expected Result              |
|---|--------------------------|-------------------|-----------------|------------------------------|
| 1 | Get completed eval       | Valid run_id      | 200             | Full results                 |
| 2 | Get running eval         | Running run_id    | 200             | Status "running"             |
| 3 | Non-existent eval run    | eval_nonexistent  | 404             | Not found error              |

---

## 15. System APIs

### 15.1 GET /api/v1/health

**Purpose:** Health check endpoint for load balancers and monitoring.

**Method:** `GET`  
**URL:** `/api/v1/health`  
**Authentication:** Not required

**Response (200 OK):**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 86400,
  "timestamp": "2025-01-15T12:00:00Z",
  "dependencies": {
    "database": {"status": "healthy", "latency_ms": 5},
    "redis": {"status": "healthy", "latency_ms": 2},
    "vector_db": {"status": "healthy", "latency_ms": 8},
    "openai": {"status": "healthy", "latency_ms": 150}
  }
}
```

**Response (503 Service Unavailable):**

```json
{
  "status": "unhealthy",
  "version": "1.0.0",
  "uptime_seconds": 86400,
  "timestamp": "2025-01-15T12:00:00Z",
  "dependencies": {
    "database": {"status": "healthy", "latency_ms": 5},
    "redis": {"status": "healthy", "latency_ms": 2},
    "vector_db": {"status": "unhealthy", "error": "Connection refused"},
    "openai": {"status": "healthy", "latency_ms": 150}
  }
}
```

**Status Codes:**
| Code | Description                 |
|------|-----------------------------|
| 200  | All dependencies healthy    |
| 503  | One or more deps unhealthy  |

**Test Cases:**

| # | Description                  | Input          | Expected Status | Expected Result              |
|---|------------------------------|----------------|-----------------|------------------------------|
| 1 | All services healthy         | —              | 200             | status="healthy"             |
| 2 | Database down                | (db failure)   | 503             | status="unhealthy"           |
| 3 | No auth required             | No token       | 200             | Succeeds without auth        |

---

### 15.2 GET /api/v1/metrics

**Purpose:** Prometheus-compatible metrics endpoint.

**Method:** `GET`  
**URL:** `/api/v1/metrics`  
**Content-Type:** `text/plain; version=0.0.4; charset=utf-8`

**Response (200 OK):**

```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",endpoint="/api/v1/documents",status="200"} 15234
http_requests_total{method="POST",endpoint="/api/v1/documents/upload",status="201"} 892

# HELP http_request_duration_seconds Request duration histogram
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{method="GET",endpoint="/api/v1/documents",le="0.1"} 14000
http_request_duration_seconds_bucket{method="GET",endpoint="/api/v1/documents",le="0.5"} 15100
http_request_duration_seconds_bucket{method="GET",endpoint="/api/v1/documents",le="1"} 15200
http_request_duration_seconds_bucket{method="GET",endpoint="/api/v1/documents",le="+Inf"} 15234

# HELP documents_total Total documents by status
# TYPE documents_total gauge
documents_total{status="uploaded"} 120
documents_total{status="parsed"} 3500
documents_total{status="failed"} 15

# HELP active_tasks_total Currently running tasks
# TYPE active_tasks_total gauge
active_tasks_total{type="parse"} 3
active_tasks_total{type="extract"} 1

# HELP ai_tokens_used_total Total AI tokens consumed
# TYPE ai_tokens_used_total counter
ai_tokens_used_total{model="gpt-4o",operation="ask"} 2500000
ai_tokens_used_total{model="text-embedding-3-small",operation="embed"} 5000000
```

**Status Codes:**
| Code | Description    |
|------|----------------|
| 200  | Metrics data   |
| 401  | Unauthorized   |

**Test Cases:**

| # | Description             | Input          | Expected Status | Expected Result              |
|---|-------------------------|----------------|-----------------|------------------------------|
| 1 | Retrieve metrics        | —              | 200             | Prometheus text format       |
| 2 | Requires auth           | No token       | 401             | Unauthorized error           |

---

## 16. Common Models

### 16.1 DocumentStatus

Enum: `uploaded`, `parsing`, `parsed`, `extraction_pending`, `extracted`, `failed`

### 16.2 TaskStatus

Enum: `pending`, `running`, `completed`, `failed`, `cancelled`

### 16.3 TaskType

Enum: `parse`, `extract`, `risks`, `checklist`, `report`, `agent`

### 16.4 RiskSeverity

Enum: `low`, `medium`, `high`, `critical`

### 16.5 RiskCategory

Enum: `legal`, `financial`, `compliance`, `operational`, `reputational`, `technical`

### 16.6 ChecklistPriority

Enum: `required`, `recommended`, `optional`

### 16.7 ChecklistStatus

Enum: `pending`, `in_progress`, `completed`, `not_applicable`

### 16.8 ReportFormat

Enum: `pdf`, `markdown`, `html`, `json`

### 16.9 AgentStepType

Enum: `thought`, `action`, `observation`, `error`

### 16.10 Error

```typescript
interface ApiError {
  error: {
    code: string;          // Machine-readable error code
    message: string;       // Human-readable description
    request_id: string;    // Request trace ID
    details?: Array<{      // Validation details (optional)
      field: string;
      issue: string;
      value?: any;
    }>;
    timestamp: string;     // ISO 8601 datetime
  };
}
```

### 16.11 PaginatedResponse<T>

```typescript
interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    next_cursor: string | null;
    prev_cursor: string | null;
    has_more: boolean;
    total_count: number;
  };
}
```

---

## 17. Test Cases Summary

### Happy Path Tests

| Endpoint                           | Test                                   | Expected |
|------------------------------------|----------------------------------------|----------|
| POST /documents/upload             | Upload valid PDF                       | 201      |
| GET /documents                     | List with defaults                     | 200      |
| GET /documents/{id}                | Get existing document                  | 200      |
| DELETE /documents/{id}             | Delete existing document               | 200      |
| POST /documents/{id}/parse         | Parse with defaults                    | 202      |
| POST /documents/{id}/extract       | Extract with valid fields              | 202      |
| POST /documents/{id}/ask           | Ask valid question                     | 200      |
| POST /documents/{id}/risks         | Analyze with defaults                  | 202      |
| POST /documents/{id}/checklist     | Generate with defaults                 | 202      |
| GET /tasks                         | List all tasks                         | 200      |
| PATCH /tasks/{id}                  | Cancel running task                    | 200      |
| POST /reports                      | Generate single-doc report             | 202      |
| GET /reports/{id}                  | Get completed report                   | 200      |
| GET /reports/{id}/export           | Download PDF                           | 200      |
| POST /agent/run                    | Valid agent session                    | 202      |
| GET /agent/sessions/{id}           | Get completed session                  | 200      |
| GET /agent/sessions/{id}/steps     | List all steps                         | 200      |
| POST /eval/runs                    | Start eval run                         | 202      |
| GET /eval/runs/{id}               | Get completed eval                     | 200      |
| GET /health                        | All services up                        | 200      |
| GET /metrics                       | Retrieve metrics                       | 200      |

### Validation Error Tests

| Scenario                           | Expected | Error Code             |
|------------------------------------|----------|------------------------|
| Missing required field             | 400      | BAD_REQUEST            |
| Invalid enum value                 | 400      | BAD_REQUEST            |
| String too long                    | 400      | BAD_REQUEST            |
| String too short                   | 400      | BAD_REQUEST            |
| Number out of range                | 400      | BAD_REQUEST            |
| Invalid JSON in metadata           | 400      | BAD_REQUEST            |
| Invalid cursor format              | 400      | BAD_REQUEST            |

### Auth Error Tests

| Scenario                           | Expected | Error Code             |
|------------------------------------|----------|------------------------|
| Missing Authorization header       | 401      | UNAUTHORIZED           |
| Expired JWT token                  | 401      | UNAUTHORIZED           |
| Invalid JWT signature              | 401      | UNAUTHORIZED           |
| Insufficient role/permissions      | 403      | FORBIDDEN              |

### Not Found Tests

| Scenario                           | Expected | Error Code             |
|------------------------------------|----------|------------------------|
| Non-existent document ID           | 404      | NOT_FOUND              |
| Non-existent task ID               | 404      | NOT_FOUND              |
| Non-existent report ID             | 404      | NOT_FOUND              |
| Non-existent session ID            | 404      | NOT_FOUND              |
| Non-existent eval run ID           | 404      | NOT_FOUND              |

### Conflict Tests

| Scenario                           | Expected | Error Code             |
|------------------------------------|----------|------------------------|
| Delete document while processing   | 409      | CONFLICT               |
| Parse already parsed document      | 409      | CONFLICT               |
| Extract from unparsed document     | 409      | CONFLICT               |
| Ask on unparsed document           | 409      | CONFLICT               |
| Cancel completed task              | 409      | CONFLICT               |
| Retry running task                 | 409      | CONFLICT               |
| Download incomplete report         | 409      | CONFLICT               |

### Rate Limiting Tests

| Scenario                           | Expected | Error Code             |
|------------------------------------|----------|------------------------|
| Exceed requests per minute         | 429      | RATE_LIMIT_EXCEEDED    |
| Verify rate limit headers present  | 200      | —                      |
| Retry after wait period            | 200      | —                      |

---

*End of API Specification*
