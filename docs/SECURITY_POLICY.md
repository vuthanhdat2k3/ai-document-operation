# Security Policy — AI Document Operations Agent

## 1. Security Overview and Principles

This document defines the security architecture, policies, and procedures for the AI Document Operations Agent platform. All development, deployment, and operational activities must adhere to these policies.

### Core Principles

| Principle | Description |
|-----------|-------------|
| **Least Privilege** | Every user, service, and component receives only the minimum permissions required |
| **Defense in Depth** | Multiple overlapping security controls at application, network, and data layers |
| **Zero Trust** | No implicit trust between services; all requests are authenticated and authorized |
| **Secure by Default** | Default configurations are restrictive; features require explicit enablement |
| **Auditability** | All security-relevant events are logged with tamper-evident mechanisms |
| **Data Minimization** | Collect and retain only data necessary for the stated purpose |

### Scope

This policy applies to:
- All application code (backend API, frontend, LLM pipelines)
- All infrastructure (Docker containers, databases, object storage, caches)
- All third-party integrations (LLM providers, Notion API, MinIO)
- All personnel with access to production systems

---

## 2. Authentication

### 2.1 JWT Token-Based Authentication

All API endpoints (except `/auth/login` and `/auth/register`) require a valid JWT Bearer token in the `Authorization` header.

```
Authorization: Bearer <access_token>
```

### 2.2 Token Generation and Validation

**Token Generation** (`POST /auth/login`):
- User submits email + password
- Server validates credentials against bcrypt hash in PostgreSQL
- On success, server issues an access token and a refresh token
- Tokens are signed with `HS256` using `JWT_SECRET_KEY` from environment variables

**Token Payload**:
```json
{
  "sub": "<user_uuid>",
  "email": "<user_email>",
  "role": "<admin|analyst|viewer>",
  "type": "access",
  "iat": 1718100000,
  "exp": 1718100900
}
```

**Token Validation Middleware**:
- Verify signature against `JWT_SECRET_KEY`
- Check `exp` claim (reject expired tokens)
- Check `type` claim (access tokens only for API calls)
- Load user from DB and verify account is active
- Attach user context to request state

### 2.3 Token Refresh Mechanism

**Endpoint**: `POST /auth/refresh`

- Client sends refresh token
- Server validates refresh token signature and expiration
- Server checks refresh token is not in the revocation list (Redis blacklist)
- Server issues new access token + new refresh token (rotation)
- Old refresh token is added to Redis blacklist

### 2.4 Token Expiration

| Token Type | Lifetime | Storage |
|------------|----------|---------|
| Access Token | 15 minutes | Client memory (not localStorage) |
| Refresh Token | 7 days | HttpOnly secure cookie or encrypted storage |

### 2.5 Password Hashing

- Algorithm: `bcrypt` with cost factor 12
- Passwords are hashed before storage; plaintext passwords are never persisted
- Minimum password requirements: 8 characters, 1 uppercase, 1 lowercase, 1 digit, 1 special character
- Password history: last 5 passwords cannot be reused

### 2.6 Multi-Factor Authentication (MFA) — Placeholder

MFA support is planned for Phase 2:
- TOTP-based (Google Authenticator, Authy)
- SMS fallback (optional)
- Recovery codes (10 single-use codes)
- MFA will be mandatory for `admin` role

---

## 3. Authorization

### 3.1 Role-Based Access Control (RBAC)

Authorization is enforced at the middleware layer. Each request is checked against the user's role and the required permission for the target resource and action.

### 3.2 Roles

| Role | Description |
|------|-------------|
| `admin` | Full system access including user management, system configuration, and all document operations |
| `analyst` | Can upload, process, query documents, and view analytics. Cannot manage users or system settings |
| `viewer` | Read-only access to documents and dashboards. Cannot upload or modify data |

### 3.3 Permission Matrix

