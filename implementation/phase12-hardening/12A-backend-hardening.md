# Phase 12A: Backend Hardening — Implementation Plan

## Task
Implement auth, rate limiting, caching, search endpoint, and security hardening.

## Current Gaps
- No JWT authentication
- No rate limiting
- No Redis caching layer
- No search API endpoint
- No CORS security hardening

## Files to Create

### 1. Authentication (`backend/app/auth/`)

#### `backend/app/auth/__init__.py`
#### `backend/app/auth/jwt.py`
- create_access_token(user_id, role, expires_delta) -> str
- create_refresh_token(user_id) -> str
- decode_token(token) -> TokenPayload
- TokenPayload: user_id, role, exp, iat, jti

#### `backend/app/auth/password.py`
- hash_password(plain: str) -> str — bcrypt
- verify_password(plain: str, hashed: str) -> bool

#### `backend/app/auth/dependencies.py`
- get_current_user(token, db) -> User — FastAPI dependency
- require_role(*roles) -> dependency — role checker

#### `backend/app/api/v1/auth.py`
- POST /auth/register — create user
- POST /auth/login — login, return tokens
- POST /auth/refresh — refresh access token
- GET /auth/me — current user info

### 2. Rate Limiting (`backend/app/api/middleware/rate_limit.py`)
- RateLimitMiddleware class
- Redis-backed sliding window
- Configurable per endpoint: 100 req/min default
- Returns 429 with Retry-After header

### 3. Redis Caching (`backend/app/cache/query_cache.py`)
- QueryCache class
- cache_search_result(query_hash, results, ttl=300)
- get_cached_search(query_hash) -> list | None
- cache_document_fields(document_id, fields, ttl=600)
- invalidate_document(document_id)

### 4. Search API (`backend/app/api/v1/search.py`)
- POST /search — hybrid search across documents
- Request: query, filters (document_ids, date_range, document_type), top_k
- Response: results with chunks, scores, citations

### 5. Security Hardening
- Update CORS config for production
- Add security headers middleware
- Add request size limit middleware

## Acceptance Criteria
- [ ] JWT auth works for all protected endpoints
- [ ] Rate limiting returns 429 when exceeded
- [ ] Cached search results returned within 50ms
- [ ] Search endpoint returns ranked results
- [ ] Security headers present

## Test Requirements
- tests/auth/test_jwt.py
- tests/auth/test_password.py
- tests/api/test_auth.py
- tests/middleware/test_rate_limit.py
- tests/cache/test_query_cache.py
- tests/api/test_search.py
