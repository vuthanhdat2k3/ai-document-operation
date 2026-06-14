# Phase 5 — RAG Q&A Pipeline Code Review Report

| Field | Value |
|---|---|
| **Reviewer** | MiMoCode (automated) |
| **Date** | 2026-06-12 |
| **Scope** | `backend/app/rag/` (Q&A modules), `backend/app/services/qa_service.py`, `backend/app/api/v1/qa.py`, `backend/app/api/schemas/qa.py` |
| **Overall Assessment** | **Good** — Well-structured RAG pipeline with clean architecture and bilingual support. Several security and production-readiness issues must be addressed before deployment. |

---

## Table of Contents

1. [Overall Assessment](#1-overall-assessment)
2. [File-by-File Review](#2-file-by-file-review)
   - 2.1 [query_understanding.py](#21-query_understandingpy)
   - 2.2 [query_rewrite.py](#22-query_rewritepy)
   - 2.3 [context_compiler.py](#23-context_compilerpy)
   - 2.4 [answer_generator.py](#24-answer_generatorpy)
   - 2.5 [groundedness.py](#25-groundednesspy)
   - 2.6 [qa_service.py](#26-qa_servicepy)
   - 2.7 [qa.py (API)](#27-qapy-api)
   - 2.8 [schemas/qa.py](#28-schemasqapy)
3. [Critical Issues (Must Fix)](#3-critical-issues-must-fix)
4. [Major Issues (Should Fix)](#4-major-issues-should-fix)
5. [Minor Issues (Nice to Have)](#5-minor-issues-nice-to-have)
6. [What Was Done Well](#6-what-was-done-well)
7. [Summary Table](#7-summary-table)

---

## 1. Overall Assessment

The Phase 5 RAG Q&A pipeline implements a well-organized 7-stage pipeline (query understanding → query rewriting → retrieval → reranking → context compilation → answer generation → groundedness validation). The code follows existing codebase patterns, provides bilingual Vietnamese/English support, and includes graceful fallbacks for missing dependencies.

However, several issues block production deployment:

- **No document access control** on the Q&A endpoint — any user can query any document.
- **Unbounded in-memory session store** that will cause OOM in production.
- **Synchronous CPU-bound reranking** blocks the event loop.
- **Duplicate `LLMProvider` protocol** across two modules creates a maintenance hazard.

The pipeline is functionally correct for single-user development but requires hardening for multi-tenant production use.

---

## 2. File-by-File Review

### 2.1 query_understanding.py

**Lines reviewed**: 1–230

A pure-regex, rule-based query analyzer. No LLM dependencies, no async — clean and predictable.

| Aspect | Assessment |
|---|---|
| Type hints | ✅ Complete. All functions have return type annotations. `QueryAnalysis` uses dataclass with field defaults. |
| Docstrings | ✅ Module, class, and public method docstrings present. Args/Returns documented. |
| Naming | ✅ Clear names. `_INTENT_KEYWORDS`, `_extract_entities`, `_classify_intent` follow private-by-convention. |
| Error handling | ✅ Empty query handled gracefully at line 203–209. |
| Security | ✅ Pure computation, no attack surface. |
| Issues | ⚠️ `_classify_intent` (line 118): `max(scores, key=scores.get)` triggers `# type: ignore[arg-type]` because `dict.get` returns `Optional[V]`. Could use `max(scores, key=lambda k: scores[k])` to avoid the ignore. |

**Verdict**: Clean, no blocking issues.

---

### 2.2 query_rewrite.py

**Lines reviewed**: 1–187

Provides HyDE rewrite (async, LLM-backed) and deterministic synonym expansion.

| Aspect | Assessment |
|---|---|
| Type hints | ✅ `LLMProvider` protocol defined. `QueryRewriter.__init__` properly typed. |
| Docstrings | ✅ All public methods documented. |
| Naming | ✅ Consistent with codebase. |
| Error handling | ✅ HyDE failure falls back to original query (line 111–114). |
| Security | ⚠️ HyDE prompt (line 97–103) embeds user query directly via f-string. Prompt injection risk if query contains adversarial instructions. |
| Issues | ⚠️ **Duplicate `LLMProvider`** (line 48–52) — identical definition exists in `answer_generator.py:15–19`. Violates DRY. |
| | ⚠️ `_FallbackLLM` (line 55–63) returns generic text silently. Caller has no signal that no real LLM is available. |

**Verdict**: Functional but DRY violation and prompt injection risk.

---

### 2.3 context_compiler.py

**Lines reviewed**: 1–160

Assembles retrieved chunks into a `ContextPack` with token budgeting and citation formatting.

| Aspect | Assessment |
|---|---|
| Type hints | ⚠️ `chunks: list` at line 93 — missing type parameter. Should be `list[SearchResult]`. |
| Docstrings | ✅ All classes and methods documented. |
| Naming | ✅ `Citation`, `ContextPack`, `ContextCompiler` are clear. |
| Token estimation | ⚠️ `_estimate_tokens` (line 65–67) uses `len(text) // 4`. For Vietnamese text (1–2 char tokens), this overestimates token count, reducing the number of sources included in context. |
| Security | ✅ No external input injection. |
| Logic | ✅ Budget-based truncation with `available` calculation at line 121 is correct. |

**Verdict**: Minor type hint and estimation issues. Functional.

---

### 2.4 answer_generator.py

**Lines reviewed**: 1–177

Generates grounded answers from context, extracts citations, and computes confidence.

| Aspect | Assessment |
|---|---|
| Type hints | ✅ `Answer` dataclass well-typed. `LLMProvider` protocol defined. |
| Docstrings | ✅ Complete. |
| Error handling | ✅ LLM failure handled at line 153–161 with fallback message. |
| Security | ⚠️ Prompt (line 51–67) embeds user query directly. Same prompt injection risk as `query_rewrite.py`. |
| Issues | ⚠️ **Duplicate `LLMProvider`** (line 15–19) — identical to `query_rewrite.py:48–52`. |
| | ⚠️ `_extract_citations` (line 92–93): When no `[source:N]` tags found but citations exist, silently returns first citation. Misleading. |
| | ⚠️ `_FallbackLLM` (line 22–30) returns canned text with `[source:1]` — artificial citation. |

**Verdict**: Functional but DRY violation and citation fallback is misleading.

---

### 2.5 groundedness.py

**Lines reviewed**: 1–138

Keyword-overlap heuristic to validate answer claims against source texts.

| Aspect | Assessment |
|---|---|
| Type hints | ✅ `GroundednessResult` well-typed. |
| Docstrings | ✅ Complete. |
| Logic | ⚠️ Claims with no keywords (all stop words) are treated as supported (line 110–112). This inflates groundedness scores. |
| | ⚠️ `_SENTENCE_SPLIT` (line 11) doesn't handle abbreviations ("Dr.", "Mr.") — may split incorrectly. |
| | ⚠️ Stop word list (line 14–24) includes generic terms like "information", "context" which are common in RAG answers. This reduces keyword overlap for legitimate claims. |
| Security | ✅ Pure computation. |

**Verdict**: Heuristic approach is reasonable but has edge cases that inflate scores.

---

### 2.6 qa_service.py

**Lines reviewed**: 1–199

Orchestrator for the full 7-stage RAG pipeline.

| Aspect | Assessment |
|---|---|
| Type hints | ⚠️ `llm_provider: Any | None = None` at line 70 — should use `LLMProvider | None` for type safety. |
| Docstrings | ✅ Excellent. Pipeline stages documented in class docstring. |
| Error handling | ✅ Each stage has try/except with fallback. Pipeline degrades gracefully. |
| Security | ⚠️ No `document_id` validation or access control check. |
| Issues | ⚠️ **Reranker called synchronously** (line 160) — `self._reranker.rerank()` is CPU-bound and blocks the event loop. Should use `asyncio.to_thread()`. |
| | ⚠️ Low groundedness (line 177) only logs a warning. Answer is still returned to user without any indicator. |
| | ⚠️ `Reranker()` instantiated per-service-call (line 73). Model loading on every request is expensive. |

**Verdict**: Well-structured but has async correctness and performance issues.

---

### 2.7 qa.py (API)

**Lines reviewed**: 1–130

FastAPI router for Q&A endpoints.

| Aspect | Assessment |
|---|---|
| Type hints | ✅ Dependencies properly annotated with `Annotated` + `Depends`. |
| Docstrings | ✅ Endpoint docstrings present. |
| Error handling | ✅ Pipeline exceptions caught and re-raised as HTTP 500. |
| Security | 🔴 **No document access control** — any authenticated user can query any document. |
| | 🔴 **No user authentication** — `ask_question` has no `user_id` dependency (compare with `documents.py` which has `_get_current_user_id`). |
| | 🔴 **Nil UUID fallback** (line 71) — `document_id or "00000000-..."` silently searches ALL documents when no ID provided. |
| Issues | 🔴 **Memory leak** (line 32) — `_SESSION_STORE: dict[str, list[dict]]` grows unboundedly. No TTL, no eviction, no max size. Production OOM risk. |
| | ⚠️ **New QAService per request** (line 35–42) — `_get_qa_service` creates new `EmbeddingPipeline`, `HybridRetriever`, `Reranker` on every request. These load ML models — extremely expensive. |
| | ⚠️ **No rate limiting** — `/ask` endpoint has no rate limiting despite `RateLimitError` being defined in error_handler. |
| | ⚠️ **Session history doesn't paginate** (line 106–129) — large sessions return unbounded response. |
| | ⚠️ **Timestamp not captured** (line 87–95) — history entry dict omits `timestamp` field, so `QAHISTORYEntry.timestamp` is always `None`. |

**Verdict**: Multiple security and production issues. Must be addressed before deployment.

---

### 2.8 schemas/qa.py

**Lines reviewed**: 1–75

Pydantic v2 request/response schemas.

| Aspect | Assessment |
|---|---|
| Type hints | ✅ All fields typed. |
| Validation | ⚠️ `document_id: str | None` (line 17) — no UUID validation. Any string accepted. |
| | ⚠️ `session_id: str | None` (line 21) — same issue. |
| Immutability | ✅ All models use `ConfigDict(frozen=True)`. |
| Naming | ⚠️ `QAHISTORYEntry` (line 56) uses ALL-caps "HISTORY" — inconsistent with `QAResponse`, `QASessionResponse`. Should be `QAHistoryEntry`. |

**Verdict**: Clean schemas but UUID validation missing.

---

## 3. Critical Issues (Must Fix)

### C1. No Document Access Control

**File**: `backend/app/api/v1/qa.py:59–103`

The `ask_question` endpoint performs no user authentication or document ownership verification. Any caller can query any `document_id`. Compare with `documents.py` which enforces `user_id` checks via `DocumentService.get_document()`.

**Impact**: Security vulnerability — data leakage across tenants.

**Fix**: Add `user_id: uuid.UUID = Depends(_get_current_user_id)` dependency. Verify document ownership before querying.

---

### C2. Unbounded In-Memory Session Store

**File**: `backend/app/api/v1/qa.py:32`

```python
_SESSION_STORE: dict[str, list[dict]] = {}
```

This module-level dict grows without bound. Each Q&A request appends entries (line 87). No TTL, no max size, no eviction. In production with multiple concurrent users, this causes OOM.

**Impact**: Memory exhaustion, service crash.

**Fix**: Use Redis (already available via `get_redis` dependency) with TTL, or add max-size LRU cache with eviction. At minimum, add a TTL-based expiry.

---

### C3. Synchronous CPU-Bound Reranking

**File**: `backend/app/services/qa_service.py:160`

```python
reranked_indices = self._reranker.rerank(query, doc_texts, top_k=8)
```

`Reranker.rerank()` (in `reranker.py:70–102`) loads and runs a PyTorch cross-encoder model synchronously. Called from an `async` function, this blocks the event loop for potentially hundreds of milliseconds.

**Impact**: Event loop starvation, degraded throughput under load.

**Fix**: Wrap in `await asyncio.to_thread(self._reranker.rerank, query, doc_texts, top_k=8)`.

---

### C4. New QAService (with ML Models) Created Per Request

**File**: `backend/app/api/v1/qa.py:35–42`

```python
async def _get_qa_service(...) -> QAService:
    embedder = EmbeddingPipeline()
    retriever = HybridRetriever(qdrant_client=qdrant_client, embedder=embedder)
    reranker = Reranker()
    return QAService(retriever=retriever, reranker=reranker)
```

Every request creates new `EmbeddingPipeline` (loads tokenizer/model), `Reranker` (loads cross-encoder), and `HybridRetriever`. This is extremely expensive and defeats model caching.

**Impact**: High latency, excessive memory usage, repeated model loading.

**Fix**: Use module-level singletons or FastAPI `lifespan`-scoped dependencies. The `EmbeddingPipeline` and `Reranker` should be created once at startup.

---

## 4. Major Issues (Should Fix)

### M1. Duplicate LLMProvider Protocol

**Files**: `query_rewrite.py:48–52`, `answer_generator.py:15–19`

Two identical `LLMProvider` protocol definitions. If one changes, the other silently diverges.

**Fix**: Define once in a shared module (e.g., `backend/app/rag/llm.py`) and import from both.

---

### M2. Nil UUID Fallback for document_id

**File**: `backend/app/api/v1/qa.py:71`

```python
document_id = body.document_id or "00000000-0000-0000-0000-000000000000"
```

Silently searches ALL documents when no ID is provided. This is a data leakage vector.

**Fix**: Either require `document_id` (make field non-optional) or add explicit authorization check for cross-document queries.

---

### M3. No UUID Validation on Request Fields

**File**: `backend/app/api/schemas/qa.py:17–23`

`document_id` and `session_id` are `str | None` — any arbitrary string is accepted.

**Fix**: Use `str | None = Field(None, pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")` or `uuid.UUID` type.

---

### M4. Groundedness Score Not Surfaced to User

**File**: `backend/app/services/qa_service.py:177–182`

Low groundedness (< 0.5) only logs a warning. The answer is still returned with no user-facing indicator.

**Fix**: Add `groundedness_warning: str | None = None` to `QAResponse` and populate when score is low.

---

### M5. History Entry Missing Timestamp

**File**: `backend/app/api/v1/qa.py:87–95`

History entry dict doesn't include `timestamp`, but `QAHISTORYEntry` has `timestamp: datetime | None = None`. All history entries will have `None` timestamps.

**Fix**: Add `"timestamp": datetime.now(timezone.utc)` to the dict at line 91.

---

### M6. Prompt Injection Risk

**Files**: `query_rewrite.py:102`, `answer_generator.py:61`

User query is embedded directly into LLM prompts via f-string interpolation without sanitization.

**Fix**: Wrap user query in XML tags (already done partially with `<question>` tag). Consider input sanitization or prompt hardening.

---

### M7. No Rate Limiting on /ask Endpoint

**File**: `backend/app/api/v1/qa.py:59`

The Q&A endpoint has no rate limiting. `RateLimitError` is defined but unused.

**Fix**: Add rate limiting middleware or dependency, especially since each request involves LLM calls.

---

## 5. Minor Issues (Nice to Have)

| # | File:Line | Description |
|---|---|---|
| m1 | `query_understanding.py:118` | `max(scores, key=scores.get)` triggers type ignore. Use `key=lambda k: scores[k]` instead. |
| m2 | `groundedness.py:11` | Sentence splitter doesn't handle abbreviations ("Dr.", "Mr.") — may split incorrectly. |
| m3 | `groundedness.py:14–24` | Stop word list includes "information", "context" — reduces keyword overlap for legitimate RAG claims. |
| m4 | `groundedness.py:110–112` | Claims with no keywords (all stop words) treated as supported — inflates groundedness scores. |
| m5 | `answer_generator.py:92–93` | When no citations found in answer, defaults to first available citation — misleading. |
| m6 | `context_compiler.py:93` | `chunks: list` missing type parameter. Should be `list[SearchResult]`. |
| m7 | `context_compiler.py:65–67` | Token estimation `len(text) // 4` overestimates Vietnamese tokens, reducing source inclusion. |
| m8 | `qa_service.py:70` | `llm_provider: Any | None` should be `LLMProvider | None` for type safety. |
| m9 | `qa.py:106–129` | Session history endpoint returns unbounded list — should paginate. |
| m10 | `schemas/qa.py:56` | `QAHISTORYEntry` naming inconsistent — should be `QAHistoryEntry`. |
| m11 | `query_rewrite.py:154` | `_apply_synonyms` only replaces first matching synonym — limits expansion quality. |

---

## 6. What Was Done Well

1. **Clean pipeline architecture** — The 7-stage pipeline in `qa_service.py` is well-organized with clear separation of concerns. Each stage is independently testable.

2. **Bilingual support** — Vietnamese and English are consistently handled across all modules (intent classification, entity extraction, query rewriting, grounding).

3. **Graceful degradation** — LLM failures in HyDE and answer generation fall back to reasonable defaults rather than crashing the pipeline.

4. **Groundedness validation** — A dedicated validation stage for hallucination detection is a strong pattern for production RAG systems.

5. **Consistent error handling** — Exceptions are caught and logged with `exc_info=True` for debugging, with fallback behavior at each stage.

6. **Clean data structures** — Well-defined dataclasses (`QueryAnalysis`, `ContextPack`, `Answer`, `GroundednessResult`, `Citation`) provide clear intermediate representations.

7. **Modern Pydantic schemas** — `ConfigDict(frozen=True)` for immutability, proper `Field` constraints (`min_length`, `max_length`, `ge`, `le`).

8. **Consistent with codebase** — Follows the same service + schema + router pattern as the documents module.

9. **Comprehensive docstrings** — All public methods have docstrings with `Args`/`Returns` sections.

10. **Appropriate logging** — Structured logging at debug/info/warning levels throughout the pipeline.

---

## 7. Summary Table

| Category | Count | IDs |
|---|---|---|
| Critical (Must Fix) | 4 | C1, C2, C3, C4 |
| Major (Should Fix) | 7 | M1–M7 |
| Minor (Nice to Have) | 11 | m1–m11 |
| **Total Issues** | **22** | |

| Severity | Count |
|---|---|
| Security | 3 (C1, C2, M6) |
| Production-readiness | 4 (C2, C3, C4, M7) |
| Correctness | 3 (M4, M5, m4) |
| Maintainability | 2 (M1, m10) |
| Performance | 2 (C3, C4) |
| Type safety | 2 (M3, m6) |
| UX | 1 (M2) |
| Code quality | 5 (m1, m2, m3, m5, m11) |