| Resource / Action | admin | analyst | viewer |
|-------------------|-------|---------|--------|
| **Users** — Create | ✅ | ❌ | ❌ |
| **Users** — Read list | ✅ | ❌ | ❌ |
| **Users** — Update role | ✅ | ❌ | ❌ |
| **Users** — Deactivate | ✅ | ❌ | ❌ |
| **Documents** — Upload | ✅ | ✅ | ❌ |
| **Documents** — Read/List | ✅ | ✅ | ✅ |
| **Documents** — Delete | ✅ | ✅ | ❌ |
| **Documents** — Download | ✅ | ✅ | ✅ |
| **Documents** — Process (OCR/LLM) | ✅ | ✅ | ❌ |
| **Queries** — Execute | ✅ | ✅ | ✅ |
| **Queries** — View history | ✅ | ✅ | ✅ (own) |
| **Analytics** — View dashboards | ✅ | ✅ | ✅ |
| **Analytics** — Export data | ✅ | ✅ | ❌ |
| **System** — View config | ✅ | ❌ | ❌ |
| **System** — Modify config | ✅ | ❌ | ❌ |
| **Audit Logs** — View | ✅ | ❌ | ❌ |
| **LLM Budgets** — Configure | ✅ | ❌ | ❌ |
| **Integrations** — Manage | ✅ | ❌ | ❌ |

### 3.4 Resource-Level Permissions

Beyond role-based access, document-level permissions are enforced:
- Documents have an `owner` field (the user who uploaded)
- Documents can have shared access via `document_permissions` table
- `admin` users can access all documents
- `analyst` users can access their own documents and shared documents
- `viewer` users can access only documents explicitly shared with them

---

## 4. API Security

### 4.1 Rate Limiting

| Scope | Limit | Window |
|-------|-------|--------|
| Per user (all endpoints) | 100 requests | 1 minute |
| Per user (auth endpoints) | 10 requests | 1 minute |
| Per user (LLM endpoints) | 20 requests | 1 minute |
| Per IP (unauthenticated) | 30 requests | 1 minute |

Rate limiting is implemented via Redis sliding window counters. Exceeding limits returns `429 Too Many Requests` with `Retry-After` header.

### 4.2 Request Size Limits

| Endpoint Type | Max Body Size |
|---------------|---------------|
| JSON API endpoints | 1 MB |
| File upload endpoints | 50 MB |
| All other endpoints | 512 KB |

### 4.3 CORS Configuration

```python
ALLOWED_ORIGINS = [
    "http://localhost:3000",       # Development frontend
    "https://app.example.com",     # Production frontend
]

CORS_CONFIG = {
    "allow_origins": ALLOWED_ORIGINS,
    "allow_methods": ["GET", "POST", "PUT", "DELETE", "PATCH"],
    "allow_headers": ["Authorization", "Content-Type", "X-Request-ID"],
    "allow_credentials": True,
    "max_age": 600,
}
```

No wildcard (`*`) origins are permitted in production.

### 4.4 Security Headers

All API responses include the following headers:

| Header | Value |
|--------|-------|
| `Content-Security-Policy` | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'` |
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains; preload` |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `X-XSS-Protection` | `0` (rely on CSP instead) |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` |
| `Cache-Control` | `no-store` (for authenticated endpoints) |

### 4.5 Input Sanitization

- All user input is validated using Pydantic models with strict type checking
- String inputs are stripped of leading/trailing whitespace
- HTML content is sanitized using `bleach` library (allowlisted tags only)
- File paths are validated to prevent path traversal (`../` sequences rejected)
- Query parameters are URL-decoded once and validated

### 4.6 SQL Injection Prevention

- All database access uses SQLAlchemy ORM with parameterized queries
- Raw SQL is prohibited in application code (enforced via linting rules)
- Database user for the application has restricted permissions (no DDL)
- Connection strings are loaded from environment variables only

### 4.7 XSS Prevention

- All API responses use `Content-Type: application/json` (not `text/html`)
- User-generated content is escaped before rendering in any HTML context
- Content-Security-Policy headers prevent inline script execution
- Frontend frameworks (React/Vue) provide automatic output escaping

---

## 5. Data Protection

### 5.1 Encryption at Rest

| Component | Encryption Method |
|-----------|-------------------|
| PostgreSQL | Transparent Data Encryption (TDE) or disk-level LUKS encryption |
| MinIO (object storage) | Server-Side Encryption (SSE-S3) with AES-256 |
| Redis | No persistent encryption (ephemeral data only; sensitive data encrypted at application level) |
| Qdrant | Volume-level encryption |

### 5.2 Encryption in Transit

