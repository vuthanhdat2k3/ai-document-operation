# Database Schema Documentation

**Database:** PostgreSQL 16
**Project:** AI Document Operations Agent
**Last Updated:** 2026-06-11

---

## Table of Contents

1. [Naming Conventions](#naming-conventions)
2. [ER Diagram](#er-diagram)
3. [Table Definitions](#table-definitions)
4. [Index Strategy](#index-strategy)
5. [Partitioning Strategy](#partitioning-strategy)
6. [SQLAlchemy Models](#sqlalchemy-models)
7. [Alembic Migration Strategy](#alembic-migration-strategy)
8. [Connection Pooling](#connection-pooling)
9. [Migration Rules](#migration-rules)

---

## Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Tables | `snake_case`, plural | `documents`, `risk_items` |
| Columns | `snake_case` | `created_at`, `user_id` |
| Primary Keys | `id` (UUID) | `id UUID PRIMARY KEY` |
| Foreign Keys | `{referenced_table_singular}_id` | `user_id`, `document_id` |
| Indexes | `idx_{table}_{columns}` | `idx_documents_user_id_status` |
| Unique Constraints | `uq_{table}_{columns}` | `uq_users_email` |
| Check Constraints | `ck_{table}_{condition}` | `ck_tasks_status_valid` |
| Foreign Key Constraints | `fk_{table}_{ref}` | `fk_documents_user_id` |
| Soft Delete Column | `deleted_at` | `deleted_at TIMESTAMPTZ NULL` |
| Timestamp Columns | `created_at`, `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT NOW()` |

---

## ER Diagram

```
                              +-------------------+
                              |      users        |
                              +-------------------+
                              | id (PK, UUID)     |
                              | email (UQ)        |
                              | role              |
                              +--------+----------+
                                       |
          +----------------------------+----------------------------+
          |                            |                            |
+---------v----------+    +------------v-----------+    +-----------v----------+
|   documents        |    |   agent_sessions       |    |   audit_logs         |
+--------------------+    +------------------------+    +----------------------+
| id (PK, UUID)      |    | id (PK, UUID)          |    | id (PK, UUID)        |
| user_id (FK)       |    | user_id (FK)           |    | user_id (FK)         |
| status             |    | status                 |    | action               |
+--------+-----------+    +-----------+------------+    | entity_type          |
         |                            |                 | entity_id            |
         |                            |                 +----------------------+
    +----+----+                 +-----+------+
    |         |                 |            |
+---v---+ +---v-----------+ +--v--------+ +-v-----------+
| doc_  | | doc_chunks    | | agent_    | | tool_calls  |
| pages | +---------------+ | steps     | +-------------+
+-------+ | document_id   | +-----------+ | agent_step_ |
| doc_id| | embedding_ref | | session_id| | id (FK)     |
+-------+ +---------------+ +-----------+ +-------------+
    |
    |
+---v-----------+       +------------------+       +------------------+
| extracted_    |       | extraction_      |       | eval_datasets    |
| fields        |       | schemas          |       +------------------+
+---------------+       +------------------+       | id (PK, UUID)    |
| document_id   |       | id (PK, UUID)    |       +--------+---------+
| schema_id(FK) |<------+| name             |                |
+---------------+       +------------------+       +--------v---------+
                                                | eval_runs        |
+---------------+       +------------------+       +------------------+
| risk_items    |       | tasks            |       | dataset_id (FK)  |
+---------------+       +------------------+       | session_id (FK)  |
| document_id   |       | document_id (FK) |       +------------------+
+---------------+       | assigned_to (FK) |
                        +------------------+

+------------------+
| reports          |
+------------------+
| id (PK, UUID)    |
| user_id (FK)     |
| document_id (FK) |
| session_id (FK)  |
+------------------+
```

### Relationship Summary

```
users 1──N documents
users 1──N agent_sessions
users 1──N tasks (assigned_to)
users 1──N reports
users 1──N audit_logs
documents 1──N document_pages
documents 1──N document_chunks
documents 1──N extracted_fields
documents 1──N risk_items
documents 1──N tasks
documents 1──N reports
extraction_schemas 1──N extracted_fields
agent_sessions 1──N agent_steps
agent_sessions 1──N eval_runs
agent_sessions 1──N reports
agent_steps 1──N tool_calls
eval_datasets 1──N eval_runs
```

---

## Table Definitions

### 1. `users`

**Purpose:** Stores user accounts for authentication, authorization, and activity tracking.

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(320) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    role            VARCHAR(50) NOT NULL DEFAULT 'viewer',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ NULL,
    preferences     JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ NULL,

    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT ck_users_role_valid CHECK (role IN ('admin', 'operator', 'analyst', 'viewer'))
);

CREATE INDEX idx_users_email ON users (email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_role_active ON users (role, is_active) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_deleted_at ON users (deleted_at) WHERE deleted_at IS NOT NULL;
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique identifier |
| `email` | VARCHAR(320) | NOT NULL, UNIQUE | Login email address |
| `hashed_password` | VARCHAR(255) | NOT NULL | bcrypt/argon2 hash |
| `full_name` | VARCHAR(255) | NOT NULL | Display name |
| `role` | VARCHAR(50) | NOT NULL, DEFAULT 'viewer', CHECK | User role |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | Account enabled flag |
| `last_login_at` | TIMESTAMPTZ | NULL | Last successful login |
| `preferences` | JSONB | NOT NULL, DEFAULT '{}' | User settings |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation time |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last modification time |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft delete timestamp |

**Example Record:**
```json
{
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "email": "jane.doe@example.com",
    "hashed_password": "$argon2id$v=19$m=65536,t=3,p=4$...",
    "full_name": "Jane Doe",
    "role": "operator",
    "is_active": true,
    "last_login_at": "2026-06-11T07:30:00Z",
    "preferences": {"theme": "dark", "language": "en"},
    "created_at": "2026-01-15T10:00:00Z",
    "updated_at": "2026-06-11T07:30:00Z",
    "deleted_at": null
}
```

---

### 2. `documents`

**Purpose:** Metadata for uploaded documents including file info, processing status, and classification.

```sql
CREATE TABLE documents (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL,
    filename          VARCHAR(500) NOT NULL,
    original_filename VARCHAR(500) NOT NULL,
    mime_type         VARCHAR(100) NOT NULL,
    file_size_bytes   BIGINT NOT NULL,
    storage_path      VARCHAR(1000) NOT NULL,
    storage_backend   VARCHAR(50) NOT NULL DEFAULT 'local',
    page_count        INTEGER NULL,
    status            VARCHAR(50) NOT NULL DEFAULT 'uploaded',
    document_type     VARCHAR(100) NULL,
    classification    JSONB NULL,
    metadata          JSONB NOT NULL DEFAULT '{}',
    checksum_sha256   VARCHAR(64) NOT NULL,
    uploaded_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at      TIMESTAMPTZ NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at        TIMESTAMPTZ NULL,

    CONSTRAINT fk_documents_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT ck_documents_status_valid CHECK (status IN (
        'uploaded', 'queued', 'processing', 'ocr_complete',
        'extraction_complete', 'reviewed', 'completed', 'failed', 'archived'
    )),
    CONSTRAINT ck_documents_file_size_positive CHECK (file_size_bytes > 0),
    CONSTRAINT ck_documents_page_count_positive CHECK (page_count IS NULL OR page_count > 0)
);

CREATE INDEX idx_documents_user_id ON documents (user_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_documents_user_id_status ON documents (user_id, status) WHERE deleted_at IS NULL;
CREATE INDEX idx_documents_status ON documents (status) WHERE deleted_at IS NULL;
CREATE INDEX idx_documents_document_type ON documents (document_type) WHERE deleted_at IS NULL;
CREATE INDEX idx_documents_uploaded_at ON documents (uploaded_at DESC);
CREATE INDEX idx_documents_checksum ON documents (checksum_sha256);
CREATE INDEX idx_documents_deleted_at ON documents (deleted_at) WHERE deleted_at IS NOT NULL;
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Unique identifier |
| `user_id` | UUID | FK → users.id, NOT NULL | Uploader |
| `filename` | VARCHAR(500) | NOT NULL | Stored filename (UUID-based) |
| `original_filename` | VARCHAR(500) | NOT NULL | Original upload name |
| `mime_type` | VARCHAR(100) | NOT NULL | MIME type (application/pdf, etc.) |
| `file_size_bytes` | BIGINT | NOT NULL, CHECK > 0 | File size |
| `storage_path` | VARCHAR(1000) | NOT NULL | Full storage path |
| `storage_backend` | VARCHAR(50) | NOT NULL, DEFAULT 'local' | Storage backend identifier |
| `page_count` | INTEGER | NULL, CHECK > 0 | Number of pages |
| `status` | VARCHAR(50) | NOT NULL, DEFAULT 'uploaded', CHECK | Processing pipeline status |
| `document_type` | VARCHAR(100) | NULL | Classified document type |
| `classification` | JSONB | NULL | ML classification results |
| `metadata` | JSONB | NOT NULL, DEFAULT '{}' | Arbitrary metadata |
| `checksum_sha256` | VARCHAR(64) | NOT NULL | File integrity hash |
| `uploaded_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Upload timestamp |
| `processed_at` | TIMESTAMPTZ | NULL | Processing completion time |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last modification |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft delete |

**Example Record:**
```json
{
    "id": "d1e2f3a4-b5c6-7890-1234-567890abcdef",
    "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "filename": "f47ac10b-58cc-4372-a567-0e02b2c3d479.pdf",
    "original_filename": "invoice_2026_06.pdf",
    "mime_type": "application/pdf",
    "file_size_bytes": 2457600,
    "storage_path": "/data/documents/2026/06/f47ac10b-58cc-4372-a567-0e02b2c3d479.pdf",
    "storage_backend": "local",
    "page_count": 3,
    "status": "completed",
    "document_type": "invoice",
    "classification": {"model": "doc-classifier-v2", "confidence": 0.95},
    "metadata": {"source": "email", "batch_id": "B20260611"},
    "checksum_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "uploaded_at": "2026-06-11T07:00:00Z",
    "processed_at": "2026-06-11T07:05:30Z",
    "created_at": "2026-06-11T07:00:00Z",
    "updated_at": "2026-06-11T07:05:30Z",
    "deleted_at": null
}
```

---

### 3. `document_pages`

**Purpose:** Per-page OCR data including extracted text, confidence scores, and physical dimensions.

```sql
CREATE TABLE document_pages (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id       UUID NOT NULL,
    page_number       INTEGER NOT NULL,
    ocr_text          TEXT NULL,
    ocr_confidence    REAL NULL,
    language          VARCHAR(10) NULL,
    width_px          INTEGER NULL,
    height_px         INTEGER NULL,
    dpi               INTEGER NULL,
    image_storage_path VARCHAR(1000) NULL,
    ocr_engine        VARCHAR(50) NULL,
    ocr_raw_output    JSONB NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_document_pages_document_id FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    CONSTRAINT uq_document_pages_doc_page UNIQUE (document_id, page_number),
    CONSTRAINT ck_document_pages_page_number_positive CHECK (page_number > 0),
    CONSTRAINT ck_document_pages_confidence_range CHECK (ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 1)),
    CONSTRAINT ck_document_pages_dimensions_positive CHECK (
        (width_px IS NULL OR width_px > 0) AND
        (height_px IS NULL OR height_px > 0) AND
        (dpi IS NULL OR dpi > 0)
    )
);

CREATE INDEX idx_document_pages_document_id ON document_pages (document_id);
CREATE INDEX idx_document_pages_doc_page ON document_pages (document_id, page_number);
CREATE INDEX idx_document_pages_confidence ON document_pages (ocr_confidence) WHERE ocr_confidence IS NOT NULL AND ocr_confidence < 0.7;
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Unique identifier |
| `document_id` | UUID | FK → documents.id, NOT NULL, CASCADE | Parent document |
| `page_number` | INTEGER | NOT NULL, CHECK > 0, UNIQUE with document_id | 1-indexed page number |
| `ocr_text` | TEXT | NULL | Extracted OCR text |
| `ocr_confidence` | REAL | NULL, CHECK 0–1 | OCR confidence score |
| `language` | VARCHAR(10) | NULL | Detected language code |
| `width_px` | INTEGER | NULL, CHECK > 0 | Page width in pixels |
| `height_px` | INTEGER | NULL, CHECK > 0 | Page height in pixels |
| `dpi` | INTEGER | NULL, CHECK > 0 | Dots per inch |
| `image_storage_path` | VARCHAR(1000) | NULL | Path to rendered page image |
| `ocr_engine` | VARCHAR(50) | NULL | OCR engine used |
| `ocr_raw_output` | JSONB | NULL | Raw engine output |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last modification |

**Example Record:**
```json
{
    "id": "p1a2b3c4-d5e6-7890-abcd-ef1234567890",
    "document_id": "d1e2f3a4-b5c6-7890-1234-567890abcdef",
    "page_number": 1,
    "ocr_text": "INVOICE #12345\nDate: 2026-06-01\nBill To: Acme Corp...",
    "ocr_confidence": 0.94,
    "language": "en",
    "width_px": 2480,
    "height_px": 3508,
    "dpi": 300,
    "image_storage_path": "/data/pages/d1e2f3a4/page_1.png",
    "ocr_engine": "tesseract-5.3",
    "ocr_raw_output": {"blocks": 42, "words": 312},
    "created_at": "2026-06-11T07:01:00Z",
    "updated_at": "2026-06-11T07:01:00Z"
}
```

---

### 4. `document_chunks`

**Purpose:** Text chunks derived from documents with embedding metadata for vector search and retrieval.

```sql
CREATE TABLE document_chunks (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id       UUID NOT NULL,
    page_number       INTEGER NULL,
    chunk_index       INTEGER NOT NULL,
    chunk_text        TEXT NOT NULL,
    token_count       INTEGER NULL,
    embedding_model   VARCHAR(100) NULL,
    embedding_dim     INTEGER NULL,
    embedding_ref     VARCHAR(500) NULL,
    chunk_metadata    JSONB NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_document_chunks_document_id FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    CONSTRAINT uq_document_chunks_doc_chunk UNIQUE (document_id, chunk_index),
    CONSTRAINT ck_document_chunks_chunk_index_positive CHECK (chunk_index >= 0),
    CONSTRAINT ck_document_chunks_token_count_positive CHECK (token_count IS NULL OR token_count > 0),
    CONSTRAINT ck_document_chunks_embedding_dim_positive CHECK (embedding_dim IS NULL OR embedding_dim > 0)
);

CREATE INDEX idx_document_chunks_document_id ON document_chunks (document_id);
CREATE INDEX idx_document_chunks_doc_chunk ON document_chunks (document_id, chunk_index);
CREATE INDEX idx_document_chunks_embedding_model ON document_chunks (embedding_model) WHERE embedding_model IS NOT NULL;
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Unique identifier |
| `document_id` | UUID | FK → documents.id, NOT NULL, CASCADE | Parent document |
| `page_number` | INTEGER | NULL | Source page number |
| `chunk_index` | INTEGER | NOT NULL, CHECK >= 0, UNIQUE with document_id | Ordering within document |
| `chunk_text` | TEXT | NOT NULL | The text content |
| `token_count` | INTEGER | NULL, CHECK > 0 | Token count for the chunk |
| `embedding_model` | VARCHAR(100) | NULL | Model used for embedding |
| `embedding_dim` | INTEGER | NULL, CHECK > 0 | Embedding vector dimension |
| `embedding_ref` | VARCHAR(500) | NULL | Reference to vector store (e.g., Pinecone ID) |
| `chunk_metadata` | JSONB | NOT NULL, DEFAULT '{}' | Additional metadata |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last modification |

**Example Record:**
```json
{
    "id": "c1a2b3c4-d5e6-7890-abcd-ef1234567890",
    "document_id": "d1e2f3a4-b5c6-7890-1234-567890abcdef",
    "page_number": 1,
    "chunk_index": 0,
    "chunk_text": "INVOICE #12345 Date: 2026-06-01 Bill To: Acme Corp Total: $4,500.00",
    "token_count": 24,
    "embedding_model": "text-embedding-3-small",
    "embedding_dim": 1536,
    "embedding_ref": "pinecone://chunks/c1a2b3c4-d5e6-7890",
    "chunk_metadata": {"section": "header", "overlap": false},
    "created_at": "2026-06-11T07:02:00Z",
    "updated_at": "2026-06-11T07:02:00Z"
}
```

---

### 5. `extraction_schemas`

**Purpose:** Defines field extraction schemas (templates) for different document types specifying which fields to extract.

```sql
CREATE TABLE extraction_schemas (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    document_type   VARCHAR(100) NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    description     TEXT NULL,
    fields_schema   JSONB NOT NULL,
    prompt_template TEXT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_by      UUID NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ NULL,

    CONSTRAINT fk_extraction_schemas_created_by FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT uq_extraction_schemas_name_version UNIQUE (name, version),
    CONSTRAINT ck_extraction_schemas_version_positive CHECK (version > 0)
);

CREATE INDEX idx_extraction_schemas_document_type ON extraction_schemas (document_type) WHERE deleted_at IS NULL;
CREATE INDEX idx_extraction_schemas_active ON extraction_schemas (is_active) WHERE deleted_at IS NULL AND is_active = TRUE;
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Unique identifier |
| `name` | VARCHAR(255) | NOT NULL, UNIQUE with version | Schema name |
| `document_type` | VARCHAR(100) | NOT NULL | Target document type |
| `version` | INTEGER | NOT NULL, DEFAULT 1, CHECK > 0, UNIQUE with name | Schema version |
| `description` | TEXT | NULL | Human-readable description |
| `fields_schema` | JSONB | NOT NULL | JSON Schema defining fields to extract |
| `prompt_template` | TEXT | NULL | LLM prompt template |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | Whether schema is in use |
| `created_by` | UUID | FK → users.id, NULL, SET NULL | Creator |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last modification |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft delete |

**Example Record:**
```json
{
    "id": "s1a2b3c4-d5e6-7890-abcd-ef1234567890",
    "name": "standard_invoice",
    "document_type": "invoice",
    "version": 3,
    "description": "Standard invoice extraction with vendor, line items, totals",
    "fields_schema": {
        "type": "object",
        "properties": {
            "invoice_number": {"type": "string"},
            "date": {"type": "string", "format": "date"},
            "vendor_name": {"type": "string"},
            "total_amount": {"type": "number"},
            "currency": {"type": "string"},
            "line_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "quantity": {"type": "number"},
                        "unit_price": {"type": "number"}
                    }
                }
            }
        },
        "required": ["invoice_number", "total_amount"]
    },
    "prompt_template": "Extract the following fields from this invoice:\n{{fields_schema}}\n\nDocument text:\n{{document_text}}",
    "is_active": true,
    "created_by": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "created_at": "2026-03-01T10:00:00Z",
    "updated_at": "2026-05-15T14:30:00Z",
    "deleted_at": null
}
```

---

### 6. `extracted_fields`

**Purpose:** Stores actual extracted field values from documents, linked to extraction schemas.

```sql
CREATE TABLE extracted_fields (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL,
    schema_id       UUID NOT NULL,
    field_name      VARCHAR(255) NOT NULL,
    field_value     JSONB NULL,
    raw_text        TEXT NULL,
    confidence      REAL NULL,
    page_number     INTEGER NULL,
    bounding_box    JSONB NULL,
    extraction_model VARCHAR(100) NULL,
    is_verified     BOOLEAN NOT NULL DEFAULT FALSE,
    verified_by     UUID NULL,
    verified_at     TIMESTAMPTZ NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_extracted_fields_document_id FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    CONSTRAINT fk_extracted_fields_schema_id FOREIGN KEY (schema_id) REFERENCES extraction_schemas(id) ON DELETE RESTRICT,
    CONSTRAINT fk_extracted_fields_verified_by FOREIGN KEY (verified_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT uq_extracted_fields_doc_schema_field UNIQUE (document_id, schema_id, field_name),
    CONSTRAINT ck_extracted_fields_confidence_range CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CONSTRAINT ck_extracted_fields_verified_consistency CHECK (
        (is_verified = FALSE AND verified_by IS NULL AND verified_at IS NULL) OR
        (is_verified = TRUE AND verified_by IS NOT NULL AND verified_at IS NOT NULL)
    )
);

CREATE INDEX idx_extracted_fields_document_id ON extracted_fields (document_id);
CREATE INDEX idx_extracted_fields_schema_id ON extracted_fields (schema_id);
CREATE INDEX idx_extracted_fields_doc_schema ON extracted_fields (document_id, schema_id);
CREATE INDEX idx_extracted_fields_unverified ON extracted_fields (document_id) WHERE is_verified = FALSE AND confidence < 0.8;
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Unique identifier |
| `document_id` | UUID | FK → documents.id, NOT NULL, CASCADE | Source document |
| `schema_id` | UUID | FK → extraction_schemas.id, NOT NULL, RESTRICT | Extraction schema used |
| `field_name` | VARCHAR(255) | NOT NULL, UNIQUE with document_id and schema_id | Field name in schema |
| `field_value` | JSONB | NULL | Extracted value (typed) |
| `raw_text` | TEXT | NULL | Original text from document |
| `confidence` | REAL | NULL, CHECK 0–1 | Extraction confidence |
| `page_number` | INTEGER | NULL | Source page |
| `bounding_box` | JSONB | NULL | Location on page `{x, y, w, h}` |
| `extraction_model` | VARCHAR(100) | NULL | Model used |
| `is_verified` | BOOLEAN | NOT NULL, DEFAULT FALSE | Human verification flag |
| `verified_by` | UUID | FK → users.id, NULL, SET NULL | Verifier user |
| `verified_at` | TIMESTAMPTZ | NULL | Verification timestamp |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last modification |

**Example Record:**
```json
{
    "id": "e1a2b3c4-d5e6-7890-abcd-ef1234567890",
    "document_id": "d1e2f3a4-b5c6-7890-1234-567890abcdef",
    "schema_id": "s1a2b3c4-d5e6-7890-abcd-ef1234567890",
    "field_name": "total_amount",
    "field_value": 4500.00,
    "raw_text": "$4,500.00",
    "confidence": 0.97,
    "page_number": 1,
    "bounding_box": {"x": 450, "y": 800, "w": 120, "h": 25},
    "extraction_model": "gpt-4o-mini",
    "is_verified": true,
    "verified_by": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "verified_at": "2026-06-11T08:00:00Z",
    "created_at": "2026-06-11T07:03:00Z",
    "updated_at": "2026-06-11T08:00:00Z"
}
```

---

### 7. `risk_items`

**Purpose:** Detected risks, anomalies, compliance issues, or flags identified during document processing.

```sql
CREATE TABLE risk_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL,
    category        VARCHAR(100) NOT NULL,
    severity        VARCHAR(20) NOT NULL DEFAULT 'medium',
    title           VARCHAR(500) NOT NULL,
    description     TEXT NULL,
    evidence        JSONB NULL,
    page_number     INTEGER NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'open',
    resolution      TEXT NULL,
    resolved_by     UUID NULL,
    resolved_at     TIMESTAMPTZ NULL,
    detected_by     VARCHAR(100) NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ NULL,

    CONSTRAINT fk_risk_items_document_id FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    CONSTRAINT fk_risk_items_resolved_by FOREIGN KEY (resolved_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT ck_risk_items_severity_valid CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    CONSTRAINT ck_risk_items_status_valid CHECK (status IN ('open', 'in_review', 'resolved', 'dismissed', 'false_positive'))
);

CREATE INDEX idx_risk_items_document_id ON risk_items (document_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_risk_items_severity ON risk_items (severity) WHERE deleted_at IS NULL AND status = 'open';
CREATE INDEX idx_risk_items_status ON risk_items (status) WHERE deleted_at IS NULL;
CREATE INDEX idx_risk_items_doc_severity ON risk_items (document_id, severity) WHERE deleted_at IS NULL;
CREATE INDEX idx_risk_items_category ON risk_items (category) WHERE deleted_at IS NULL;
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Unique identifier |
| `document_id` | UUID | FK → documents.id, NOT NULL, CASCADE | Source document |
| `category` | VARCHAR(100) | NOT NULL | Risk category |
| `severity` | VARCHAR(20) | NOT NULL, DEFAULT 'medium', CHECK | Severity level |
| `title` | VARCHAR(500) | NOT NULL | Short description |
| `description` | TEXT | NULL | Detailed description |
| `evidence` | JSONB | NULL | Supporting evidence data |
| `page_number` | INTEGER | NULL | Relevant page |
| `status` | VARCHAR(50) | NOT NULL, DEFAULT 'open', CHECK | Resolution status |
| `resolution` | TEXT | NULL | Resolution notes |
| `resolved_by` | UUID | FK → users.id, NULL, SET NULL | Resolver user |
| `resolved_at` | TIMESTAMPTZ | NULL | Resolution timestamp |
| `detected_by` | VARCHAR(100) | NULL | Detection method/agent |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last modification |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft delete |

**Example Record:**
```json
{
    "id": "r1a2b3c4-d5e6-7890-abcd-ef1234567890",
    "document_id": "d1e2f3a4-b5c6-7890-1234-567890abcdef",
    "category": "financial_discrepancy",
    "severity": "high",
    "title": "Line item total does not match sum of line items",
    "description": "Invoice states total of $4,500.00 but line items sum to $4,350.00",
    "evidence": {"stated_total": 4500.00, "calculated_total": 4350.00, "difference": 150.00},
    "page_number": 1,
    "status": "open",
    "resolution": null,
    "resolved_by": null,
    "resolved_at": null,
    "detected_by": "validation-agent-v1",
    "created_at": "2026-06-11T07:04:00Z",
    "updated_at": "2026-06-11T07:04:00Z",
    "deleted_at": null
}
```

---

### 8. `tasks`

**Purpose:** Action tasks and checklists generated from document processing, assigned to users for follow-up.

```sql
CREATE TABLE tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NULL,
    session_id      UUID NULL,
    assigned_to     UUID NULL,
    title           VARCHAR(500) NOT NULL,
    description     TEXT NULL,
    priority        VARCHAR(20) NOT NULL DEFAULT 'medium',
    status          VARCHAR(50) NOT NULL DEFAULT 'pending',
    due_date        DATE NULL,
    completed_at    TIMESTAMPTZ NULL,
    task_metadata   JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ NULL,

    CONSTRAINT fk_tasks_document_id FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL,
    CONSTRAINT fk_tasks_assigned_to FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT ck_tasks_priority_valid CHECK (priority IN ('critical', 'high', 'medium', 'low')),
    CONSTRAINT ck_tasks_status_valid CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled', 'blocked'))
);

CREATE INDEX idx_tasks_assigned_to ON tasks (assigned_to) WHERE deleted_at IS NULL AND status NOT IN ('completed', 'cancelled');
CREATE INDEX idx_tasks_document_id ON tasks (document_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_tasks_status ON tasks (status) WHERE deleted_at IS NULL;
CREATE INDEX idx_tasks_priority_status ON tasks (priority, status) WHERE deleted_at IS NULL;
CREATE INDEX idx_tasks_due_date ON tasks (due_date) WHERE deleted_at IS NULL AND status NOT IN ('completed', 'cancelled');
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Unique identifier |
| `document_id` | UUID | FK → documents.id, NULL, SET NULL | Related document |
| `session_id` | UUID | NULL | Agent session that created task |
| `assigned_to` | UUID | FK → users.id, NULL, SET NULL | Assigned user |
| `title` | VARCHAR(500) | NOT NULL | Task title |
| `description` | TEXT | NULL | Detailed description |
| `priority` | VARCHAR(20) | NOT NULL, DEFAULT 'medium', CHECK | Priority level |
| `status` | VARCHAR(50) | NOT NULL, DEFAULT 'pending', CHECK | Task status |
| `due_date` | DATE | NULL | Due date |
| `completed_at` | TIMESTAMPTZ | NULL | Completion timestamp |
| `task_metadata` | JSONB | NOT NULL, DEFAULT '{}' | Additional metadata |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last modification |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft delete |

**Example Record:**
```json
{
    "id": "t1a2b3c4-d5e6-7890-abcd-ef1234567890",
    "document_id": "d1e2f3a4-b5c6-7890-1234-567890abcdef",
    "session_id": "sess-a2b3c4d5-e6f7-8901-abcd-ef1234567890",
    "assigned_to": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "title": "Verify invoice total discrepancy",
    "description": "Invoice #12345 has a $150 discrepancy between stated total and line item sum",
    "priority": "high",
    "status": "pending",
    "due_date": "2026-06-13",
    "completed_at": null,
    "task_metadata": {"risk_item_id": "r1a2b3c4-d5e6-7890-abcd-ef1234567890"},
    "created_at": "2026-06-11T07:05:00Z",
    "updated_at": "2026-06-11T07:05:00Z",
    "deleted_at": null
}
```

---

### 9. `reports`

**Purpose:** Generated reports (summaries, analyses, compliance reports) from document processing sessions.

```sql
CREATE TABLE reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    document_id     UUID NULL,
    session_id      UUID NULL,
    report_type     VARCHAR(100) NOT NULL,
    title           VARCHAR(500) NOT NULL,
    content         JSONB NOT NULL,
    format          VARCHAR(20) NOT NULL DEFAULT 'json',
    storage_path    VARCHAR(1000) NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'generated',
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ NULL,

    CONSTRAINT fk_reports_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT fk_reports_document_id FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL,
    CONSTRAINT ck_reports_format_valid CHECK (format IN ('json', 'pdf', 'html', 'csv', 'markdown')),
    CONSTRAINT ck_reports_status_valid CHECK (status IN ('generating', 'generated', 'failed', 'expired'))
);

CREATE INDEX idx_reports_user_id ON reports (user_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_reports_document_id ON reports (document_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_reports_session_id ON reports (session_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_reports_type ON reports (report_type) WHERE deleted_at IS NULL;
CREATE INDEX idx_reports_generated_at ON reports (generated_at DESC);
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Unique identifier |
| `user_id` | UUID | FK → users.id, NOT NULL, RESTRICT | Report owner |
| `document_id` | UUID | FK → documents.id, NULL, SET NULL | Related document |
| `session_id` | UUID | NULL | Generating agent session |
| `report_type` | VARCHAR(100) | NOT NULL | Type of report |
| `title` | VARCHAR(500) | NOT NULL | Report title |
| `content` | JSONB | NOT NULL | Report content |
| `format` | VARCHAR(20) | NOT NULL, DEFAULT 'json', CHECK | Output format |
| `storage_path` | VARCHAR(1000) | NULL | File storage path |
| `status` | VARCHAR(50) | NOT NULL, DEFAULT 'generated', CHECK | Report status |
| `generated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Generation time |
| `expires_at` | TIMESTAMPTZ | NULL | Expiration time |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last modification |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft delete |

**Example Record:**
```json
{
    "id": "rep1a2b3c4-d5e6-7890-abcd-ef1234567890",
    "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "document_id": "d1e2f3a4-b5c6-7890-1234-567890abcdef",
    "session_id": "sess-a2b3c4d5-e6f7-8901-abcd-ef1234567890",
    "report_type": "document_summary",
    "title": "Invoice Analysis - #12345",
    "content": {"summary": "3-page invoice from Acme Corp", "total": 4500.00, "risks": 1},
    "format": "json",
    "storage_path": "/data/reports/rep1a2b3c4.json",
    "status": "generated",
    "generated_at": "2026-06-11T07:10:00Z",
    "expires_at": "2026-09-11T07:10:00Z",
    "created_at": "2026-06-11T07:10:00Z",
    "updated_at": "2026-06-11T07:10:00Z",
    "deleted_at": null
}
```

---

### 10. `agent_sessions`

**Purpose:** Tracks agent orchestration sessions including multi-step reasoning, tool usage, and outcomes.

```sql
CREATE TABLE agent_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    document_id     UUID NULL,
    agent_type      VARCHAR(100) NOT NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'running',
    input_data      JSONB NOT NULL DEFAULT '{}',
    output_data     JSONB NULL,
    error_message   TEXT NULL,
    model           VARCHAR(100) NULL,
    total_tokens    INTEGER NULL,
    total_cost_usd  NUMERIC(10, 6) NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_agent_sessions_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT fk_agent_sessions_document_id FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL,
    CONSTRAINT ck_agent_sessions_status_valid CHECK (status IN ('running', 'completed', 'failed', 'cancelled', 'timeout')),
    CONSTRAINT ck_agent_sessions_tokens_positive CHECK (total_tokens IS NULL OR total_tokens >= 0),
    CONSTRAINT ck_agent_sessions_cost_positive CHECK (total_cost_usd IS NULL OR total_cost_usd >= 0)
);

CREATE INDEX idx_agent_sessions_user_id ON agent_sessions (user_id);
CREATE INDEX idx_agent_sessions_document_id ON agent_sessions (document_id);
CREATE INDEX idx_agent_sessions_status ON agent_sessions (status);
CREATE INDEX idx_agent_sessions_agent_type ON agent_sessions (agent_type);
CREATE INDEX idx_agent_sessions_started_at ON agent_sessions (started_at DESC);
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Unique identifier |
| `user_id` | UUID | FK → users.id, NOT NULL, RESTRICT | Session initiator |
| `document_id` | UUID | FK → documents.id, NULL, SET NULL | Related document |
| `agent_type` | VARCHAR(100) | NOT NULL | Type of agent session |
| `status` | VARCHAR(50) | NOT NULL, DEFAULT 'running', CHECK | Session status |
| `input_data` | JSONB | NOT NULL, DEFAULT '{}' | Session input parameters |
| `output_data` | JSONB | NULL | Final output |
| `error_message` | TEXT | NULL | Error details if failed |
| `model` | VARCHAR(100) | NULL | LLM model used |
| `total_tokens` | INTEGER | NULL, CHECK >= 0 | Total tokens consumed |
| `total_cost_usd` | NUMERIC(10,6) | NULL, CHECK >= 0 | Total cost in USD |
| `started_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Session start time |
| `completed_at` | TIMESTAMPTZ | NULL | Session end time |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last modification |

**Example Record:**
```json
{
    "id": "sess-a2b3c4d5-e6f7-8901-abcd-ef1234567890",
    "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "document_id": "d1e2f3a4-b5c6-7890-1234-567890abcdef",
    "agent_type": "document_analysis",
    "status": "completed",
    "input_data": {"task": "full_analysis", "schema_id": "s1a2b3c4-d5e6-7890"},
    "output_data": {"fields_extracted": 8, "risks_found": 1, "confidence_avg": 0.93},
    "error_message": null,
    "model": "gpt-4o",
    "total_tokens": 4520,
    "total_cost_usd": 0.013560,
    "started_at": "2026-06-11T07:00:30Z",
    "completed_at": "2026-06-11T07:05:00Z",
    "created_at": "2026-06-11T07:00:30Z",
    "updated_at": "2026-06-11T07:05:00Z"
}
```

---

### 11. `agent_steps`

**Purpose:** Individual reasoning and action steps within an agent session for full traceability.

```sql
CREATE TABLE agent_steps (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL,
    step_index      INTEGER NOT NULL,
    step_type       VARCHAR(50) NOT NULL,
    action          VARCHAR(255) NULL,
    input_data      JSONB NULL,
    output_data     JSONB NULL,
    reasoning       TEXT NULL,
    model           VARCHAR(100) NULL,
    tokens_used     INTEGER NULL,
    duration_ms     INTEGER NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'completed',
    error_message   TEXT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_agent_steps_session_id FOREIGN KEY (session_id) REFERENCES agent_sessions(id) ON DELETE CASCADE,
    CONSTRAINT uq_agent_steps_session_step UNIQUE (session_id, step_index),
    CONSTRAINT ck_agent_steps_step_index_positive CHECK (step_index >= 0),
    CONSTRAINT ck_agent_steps_step_type_valid CHECK (step_type IN ('reasoning', 'tool_call', 'observation', 'planning', 'decision', 'error')),
    CONSTRAINT ck_agent_steps_status_valid CHECK (status IN ('completed', 'failed', 'skipped')),
    CONSTRAINT ck_agent_steps_duration_positive CHECK (duration_ms IS NULL OR duration_ms >= 0),
    CONSTRAINT ck_agent_steps_tokens_positive CHECK (tokens_used IS NULL OR tokens_used >= 0)
);

CREATE INDEX idx_agent_steps_session_id ON agent_steps (session_id);
CREATE INDEX idx_agent_steps_session_step ON agent_steps (session_id, step_index);
CREATE INDEX idx_agent_steps_type ON agent_steps (step_type);
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Unique identifier |
| `session_id` | UUID | FK → agent_sessions.id, NOT NULL, CASCADE | Parent session |
| `step_index` | INTEGER | NOT NULL, CHECK >= 0, UNIQUE with session_id | Step ordering |
| `step_type` | VARCHAR(50) | NOT NULL, CHECK | Step category |
| `action` | VARCHAR(255) | NULL | Action taken |
| `input_data` | JSONB | NULL | Step input |
| `output_data` | JSONB | NULL | Step output |
| `reasoning` | TEXT | NULL | LLM reasoning text |
| `model` | VARCHAR(100) | NULL | Model used |
| `tokens_used` | INTEGER | NULL, CHECK >= 0 | Tokens for this step |
| `duration_ms` | INTEGER | NULL, CHECK >= 0 | Step duration |
| `status` | VARCHAR(50) | NOT NULL, DEFAULT 'completed', CHECK | Step status |
| `error_message` | TEXT | NULL | Error details |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last modification |

**Example Record:**
```json
{
    "id": "step1a2b3c4-d5e6-7890-abcd-ef123456789",
    "session_id": "sess-a2b3c4d5-e6f7-8901-abcd-ef1234567890",
    "step_index": 0,
    "step_type": "reasoning",
    "action": "analyze_document_structure",
    "input_data": {"document_id": "d1e2f3a4-b5c6-7890-1234-567890abcdef"},
    "output_data": {"pages": 3, "detected_type": "invoice"},
    "reasoning": "The document appears to be an invoice based on header keywords and layout.",
    "model": "gpt-4o",
    "tokens_used": 320,
    "duration_ms": 1250,
    "status": "completed",
    "error_message": null,
    "created_at": "2026-06-11T07:00:31Z",
    "updated_at": "2026-06-11T07:00:33Z"
}
```

---

### 12. `tool_calls`

**Purpose:** Detailed log of every tool invocation by agent steps for debugging and auditing.

```sql
CREATE TABLE tool_calls (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_step_id   UUID NOT NULL,
    session_id      UUID NOT NULL,
    tool_name       VARCHAR(255) NOT NULL,
    tool_input      JSONB NOT NULL DEFAULT '{}',
    tool_output     JSONB NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'success',
    error_message   TEXT NULL,
    duration_ms     INTEGER NULL,
    retry_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_tool_calls_agent_step_id FOREIGN KEY (agent_step_id) REFERENCES agent_steps(id) ON DELETE CASCADE,
    CONSTRAINT fk_tool_calls_session_id FOREIGN KEY (session_id) REFERENCES agent_sessions(id) ON DELETE CASCADE,
    CONSTRAINT ck_tool_calls_status_valid CHECK (status IN ('success', 'failed', 'timeout', 'skipped')),
    CONSTRAINT ck_tool_calls_duration_positive CHECK (duration_ms IS NULL OR duration_ms >= 0),
    CONSTRAINT ck_tool_calls_retry_count_positive CHECK (retry_count >= 0)
);

CREATE INDEX idx_tool_calls_agent_step_id ON tool_calls (agent_step_id);
CREATE INDEX idx_tool_calls_session_id ON tool_calls (session_id);
CREATE INDEX idx_tool_calls_tool_name ON tool_calls (tool_name);
CREATE INDEX idx_tool_calls_session_tool ON tool_calls (session_id, tool_name);
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Unique identifier |
| `agent_step_id` | UUID | FK → agent_steps.id, NOT NULL, CASCADE | Parent step |
| `session_id` | UUID | FK → agent_sessions.id, NOT NULL, CASCADE | Parent session |
| `tool_name` | VARCHAR(255) | NOT NULL | Tool identifier |
| `tool_input` | JSONB | NOT NULL, DEFAULT '{}' | Tool input parameters |
| `tool_output` | JSONB | NULL | Tool output |
| `status` | VARCHAR(50) | NOT NULL, DEFAULT 'success', CHECK | Execution status |
| `error_message` | TEXT | NULL | Error details |
| `duration_ms` | INTEGER | NULL, CHECK >= 0 | Execution time |
| `retry_count` | INTEGER | NOT NULL, DEFAULT 0, CHECK >= 0 | Number of retries |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last modification |

**Example Record:**
```json
{
    "id": "tc1a2b3c4-d5e6-7890-abcd-ef123456789",
    "agent_step_id": "step1a2b3c4-d5e6-7890-abcd-ef123456789",
    "session_id": "sess-a2b3c4d5-e6f7-8901-abcd-ef1234567890",
    "tool_name": "ocr_extract",
    "tool_input": {"page_number": 1, "language": "en"},
    "tool_output": {"text": "INVOICE #12345...", "confidence": 0.94},
    "status": "success",
    "error_message": null,
    "duration_ms": 3200,
    "retry_count": 0,
    "created_at": "2026-06-11T07:00:35Z",
    "updated_at": "2026-06-11T07:00:38Z"
}
```

---

### 13. `eval_datasets`

**Purpose:** Evaluation dataset definitions for benchmarking and testing agent performance.

```sql
CREATE TABLE eval_datasets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    description     TEXT NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    task_type       VARCHAR(100) NOT NULL,
    record_count    INTEGER NOT NULL DEFAULT 0,
    storage_path    VARCHAR(1000) NULL,
    schema_definition JSONB NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_by      UUID NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ NULL,

    CONSTRAINT fk_eval_datasets_created_by FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT uq_eval_datasets_name_version UNIQUE (name, version),
    CONSTRAINT ck_eval_datasets_version_positive CHECK (version > 0),
    CONSTRAINT ck_eval_datasets_record_count_non_negative CHECK (record_count >= 0)
);

CREATE INDEX idx_eval_datasets_task_type ON eval_datasets (task_type) WHERE deleted_at IS NULL;
CREATE INDEX idx_eval_datasets_active ON eval_datasets (is_active) WHERE deleted_at IS NULL AND is_active = TRUE;
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Unique identifier |
| `name` | VARCHAR(255) | NOT NULL, UNIQUE with version | Dataset name |
| `description` | TEXT | NULL | Description |
| `version` | INTEGER | NOT NULL, DEFAULT 1, CHECK > 0, UNIQUE with name | Dataset version |
| `task_type` | VARCHAR(100) | NOT NULL | Evaluation task type |
| `record_count` | INTEGER | NOT NULL, DEFAULT 0, CHECK >= 0 | Number of records |
| `storage_path` | VARCHAR(1000) | NULL | Dataset file path |
| `schema_definition` | JSONB | NULL | Expected schema |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | Active flag |
| `created_by` | UUID | FK → users.id, NULL, SET NULL | Creator |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last modification |
| `deleted_at` | TIMESTAMPTZ | NULL | Soft delete |

**Example Record:**
```json
{
    "id": "eval1a2b3c4-d5e6-7890-abcd-ef12345678",
    "name": "invoice_extraction_v1",
    "description": "50 labeled invoices for extraction accuracy benchmarking",
    "version": 1,
    "task_type": "field_extraction",
    "record_count": 50,
    "storage_path": "/data/eval/invoice_extraction_v1.jsonl",
    "schema_definition": {"fields": ["invoice_number", "total_amount", "date"]},
    "is_active": true,
    "created_by": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "created_at": "2026-04-01T10:00:00Z",
    "updated_at": "2026-04-01T10:00:00Z",
    "deleted_at": null
}
```

---

### 14. `eval_runs`

**Purpose:** Results of evaluation runs against datasets, tracking agent performance metrics over time.

```sql
CREATE TABLE eval_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id      UUID NOT NULL,
    session_id      UUID NULL,
    run_name        VARCHAR(255) NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'running',
    metrics         JSONB NULL,
    config          JSONB NOT NULL DEFAULT '{}',
    error_count     INTEGER NOT NULL DEFAULT 0,
    total_records   INTEGER NOT NULL DEFAULT 0,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_eval_runs_dataset_id FOREIGN KEY (dataset_id) REFERENCES eval_datasets(id) ON DELETE CASCADE,
    CONSTRAINT ck_eval_runs_status_valid CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    CONSTRAINT ck_eval_runs_error_count_non_negative CHECK (error_count >= 0),
    CONSTRAINT ck_eval_runs_total_records_non_negative CHECK (total_records >= 0)
);

CREATE INDEX idx_eval_runs_dataset_id ON eval_runs (dataset_id);
CREATE INDEX idx_eval_runs_status ON eval_runs (status);
CREATE INDEX idx_eval_runs_started_at ON eval_runs (started_at DESC);
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Unique identifier |
| `dataset_id` | UUID | FK → eval_datasets.id, NOT NULL, CASCADE | Dataset used |
| `session_id` | UUID | NULL | Agent session for the run |
| `run_name` | VARCHAR(255) | NULL | Human-readable name |
| `status` | VARCHAR(50) | NOT NULL, DEFAULT 'running', CHECK | Run status |
| `metrics` | JSONB | NULL | Computed metrics (precision, recall, F1, etc.) |
| `config` | JSONB | NOT NULL, DEFAULT '{}' | Run configuration |
| `error_count` | INTEGER | NOT NULL, DEFAULT 0, CHECK >= 0 | Number of errors |
| `total_records` | INTEGER | NOT NULL, DEFAULT 0, CHECK >= 0 | Records processed |
| `started_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Run start time |
| `completed_at` | TIMESTAMPTZ | NULL | Run end time |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last modification |

**Example Record:**
```json
{
    "id": "erun1a2b3c4-d5e6-7890-abcd-ef12345678",
    "dataset_id": "eval1a2b3c4-d5e6-7890-abcd-ef12345678",
    "session_id": "sess-a2b3c4d5-e6f7-8901-abcd-ef1234567890",
    "run_name": "baseline-v3-invoice-extraction",
    "status": "completed",
    "metrics": {"precision": 0.92, "recall": 0.89, "f1": 0.905, "exact_match": 0.84},
    "config": {"model": "gpt-4o", "temperature": 0.0, "max_tokens": 2000},
    "error_count": 2,
    "total_records": 50,
    "started_at": "2026-06-10T14:00:00Z",
    "completed_at": "2026-06-10T14:15:30Z",
    "created_at": "2026-06-10T14:00:00Z",
    "updated_at": "2026-06-10T14:15:30Z"
}
```

---

### 15. `audit_logs`

**Purpose:** Immutable audit trail for all significant operations across the system for compliance and debugging.

```sql
CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NULL,
    session_id      UUID NULL,
    action          VARCHAR(100) NOT NULL,
    entity_type     VARCHAR(100) NOT NULL,
    entity_id       UUID NULL,
    old_values      JSONB NULL,
    new_values      JSONB NULL,
    ip_address      INET NULL,
    user_agent      VARCHAR(500) NULL,
    request_id      UUID NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_audit_logs_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT ck_audit_logs_action_valid CHECK (action IN (
        'create', 'read', 'update', 'delete',
        'login', 'logout', 'login_failed',
        'upload', 'download', 'process',
        'export', 'import', 'approve', 'reject',
        'execute', 'configure'
    ))
);

CREATE INDEX idx_audit_logs_user_id ON audit_logs (user_id);
CREATE INDEX idx_audit_logs_entity ON audit_logs (entity_type, entity_id);
CREATE INDEX idx_audit_logs_action ON audit_logs (action);
CREATE INDEX idx_audit_logs_created_at ON audit_logs (created_at DESC);
CREATE INDEX idx_audit_logs_session_id ON audit_logs (session_id) WHERE session_id IS NOT NULL;
CREATE INDEX idx_audit_logs_request_id ON audit_logs (request_id) WHERE request_id IS NOT NULL;
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Unique identifier |
| `user_id` | UUID | FK → users.id, NULL, SET NULL | Acting user |
| `session_id` | UUID | NULL | Related agent session |
| `action` | VARCHAR(100) | NOT NULL, CHECK | Action performed |
| `entity_type` | VARCHAR(100) | NOT NULL | Entity type affected |
| `entity_id` | UUID | NULL | Entity ID affected |
| `old_values` | JSONB | NULL | Previous state (for updates) |
| `new_values` | JSONB | NULL | New state (for creates/updates) |
| `ip_address` | INET | NULL | Client IP address |
| `user_agent` | VARCHAR(500) | NULL | Client user agent |
| `request_id` | UUID | NULL | Request correlation ID |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Event timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record modification |

**Note:** `audit_logs` is append-only. No soft delete. `updated_at` exists only for schema consistency.

**Example Record:**
```json
{
    "id": "log1a2b3c4-d5e6-7890-abcd-ef12345678",
    "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "session_id": null,
    "action": "upload",
    "entity_type": "document",
    "entity_id": "d1e2f3a4-b5c6-7890-1234-567890abcdef",
    "old_values": null,
    "new_values": {"filename": "invoice_2026_06.pdf", "status": "uploaded"},
    "ip_address": "192.168.1.100",
    "user_agent": "Mozilla/5.0 ...",
    "request_id": "req-a2b3c4d5-e6f7-8901-abcd-ef1234567890",
    "created_at": "2026-06-11T07:00:00Z",
    "updated_at": "2026-06-11T07:00:00Z"
}
```

---

## Index Strategy

### Principles

1. **Partial indexes** on soft-deleted tables: `WHERE deleted_at IS NULL` excludes deleted rows from index size.
2. **Composite indexes** follow query patterns: most selective column first.
3. **Covering indexes** are not used (PostgreSQL supports them via `INCLUDE` but adds maintenance cost).
4. **Expression indexes** on `LOWER(email)` for case-insensitive lookups if needed.
5. **GIN indexes** on JSONB columns only when JSONB queries are frequent.

### Recommended Additional Indexes

```sql
-- Full-text search on document pages
CREATE INDEX idx_document_pages_ocr_text_gin ON document_pages USING gin(to_tsvector('english', ocr_text));

-- JSONB containment queries on document metadata
CREATE INDEX idx_documents_metadata_gin ON documents USING gin(metadata jsonb_path_ops);

-- JSONB containment on extracted fields
CREATE INDEX idx_extracted_fields_value_gin ON extracted_fields USING gin(field_value jsonb_path_ops);
```

### Index Monitoring

```sql
-- Find unused indexes
SELECT schemaname, relname, indexrelname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE idx_scan = 0 AND indexrelname NOT LIKE 'uq_%'
ORDER BY pg_relation_size(indexrelid) DESC;

-- Find missing indexes (high sequential scan tables)
SELECT relname, seq_scan, seq_tup_read, idx_scan, idx_tup_fetch
FROM pg_stat_user_tables
WHERE seq_scan > 100 AND seq_tup_read > 10000
ORDER BY seq_tup_read DESC;
```

---

## Partitioning Strategy

### `audit_logs` — Range Partitioning by `created_at`

The `audit_logs` table grows indefinitely and is the primary candidate for partitioning.

```sql
-- Create partitioned table
CREATE TABLE audit_logs (
    -- ... same columns as above ...
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE audit_logs_2026_01 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE audit_logs_2026_02 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
-- ... continue for each month ...

-- Auto-create future partitions (pg_partman or cron)
```

### `tool_calls` — Range Partitioning by `created_at`

```sql
CREATE TABLE tool_calls (
    -- ... same columns as above ...
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);
```

### `agent_steps` — Range Partitioning by `created_at`

```sql
CREATE TABLE agent_steps (
    -- ... same columns as above ...
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);
```

### Partition Management Script

```sql
-- Auto-generate partitions for the next 3 months
DO $$
DECLARE
    month_start DATE;
    month_end DATE;
    partition_name TEXT;
BEGIN
    FOR i IN 0..2 LOOP
        month_start := date_trunc('month', CURRENT_DATE + (interval '1 month' * i));
        month_end := month_start + interval '1 month';
        partition_name := 'audit_logs_' || to_char(month_start, 'YYYY_MM');

        IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = partition_name) THEN
            EXECUTE format(
                'CREATE TABLE %I PARTITION OF audit_logs FOR VALUES FROM (%L) TO (%L)',
                partition_name, month_start, month_end
            );
        END IF;
    END LOOP;
END $$;
```

---

## SQLAlchemy Models

### Base Mixin

```python
import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None, index=True
    )
```

### User Model

```python
from sqlalchemy import String, Boolean, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB, INET


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    preferences: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'operator', 'analyst', 'viewer')", name="ck_users_role_valid"),
        Index("idx_users_email", "email", postgresql_where="deleted_at IS NULL"),
        Index("idx_users_role_active", "role", "is_active", postgresql_where="deleted_at IS NULL"),
    )
```

### Document Model

```python
from sqlalchemy import String, Integer, BigInteger, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import relationship


class Document(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(50), nullable=False, default="local")
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="uploaded")
    document_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    classification: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="documents")
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded','queued','processing','ocr_complete','extraction_complete','reviewed','completed','failed','archived')",
            name="ck_documents_status_valid",
        ),
        CheckConstraint("file_size_bytes > 0", name="ck_documents_file_size_positive"),
        Index("idx_documents_user_id_status", "user_id", "status", postgresql_where="deleted_at IS NULL"),
    )
```

### AgentSession Model

```python
from sqlalchemy import Numeric


class AgentSession(Base, TimestampMixin):
    __tablename__ = "agent_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True)
    agent_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    input_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    steps = relationship("AgentStep", back_populates="session", cascade="all, delete-orphan")
    tool_calls = relationship("ToolCall", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "status IN ('running','completed','failed','cancelled','timeout')",
            name="ck_agent_sessions_status_valid",
        ),
    )
```

### AuditLog Model

```python
class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    old_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        Index("idx_audit_logs_entity", "entity_type", "entity_id"),
        Index("idx_audit_logs_created_at", "created_at", postgresql_using="btree"),
    )
```

---

## Alembic Migration Strategy

### Directory Structure

```
alembic/
├── alembic.ini
├── env.py
├── script.py.mako
└── versions/
    ├── 001_initial_schema.py
    ├── 002_add_document_chunks.py
    └── ...
```

### `alembic.ini` Configuration

```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://user:pass@localhost:5432/docops
file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d_%%(rev)s_%%(slug)s

[loggers]
keys = root,sqlalchemy,alembic

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine
```

### `env.py` (Async Support)

```python
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from app.models.base import Base
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### Example Migration: Initial Schema

```python
"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-01-15 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

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
    # ... remaining tables ...


def downgrade() -> None:
    op.drop_table("audit_logs")
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
```

---

## Connection Pooling

### SQLAlchemy Configuration

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

engine = create_async_engine(
    "postgresql+asyncpg://user:password@localhost:5432/docops",
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
    echo=False,
    connect_args={
        "server_settings": {
            "application_name": "docops_agent",
            "jit": "off",
        },
        "command_timeout": 60,
    },
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
```

### PgBouncer Configuration (`pgbouncer.ini`)

```ini
[databases]
docops = host=127.0.0.1 port=5432 dbname=docops

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt

pool_mode = transaction
default_pool_size = 50
max_client_conn = 500
max_db_connections = 100
server_idle_timeout = 300
server_lifetime = 3600
server_connect_timeout = 15
query_timeout = 120
query_wait_timeout = 30
```

### Environment Variables

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/docops
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=1800
DATABASE_ECHO=false
```

---

## Migration Rules

1. **Never modify released migrations.** Create a new migration to fix issues.
2. **Always provide `downgrade()`** — every migration must be reversible.
3. **Use `op.batch_alter_table()`** for SQLite compatibility in tests.
4. **Never drop columns in production** without a deprecation period:
   - Step 1: Stop writing to column (deploy code change)
   - Step 2: Stop reading from column (deploy code change)
   - Step 3: Drop column (migration)
5. **Add columns as NULLABLE first**, backfill, then add NOT NULL constraint.
6. **Index creation must use `op.create_index(..., postgresql_concurrently=True)`** for zero-downtime on large tables. Run outside a transaction.
7. **Test migrations against a copy of production data** before deploying.
8. **Tag migrations** that require manual intervention: `# MANUAL: requires backfill`
9. **Foreign key constraints** should be added with `NOT VALID` then validated separately:
   ```python
   op.create_foreign_key("fk_new", "table", "ref", ["col"], ["id"], postgresql_not_valid=True)
   op.execute("ALTER TABLE table VALIDATE CONSTRAINT fk_new")
   ```
10. **Partition management** is handled outside Alembic via scheduled jobs (pg_partman or cron).

---

## Quick Reference: Table Sizes & Retention

| Table | Expected Growth | Retention Policy |
|---|---|---|
| `users` | Low (~100s) | Soft delete, keep indefinitely |
| `documents` | Medium (~10K/mo) | Soft delete, archive after 2 years |
| `document_pages` | High (~30K/mo) | Cascade with documents |
| `document_chunks` | High (~100K/mo) | Cascade with documents |
| `extraction_schemas` | Low (~50) | Soft delete, version indefinitely |
| `extracted_fields` | Medium (~80K/mo) | Cascade with documents |
| `risk_items` | Medium (~5K/mo) | Soft delete after resolution + 1 year |
| `tasks` | Low (~2K/mo) | Soft delete after completion + 6 months |
| `reports` | Medium (~5K/mo) | Delete after expiry |
| `agent_sessions` | High (~10K/mo) | Partition, archive after 1 year |
| `agent_steps` | Very High (~100K/mo) | Partition, archive after 6 months |
| `tool_calls` | Very High (~200K/mo) | Partition, archive after 3 months |
| `eval_datasets` | Low (~20) | Soft delete, keep indefinitely |
| `eval_runs` | Low (~500/mo) | Keep indefinitely |
| `audit_logs` | Very High (~500K/mo) | Partition, retain 7 years (compliance) |
