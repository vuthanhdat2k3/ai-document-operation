# Phase 1C: Infrastructure Clients — Implementation Plan

## Task
Configure Redis, Qdrant, and MinIO clients with health checks and connection management.

## Dependencies
Phase 1A (config must exist)

## Files to Create

### 1. `backend/app/cache/__init__.py`
- Empty init

### 2. `backend/app/cache/redis.py`
- RedisCache class wrapping redis.asyncio
- Methods: get, set, delete, exists, expire, health_check
- Connection pool configuration
- Key prefix support
- JSON serialization

### 3. `backend/app/vector/__init__.py`
- Empty init

### 4. `backend/app/vector/client.py`
- QdrantClientWrapper class
- Methods: health_check, create_collection, delete_collection, list_collections
- Collection configuration for dense + sparse vectors
- Connection management

### 5. `backend/app/vector/collections.py`
- create_document_collection() — creates collection with dense (1024-dim) + sparse vectors
- Collection payload schema: document_id, page, chunk_index, text, metadata

### 6. `backend/app/storage/__init__.py`
- Empty init

### 7. `backend/app/storage/minio.py`
- MinioStorage class wrapping minio client
- Methods: upload_file, download_file, delete_file, get_presigned_url, health_check, ensure_bucket
- Bucket creation on startup

### 8. `backend/app/storage/local.py`
- LocalFileSystem storage (fallback for development)
- Same interface as MinioStorage

## Acceptance Criteria
- [ ] Redis client connects and responds to ping
- [ ] Qdrant client connects and can create/list collections
- [ ] MinIO client connects and can create buckets
- [ ] All health checks return True when services are running
- [ ] Graceful error handling when services are unavailable

## Test Requirements
- `tests/cache/test_redis.py` — Redis CRUD and health check
- `tests/vector/test_client.py` — Qdrant connection and collection management
- `tests/storage/test_minio.py` — MinIO upload/download and health check