- All external communication uses TLS 1.3 (TLS 1.2 minimum)
- Internal Docker network traffic uses mTLS where feasible
- Certificate management via Let's Encrypt (production) or self-signed (development)
- HSTS header enforces HTTPS in browsers

### 5.3 PII Detection and Masking

**Detection**:
- Automated PII scanning on document upload using regex patterns and NER models
- Detected PII types: email, phone number, national ID, bank account, name, address
- PII metadata is stored alongside documents (not the raw PII values)

**Masking**:
- PII in logs is automatically redacted (e.g., `***@***.com`)
- PII in API responses for non-owner users is masked
- Export functionality applies masking rules based on requesting user's role

### 5.4 Data Retention Policies

| Data Type | Retention Period | Action After Expiry |
|-----------|------------------|---------------------|
| User accounts | Active + 30 days after deletion request | Anonymize |
| Documents | 2 years from upload (configurable) | Archive to cold storage, then delete |
| Audit logs | 90 days | Archive to cold storage |
| Query history | 1 year | Delete |
| LLM conversation logs | 90 days | Delete |
| Session data (Redis) | 7 days (refresh token TTL) | Auto-expire |

### 5.5 Data Deletion Procedures

**User Data Deletion** (`DELETE /users/{id}`):
1. Anonymize user record (replace PII with hashed placeholders)
2. Revoke all active tokens (add to Redis blacklist)
3. Transfer document ownership to system account
4. Delete user's query history after 30-day grace period
5. Log deletion event in audit log

**Document Deletion** (`DELETE /documents/{id}`):
1. Verify requester has delete permission
2. Remove file from MinIO
3. Remove vector embeddings from Qdrant
4. Mark document as deleted in PostgreSQL (soft delete for 30 days)
5. Hard delete after 30 days

---

## 6. Secret Management

### 6.1 Environment Variables Only

All secrets are loaded from environment variables. No secrets are stored in source code, configuration files, or Docker images.

Required environment variables:
```
JWT_SECRET_KEY=<random-256-bit>
JWT_REFRESH_SECRET_KEY=<random-256-bit>
POSTGRES_PASSWORD=<strong-password>
REDIS_PASSWORD=<strong-password>
MINIO_ACCESS_KEY=<access-key>
MINIO_SECRET_KEY=<secret-key>
QDRANT_API_KEY=<api-key>
OPENAI_API_KEY=<api-key>
NOTION_API_KEY=<api-key>
```

### 6.2 No Secrets in Code or Config Files

- Pre-commit hooks scan for secret patterns (using `detect-secrets` or `gitleaks`)
- CI/CD pipeline includes secret scanning stage
- `.gitignore` includes `.env`, `.env.*`, `secrets/`, `*.pem`, `*.key`
- Docker images do not include `.env` files (use `docker-compose` env_file or Docker secrets)

### 6.3 Secret Rotation Strategy

| Secret | Rotation Frequency | Procedure |
|--------|-------------------|-----------|
| JWT_SECRET_KEY | 90 days | Generate new key, deploy with dual-key support (accept old + new for 24h), then remove old |
| Database password | 90 days | Update password in vault/env, restart services with rolling deployment |
| API keys (OpenAI, Notion) | On compromise or annually | Generate new key in provider dashboard, update env, restart services |
| MinIO credentials | 90 days | Rotate via MinIO admin, update env, restart services |

### 6.4 .env File Security

- `.env` files have `600` permissions (owner read/write only)
- `.env.example` contains placeholder values only (no real secrets)
- Production `.env` files are managed by deployment tooling, not committed to git
- `.env` files are listed in `.gitignore` and `.dockerignore`

### 6.5 Docker Secrets (Production)

In production (Docker Swarm or Kubernetes):
- Secrets are stored in Docker secrets or Kubernetes secrets
- Secrets are mounted as files in `/run/secrets/`
- Application reads secrets from files when available, falling back to environment variables
- Docker Compose `secrets` directive is used for local production testing

### 6.6 HashiCorp Vault Integration — Placeholder

Future integration with HashiCorp Vault for:
- Dynamic database credentials
- Automatic secret rotation
- Audit logging of secret access
- Transit encryption for sensitive fields

---

## 7. LLM Security

### 7.1 Prompt Injection Detection

