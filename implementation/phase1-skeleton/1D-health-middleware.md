# Phase 1D: Health + Middleware — Implementation Plan

## Task
Implement health/ready endpoints, request ID middleware, structured logging, CORS, and error handlers.

## Dependencies
Phase 1A, 1B, 1C

## Files to Create/Update

### 1. `backend/app/api/v1/admin.py`
- GET /health — returns {"status": "ok", "version": "1.0.0", "timestamp": "..."}
- GET /ready — checks all dependencies:
  - PostgreSQL: SELECT 1
  - Redis: PING
  - Qdrant: GET /healthz
  - MinIO: bucket list
  - Returns {"status": "ready"|"degraded", "services": {"postgres": "ok", "redis": "ok", ...}}

### 2. `backend/app/api/middleware/request_id.py`
- ASIOMiddleware
- Extract X-Request-ID from header or generate UUID4
- Store in request.state.request_id
- Add to response headers
- Propagate to structlog context

### 3. `backend/app/api/middleware/logging.py`
- Structured logging middleware
- Log: method, path, status_code, duration_ms, request_id
- Use structlog with JSON renderer

### 4. `backend/app/api/middleware/error_handler.py`
- AppError base exception
- NotFoundError (404)
- ValidationError (422)
- RateLimitError (429)
- UnauthorizedError (401)
- ForbiddenError (403)
- Global exception handler returning ErrorResponse

### 5. `backend/app/logging.py`
- structlog configuration
- JSON renderer for production
- Console renderer for development
- Context processors: request_id, user_id

### 6. Update `backend/app/main.py`
- Register all middleware in correct order
- Register exception handlers
- CORS configuration from settings

## Middleware Order (outermost first)
1. CORS
2. Request ID
3. Logging
4. Rate Limiting (placeholder)

## Acceptance Criteria
- [ ] GET /health returns 200 with version info
- [ ] GET /ready returns service status for all dependencies
- [ ] Every response has X-Request-ID header
- [ ] Structured JSON logs include request_id
- [ ] Error responses follow ErrorResponse schema
- [ ] CORS headers present on cross-origin requests

## Test Requirements
- `tests/api/test_health.py` — health and ready endpoint tests
- `tests/middleware/test_request_id.py` — request ID propagation
- `tests/middleware/test_error_handler.py` — error response format
- `tests/test_logging.py` — structured log output