All user inputs destined for LLM prompts are scanned for injection patterns:
- Role/persona override attempts ("Ignore previous instructions...")
- System prompt extraction attempts
- Encoding tricks (base64, ROT13, unicode homoglyphs)
- Nested instruction patterns

Detection is implemented via:
1. Pattern matching with known injection signatures
2. Input/output semantic similarity check (if output closely matches known injection patterns, flag it)
3. Canary tokens in system prompts

### 7.2 Input Sanitization Before LLM

- User input is wrapped in delimiters with escape characters
- System prompts use XML-like tags to separate instructions from user content
- Maximum input length for LLM queries: 4000 characters
- HTML, script tags, and special control characters are stripped

### 7.3 Output Filtering

LLM responses are filtered before returning to users:
- Remove any leaked system prompt content
- Remove PII that the LLM may have generated or exposed
- Filter harmful content categories (violence, illegal activity, etc.)
- Validate output format matches expected schema (for structured outputs)

### 7.4 Content Policy Enforcement

- LLM interactions are logged with input/output pairs (redacted for PII)
- Responses violating content policy are blocked and flagged
- Repeated policy violations trigger user account review
- Content moderation is applied at the output layer

### 7.5 Cost Budget Limits

| Scope | Budget | Period |
|-------|--------|--------|
| Per user | $10.00 | Monthly |
| Per organization | $500.00 | Monthly |
| System-wide | $2000.00 | Monthly |

When budget is reached:
- LLM requests return `429 Budget Exceeded` error
- Admin is notified via configured alerting channel
- Budget resets at the start of each calendar month

### 7.6 Rate Limiting for LLM Calls

| User Role | Max LLM Calls | Window |
|-----------|---------------|--------|
| admin | 50 | 1 minute |
| analyst | 20 | 1 minute |
| viewer | 5 | 1 minute |

LLM call counts are tracked in Redis with per-user sliding window counters.

---

## 8. Document Security

### 8.1 File Type Validation

All uploaded files undergo multi-layer validation:

1. **Extension check**: Only allowed extensions are accepted
   - Allowed: `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.txt`, `.csv`, `.png`, `.jpg`, `.jpeg`, `.tiff`
2. **Magic bytes validation**: File content is inspected to verify it matches the declared type
   - PDF: `%PDF` header
   - ZIP-based (DOCX/XLSX/PPTX): `PK` header
   - Images: JPEG (`FF D8 FF`), PNG (`89 50 4E 47`)
3. **MIME type check**: Content-Type header is validated against allowed types
4. **File size limit**: Maximum 50 MB per file

### 8.2 Virus Scanning Integration Point

All uploaded files are scanned before processing:
- Integration point: ClamAV daemon (via `pyclamd` library)
- Files are scanned immediately upon upload
- Infected files are quarantined and the upload is rejected
- Scan results are logged in the audit log
- ClamAV virus definitions are updated daily via `freshclam`

### 8.3 File Storage Access Control

MinIO bucket policies:
- Private bucket: `documents` (default, no public access)
- Presigned URLs for downloads (valid for 15 minutes)
- No direct public URLs to document storage
- Bucket versioning enabled for recovery

### 8.4 Document-Level Permissions

Documents have the following access model:

```
document_permissions table:
- document_id (FK)
- user_id (FK)
- permission (enum: read, write, admin)
- granted_by (FK to users)
- granted_at (timestamp)
- expires_at (timestamp, nullable)
```

### 8.5 Audit Logging for Document Access

Every document access event is logged:
- Document upload (who, when, file metadata)
- Document download (who, when, IP address)
- Document processing (OCR/LLM, who initiated, parameters)
- Document deletion (who, when, soft/hard)
- Permission changes (who granted/revoked, to whom)

---

## 9. Infrastructure Security

### 9.1 Docker Security

All containers follow these security practices:

```dockerfile
# Run as non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

# Read-only filesystem where possible
# In docker-compose.yml:
read_only: true
tmpfs:
  - /tmp
  - /app/cache
```

Additional measures:
- No `--privileged` containers
- No host network mode (except for reverse proxy)
- Resource limits (CPU, memory) on all containers
- Health checks on all services
- Base images are scanned with `docker scout` or `trivy`

### 9.2 Network Segmentation

Docker networks are segmented by function:

```
frontend_net:  nginx, frontend
backend_net:   nginx, api, worker
data_net:      api, worker, postgres, redis, minio, qdrant
```

- `api` and `worker` are the only services with access to `data_net`
- `frontend` has no direct access to databases
- All inter-service communication is within Docker networks (no exposed ports except nginx)

### 9.3 Database Access Control

PostgreSQL security:
- Application user has `SELECT, INSERT, UPDATE, DELETE` on application schema only
- No DDL permissions for application user
- Migration user has DDL permissions (used only during deployment)
- `pg_hba.conf` restricts connections to Docker network CIDR
- Statement timeout: 30 seconds
- Connection pool limits: 20 connections per service

### 9.4 Redis AUTH

- Redis requires password authentication (`requirepass` directive)
- Redis is not exposed outside Docker network
- Dangerous commands are disabled: `FLUSHALL`, `FLUSHDB`, `CONFIG`, `DEBUG`
- Redis keys have TTL set (no indefinite keys)

### 9.5 Qdrant API Key

- Qdrant is configured with API key authentication
- API key is loaded from environment variable `QDRANT_API_KEY`
- Qdrant port (6333) is not exposed outside Docker network
- Collection-level access is managed via application-layer permissions

---

## 10. Dependency Security

### 10.1 Dependency Scanning

| Ecosystem | Tool | Frequency |
|-----------|------|-----------|
| Python (pip) | `pip-audit` | Every CI build + weekly scheduled scan |
| JavaScript (npm) | `npm audit` | Every CI build + weekly scheduled scan |
| Docker images | `trivy` | Every image build |

CI pipeline fails on any `HIGH` or `CRITICAL` vulnerability.

### 10.2 Version Pinning

- Python: `requirements.txt` uses exact versions (`package==1.2.3`)
- JavaScript: `package-lock.json` is committed; `npm ci` is used in CI/CD
- Docker: Base images use specific tags (not `latest`), e.g., `python:3.11.7-slim`
- Dependency updates are reviewed before merging

### 10.3 Security Update Process

1. Automated alerts from Dependabot/Renovate for known vulnerabilities
2. Critical vulnerabilities: patched within 24 hours
3. High vulnerabilities: patched within 7 days
4. Medium/Low vulnerabilities: patched in next scheduled release
5. All patches go through standard code review and CI/CD pipeline

### 10.4 License Compliance

- Allowed licenses: MIT, BSD, Apache 2.0, ISC, PSF, MPL 2.0
- Prohibited licenses: GPL (strong copyleft), AGPL (in libraries used by proprietary code)
- License scanning via `pip-licenses` and `license-checker`
- License report generated on each release

---

## 11. Audit Logging

### 11.1 What to Log

| Category | Events |
|----------|--------|
| **Authentication** | Login, logout, failed login, token refresh, password change, MFA events |
| **Authorization** | Permission denied, role changes, permission grants/revocations |
| **Documents** | Upload, download, delete, process, share, permission change |
| **Users** | Create, update, deactivate, role change |
| **LLM** | Query sent, response received, budget exceeded, policy violation |
| **System** | Configuration changes, deployment events, service restarts |
| **API** | All requests (method, path, status code, duration, user ID) |

### 11.2 Log Format

Structured JSON logs with the following fields:

```json
{
  "timestamp": "2026-06-11T15:03:07.123Z",
  "level": "INFO",
  "event_type": "document.upload",
  "user_id": "uuid",
  "user_email": "user@example.com",
  "resource_type": "document",
  "resource_id": "uuid",
  "action": "create",
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0...",
  "request_id": "uuid",
  "details": {
    "filename": "report.pdf",
    "file_size_bytes": 1048576,
    "mime_type": "application/pdf"
  },
  "status": "success",
  "duration_ms": 234
}
```

### 11.3 Log Retention

- **Hot storage** (local/ELK): 30 days
- **Warm storage** (compressed in object storage): 90 days
- **Cold storage** (archived): 1 year (compliance requirement)
- Logs older than 1 year are securely deleted

### 11.4 Log Integrity

- Logs are written to append-only storage
- Log files are rotated daily and compressed
- Logs are shipped to a centralized logging service (ELK stack or equivalent)
- Log tampering is detected via checksum verification
- Access to log storage is restricted to `admin` role

### 11.5 Compliance Requirements

- Audit logs must capture: who, what, when, where (IP), outcome
- Logs must be available for compliance audits within 24 hours
- Log access is itself audited

---

## 12. Incident Response

### 12.1 Detection Procedures

| Detection Method | Coverage |
|-----------------|----------|
| Automated alerts | Failed login spikes, unusual API patterns, budget overruns, error rate spikes |
| Log monitoring | Anomalous patterns in audit logs (e.g., mass document downloads) |
| Dependency scanning | New CVEs in production dependencies |
| User reports | Manual reports of suspicious activity |
| Health checks | Service degradation or downtime |

### 12.2 Response Playbook

**Severity Levels**:

| Level | Definition | Response Time |
|-------|-----------|---------------|
| P1 — Critical | Data breach, system compromise, complete outage | 1 hour |
| P2 — High | Partial outage, unauthorized access to sensitive data | 4 hours |
| P3 — Medium | Non-critical vulnerability, degraded performance | 24 hours |
| P4 — Low | Minor issue, informational | Next business day |

**Response Steps**:

1. **Identify**: Confirm the incident, assess scope and severity
2. **Contain**: Isolate affected systems, revoke compromised credentials
3. **Eradicate**: Remove the root cause (patch vulnerability, remove malware)
4. **Recover**: Restore services from clean backups, verify integrity
5. **Document**: Complete incident report with timeline, root cause, and remediation

### 12.3 Communication Plan

| Audience | Channel | Timing |
|----------|---------|--------|
| Internal team | Slack/Teams incident channel | Immediately upon detection |
| Management | Email | Within 1 hour of P1/P2 |
| Affected users | Email + in-app notification | Within 72 hours (GDPR requirement for data breaches) |
| Regulators | As required by law | Within 72 hours for data breaches affecting PII |

### 12.4 Post-Incident Review

- Blameless post-mortem conducted within 5 business days of incident closure
- Root cause analysis documented
- Action items tracked to completion
- Security policy updated if needed
- Lessons learned shared with the team

---

## 13. Compliance

### 13.1 Data Privacy (GDPR Considerations)

Even if not directly subject to GDPR, we follow its principles as best practice:

- **Right to access**: Users can request a copy of their data (`GET /users/me/data-export`)
- **Right to rectification**: Users can update their personal information
- **Right to erasure**: Users can request account and data deletion (`DELETE /users/me`)
- **Right to portability**: Data export in machine-readable format (JSON)
- **Data Protection Impact Assessment (DPIA)**: Conducted for new features processing PII
- **Privacy by design**: PII is minimized, pseudonymized where possible

### 13.2 Vietnamese Data Protection Laws

Compliance with Vietnamese regulations:
- **Cybersecurity Law (2018)**: Data localization requirements for Vietnamese user data
- **Personal Data Protection Decree (2023)**: Consent requirements, data subject rights
- **Decree 13/2023/ND-CP**: Personal data processing impact assessment requirements

Key measures:
- Vietnamese user data stored in servers located in Vietnam (or approved jurisdictions)
- Consent obtained before collecting personal data
- Data processing records maintained
- Data Protection Officer (DPO) designated (or equivalent responsibility)

### 13.3 Data Processing Agreements

- All third-party processors (LLM providers, cloud storage) have Data Processing Agreements (DPAs)
- DPAs include: data purpose, retention, security measures, breach notification obligations
- Annual review of all processor agreements
- Processors are assessed for security posture before onboarding

---

## 14. Security Checklist

### Per Feature

- [ ] Threat model reviewed for new feature
- [ ] Input validation implemented (Pydantic models)
- [ ] Authorization checks added (RBAC decorator)
- [ ] Rate limiting configured for new endpoints
- [ ] Audit logging added for all mutations
- [ ] PII handling reviewed (detection, masking, retention)
- [ ] LLM inputs/outputs sanitized (if applicable)
- [ ] Database queries use ORM (no raw SQL)
- [ ] Error messages do not leak sensitive information
- [ ] Unit tests cover security edge cases
- [ ] Code reviewed by at least one other developer

### Per Deployment

- [ ] All secrets rotated if compromised
- [ ] Database migrations tested and reversible
- [ ] Docker images rebuilt from latest base (security patches)
- [ ] Dependency scan passes with no HIGH/CRITICAL vulnerabilities
- [ ] TLS certificates valid and not expiring within 30 days
- [ ] Backup and restore procedure tested
- [ ] Health checks and monitoring configured
- [ ] Rate limiting verified in production environment
- [ ] CORS origins updated for new domains
- [ ] Security headers verified via `curl -I`
- [ ] Audit log shipping confirmed operational
- [ ] Rollback procedure documented and tested

---

## 15. Implementation Checklist

### Phase 1 — Foundation (Week 1-2)

- [ ] Implement JWT authentication with access/refresh token flow
- [ ] Set up bcrypt password hashing (cost factor 12)
- [ ] Implement RBAC middleware with admin/analyst/viewer roles
- [ ] Configure CORS with explicit allowed origins
- [ ] Add security headers middleware
- [ ] Set up rate limiting via Redis
- [ ] Implement Pydantic request validation for all endpoints
- [ ] Configure SQLAlchemy with parameterized queries only
- [ ] Set up structured JSON logging

### Phase 2 — Data Protection (Week 3-4)

- [ ] Enable MinIO server-side encryption
- [ ] Configure PostgreSQL encryption at rest
- [ ] Implement PII detection on document upload
- [ ] Add PII masking in logs and API responses
- [ ] Implement document-level permissions
- [ ] Set up audit logging for all document operations
- [ ] Configure data retention policies with automated cleanup
- [ ] Implement soft-delete with 30-day grace period

### Phase 3 — LLM & Document Security (Week 5-6)

- [ ] Implement prompt injection detection
- [ ] Add LLM input sanitization and output filtering
- [ ] Set up LLM cost budget tracking and limits
- [ ] Implement per-user LLM rate limiting
- [ ] Add magic bytes file validation
- [ ] Integrate ClamAV for virus scanning
- [ ] Implement presigned URLs for document downloads
- [ ] Add content policy enforcement for LLM outputs

### Phase 4 — Infrastructure & Operations (Week 7-8)

- [ ] Harden Docker containers (non-root, read-only, resource limits)
- [ ] Set up Docker network segmentation
- [ ] Configure Redis AUTH and disable dangerous commands
- [ ] Set up Qdrant API key authentication
- [ ] Implement dependency scanning in CI/CD
- [ ] Set up secret rotation procedures
- [ ] Configure centralized log aggregation (ELK or equivalent)
- [ ] Implement incident response alerting
- [ ] Conduct penetration testing
- [ ] Complete security documentation review

---

## 16. Acceptance Criteria

The system is considered security-compliant when all of the following are met:

| # | Criterion | Verification |
|---|-----------|-------------|
| 1 | All API endpoints require valid JWT token (except auth endpoints) | Automated test suite |
| 2 | Token expiration enforced (access: 15min, refresh: 7 days) | Automated test suite |
| 3 | RBAC enforced on all endpoints per permission matrix | Automated test suite |
| 4 | Rate limiting returns 429 when threshold exceeded | Load test |
| 5 | No SQL injection vulnerabilities | OWASP ZAP scan |
| 6 | No XSS vulnerabilities | OWASP ZAP scan |
| 7 | All secrets loaded from environment variables (no hardcoded secrets) | `detect-secrets` scan |
| 8 | File uploads validated by magic bytes | Manual test |
| 9 | PII detected and masked in logs | Log review |
| 10 | LLM prompt injection patterns detected and blocked | Automated test suite |
| 11 | All CRUD operations logged in audit trail | Audit log review |
| 12 | Docker containers run as non-root | Docker inspect |
| 13 | No HIGH/CRITICAL dependency vulnerabilities | `pip-audit` + `npm audit` |
| 14 | TLS 1.3 enforced on all external connections | SSL Labs test (A+ rating) |
| 15 | Data retention policies enforced automatically | Manual verification |
| 16 | Document access logged with user, timestamp, IP | Audit log review |
| 17 | LLM cost budgets enforced (per-user and system-wide) | Automated test suite |
| 18 | CORS restricted to allowed origins only | Manual test with `curl` |
| 19 | Security headers present on all responses | `curl -I` verification |
| 20 | Backup and restore procedure functional | DR drill |

---

*Last updated: 2026-06-11*
*Next review: 2026-09-11 (quarterly)*
*Owner: Security Team*
