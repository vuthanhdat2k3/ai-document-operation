# Phase 4 Code Review Report — Chunking, Embedding & RAG Pipeline

**Reviewer:** MiMoCode (Senior Code Review)
**Date:** 2026-06-12
**Scope:** `backend/app/rag/`, `backend/app/services/indexing_service.py`
**Overall Assessment:** **NEEDS_WORK**

---

## Table of Contents

1. [Overall Assessment](#1-overall-assessment)
2. [File-by-File Review](#2-file-by-file-review)
3. [Critical Issues (Must Fix)](#3-critical-issues-must-fix)
4. [Major Issues (Should Fix)](#4-major-issues-should-fix)
5. [Minor Issues (Nice to Have)](#5-minor-issues-nice-to-have)
6. [What Was Done Well](#6-what-was-done-well)
7. [Summary](#7-summary)

---

## 1. Overall Assessment

**Verdict: NEEDS_WORK**

Phase 4 delivers a well-decomposed RAG pipeline with clean separation between chunking, embedding, retrieval, fusion, reranking, query understanding, rewriting, context compilation, answer generation, and groundedness validation. The architecture is sound — each component is independently testable and follows single-responsibility principles.

However, there are several blocking issues:

- **4 Critical issues** — synchronous Qdrant client calls blocking the event loop in async methods, duplicate embedding computation, and no transaction rollback on partial failure
- **4 Major issues** — redundant LLMProvider protocol, unused imports, NaN/inf in fallback encoder, mutable default in Chunk
- **8 Minor issues** — token counting heuristic, logging inconsistency, documentation gaps

The core design is strong. The synchronous-in-async issues and the duplicate embedding computation in the retriever are the most urgent fixes.

---

## 2. File-by-File Review

### 2.1 `backend/app/rag/__init__.py`

**Rating:** ✅ Empty (expected for Phase 4)

No issues. Module-level `__init__.py` is empty as expected for a package of utility modules.

---

### 2.2 `backend/app/rag/chunker.py`

**Rating:** ✅ Excellent

Recursive separator strategy with overlap is the industry-standard approach (same as LangChain's `RecursiveCharacterTextSplitter`). Overlap application is correct. Hard-split fallback ensures no infinite recursion.

**Issues found:**

1. **[MINOR]** Line 24: `metadata: dict = field(default_factory=dict)` — Mutable default is correctly handled via `field(default_factory=dict)`, but note that `dict(metadata)` at line 157 creates a shallow copy only. Nested dicts/lists inside metadata will be shared references. Acceptable for current usage but worth noting.

2. **[MINOR]** Line 145: `original.find(piece, search_start)` can give incorrect offsets if the same text appears multiple times. This is a known limitation but acceptable for most documents.

3. **[INFO]** Line 40: Default separators `["\n\n", "\n", ". ", " ", ""]` are English-centric. CJK text without spaces would fall through to `_hard_split`. Consider adding CJK-aware separators for Vietnamese/Chinese documents.

**Positives:**
- Frozen dataclass for `Chunk` is correct for immutable value objects
- Overlap application at `_apply_overlap` (line 167) correctly extends each chunk with context from the previous chunk
- `search_start` tracking in `_merge_pieces` (line 160) prevents offset drift
- Proper validation in `__init__` that `chunk_overlap < chunk_size`

---

### 2.3 `backend/app/rag/embedder.py`

**Rating:** ⚠️ Needs Work

Graceful fallback to hash-based encoder when sentence-transformers is unavailable. Batch processing with configurable batch size. Sparse encoding attempt with TF fallback.

**Issues found:**

1. **[CRITICAL]** Lines 52-66: `_FallbackEncoder.encode()` uses SHA-512 unpacked as `float` — some resulting floats may be `NaN` or `inf`. The normalization at line 63-65 would propagate these non-finite values. Downstream Qdrant will reject vectors containing `NaN`/`inf`.

   ```python
   # Current (BUGGY):
   vec.append(struct.unpack("f", chunk)[0])  # Can produce NaN/inf
   norm = sum(v * v for v in vec) ** 0.5
   if norm > 0:
       vec = [v / norm for v in vec]  # NaN propagates through division

   # Fix:
   import math
   vec.append(struct.unpack("f", chunk)[0])
   # ... after building vec:
   vec = [v if math.isfinite(v) else 0.0 for v in vec]
   norm = sum(v * v for v in vec) ** 0.5
   if norm > 0:
       vec = [v / norm for v in vec]
   ```

2. **[MINOR]** Line 92: Type annotation `SentenceTransformer | _FallbackEncoder | None` mixes library and fallback types. Consider a Protocol/ABC for cleaner abstraction.

3. **[INFO]** Line 124: `hasattr(model, "encode")` is redundant — both `SentenceTransformer` and `_FallbackEncoder` have `encode`. This check always passes.

**Positives:**
- Lazy model loading via `_get_model()` avoids import-time side effects
- Batch processing in `embed_texts` is correct
- Sparse encoding with graceful fallback to TF is well-designed
- `_tf_sparse` is a clean last-resort fallback

---

### 2.4 `backend/app/rag/retriever.py`

**Rating:** ⚠️ Needs Work

Hybrid search (dense + sparse) with RRF fusion is the correct architecture. Filter building supports both exact match and `MatchAny`.

**Issues found:**

1. **[CRITICAL]** Lines 115-122, 145-152: `_dense_search` and `_sparse_search` call `self._client.query_points()` synchronously inside `async def` methods. The `qdrant_client.QdrantClient` is synchronous and will block the event loop. This is the same issue flagged in Phase 1 (C-1) — the codebase has a `QdrantClientWrapper` with async HTTP methods but the retriever uses the SDK directly.

   ```python
   # Current (BLOCKING):
   async def _dense_search(self, ...):
       results = self._client.query_points(...)  # BLOCKS event loop
       return self._parse_points(results)

   # Fix: Use the async wrapper or run_in_executor
   async def _dense_search(self, ...):
       loop = asyncio.get_running_loop()
       results = await loop.run_in_executor(
           None, lambda: self._client.query_points(...)
       )
       return self._parse_points(results)
   ```

2. **[CRITICAL]** Lines 85-87: Duplicate embedding computation. `embed_query(query)` returns a dense vector, then `embed_texts([query])` is called again for the same query to get sparse vectors. This doubles the embedding computation cost.

   ```python
   # Current (WASTEFUL):
   query_dense = self._embedder.embed_query(query)
   query_result = self._embedder.embed_texts([query])
   query_sparse = query_result.sparse[0] if query_result.sparse else None

   # Fix: Call embed_texts once and extract dense from it
   result = self._embedder.embed_texts([query])
   query_dense = result.dense[0]
   query_sparse = result.sparse[0] if result.sparse else None
   ```

3. **[MINOR]** Line 83: `from qdrant_client.models import Filter, FieldCondition, MatchValue, QueryResponse` — `Filter`, `FieldCondition`, `MatchValue` are imported but not used at this scope (they're used in `_build_filter`). `QueryResponse` is imported but never used.

4. **[MINOR]** Line 112: `from qdrant_client.models import NamedVector` imported but never used.

5. **[INFO]** Line 83: Imports from `qdrant_client.models` are inside methods. This is fine for optional-dependency handling but adds import overhead per call.

**Positives:**
- Hybrid search with RRF fusion is the correct architecture
- `_build_filter` supports both `MatchValue` and `MatchAny` for flexible filtering
- `_parse_points` correctly handles the Qdrant response structure
- `top_k * 2` oversampling before fusion is a good practice

---

### 2.5 `backend/app/rag/fusion.py`

**Rating:** ✅ Excellent

**No issues found.** Clean, minimal implementation of RRF (Cormack et al. 2009).

**Positives:**
- RRF formula is correctly implemented: `score(d) = Σ 1/(k + rank_i(d))`
- First-seen payload preservation is a reasonable design choice
- Default `k=60` matches the original paper
- `defaultdict(float)` for score accumulation is clean

---

### 2.6 `backend/app/rag/reranker.py`

**Rating:** ⚠️ Needs Work

Same fallback pattern as embedder — consistent design. Batch processing support.

**Issues found:**

1. **[MAJOR]** Line 34: Fallback encoder uses `abs(raw) / 10.0` which may not produce well-distributed scores. The hash-based approach gives deterministic but essentially random scores. If the reranker is used for ranking, these scores will produce arbitrary orderings. This is acceptable only when the real reranker is unavailable, but should be documented more prominently.

2. **[MINOR]** Line 33: `struct.unpack("f", digest[:4])[0]` — same `NaN`/`inf` concern as the embedder fallback. Though `abs(raw) / 10.0` and `min(1.0, ...)` will produce finite values, `raw` could theoretically be `inf` which would make `abs(inf)/10.0 = inf` and `min(1.0, inf) = 1.0`. The clamping works but the intermediate value is `inf`.

**Positives:**
- Lazy model loading via `_get_model()`
- Batch processing support in `rerank`
- Consistent fallback pattern with `_FallbackCrossEncoder`
- Score clamping to [0, 1] is correct

---

### 2.7 `backend/app/rag/query_understanding.py`

**Rating:** ✅ Good

Rule-based intent classification, entity extraction, and language detection. Well-suited for MVP without requiring an LLM.

**Issues found:**

1. **[MINOR]** Line 75: `_INTENT_KEYWORDS` patterns use `re.I` (inline flag) while other patterns in the module use `re.IGNORECASE` (module-level constant). Both work but the style is inconsistent.

2. **[INFO]** Line 118: `max(scores, key=scores.get)` — `scores.get` returns `None` for missing keys, but since we're iterating `scores.items()`, all keys exist. The `type: ignore[arg-type]` comment is technically correct but could be avoided by using `lambda x: x[1]` instead of `scores.get`.

3. **[INFO]** Lines 12-41: Regex patterns are compiled at module level, which is correct for performance. However, `_PERSON_ORG` (line 37) uses `[A-Z][a-zà-ỹ]+` which only matches names starting with an uppercase letter followed by lowercase — it will miss all-caps names like "VNPT" or "EVN".

**Positives:**
- Bilingual (Vietnamese/English) support is well-implemented
- `_extract_entities` covers section refs, dates, amounts, and person/org patterns
- Complexity assessment considers both word count and entity count
- `_classify_intent` correctly falls back to `EXPLORATORY` for queries without matching patterns

---

### 2.8 `backend/app/rag/query_rewrite.py`

**Rating:** ✅ Good

HyDE (Hypothetical Document Embeddings) and synonym-based query expansion. Vietnamese abbreviation expansion is a thoughtful addition.

**Issues found:**

1. **[MAJOR]** Lines 16, 49-52: `LLMProvider` protocol is defined here AND in `answer_generator.py:16-19`. The two definitions have slightly different default values (`max_tokens=256` vs `max_tokens=1024`, `temperature=0.3` vs `temperature=0.1`). This is a DRY violation — changes to one definition won't propagate to the other.

   ```python
   # query_rewrite.py:52
   async def generate(self, prompt: str, max_tokens: int = 256, temperature: float = 0.3) -> str: ...

   # answer_generator.py:19
   async def generate(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.1) -> str: ...
   ```

   **Fix:** Define `LLMProvider` once in a shared module (e.g., `rag/protocols.py`) and import from there. The caller should pass `max_tokens` and `temperature` explicitly when calling `generate()`.

2. **[INFO]** Line 58: `_FallbackLLM.generate` always returns the same generic response. This makes HyDE always produce the same hypothetical document regardless of the query, rendering HyDE ineffective in fallback mode. This is expected but should be documented.

**Positives:**
- HyDE implementation is correct (generate hypothetical answer → use as embedding input)
- Vietnamese abbreviation expansion is domain-specific and well-chosen
- Synonym-based expansion with deduplication
- `_rephrase` handles both English and Vietnamese question patterns
- Graceful fallback to original query on LLM failure

---

### 2.9 `backend/app/rag/context_compiler.py`

**Rating:** ✅ Good

Token-budgeted context assembly with citations. Clean, well-structured.

**Issues found:**

1. **[MINOR]** Line 67: `_estimate_tokens` uses `len(text) // 4` as a heuristic. For English this is reasonable (~4 chars/token), but for CJK text (where 1 character ≈ 1-2 tokens), this will significantly underestimate token usage. Could cause context to exceed LLM's actual token limit.

2. **[MINOR]** Line 129: `if used_tokens + block_tokens > available and citations:` — The `and citations` guard means the first chunk is always included even if it exceeds the budget. This is intentional (ensures at least one source) but should be documented.

3. **[INFO]** Line 11: `_APPROX_CHARS_PER_TOKEN = 4` is a constant. For production use, consider using `tiktoken` or the model's tokenizer for accurate counting.

**Positives:**
- Token budget management is correct (system prompt + query + context)
- Citation extraction with `[source:N]` notation is clean
- `_truncate_excerpt` for short citation previews is well-implemented
- System prompt is comprehensive with clear rules for grounding

---

### 2.10 `backend/app/rag/answer_generator.py`

**Rating:** ✅ Good

Grounded answer generation with citation extraction and confidence scoring.

**Issues found:**

1. **[MAJOR]** Lines 16-19: Duplicate `LLMProvider` protocol definition (see query_rewrite.py:16 above). Same DRY violation.

2. **[MINOR]** Line 93: `_extract_citations` returns `[available_citations[0]]` as fallback when no citations are found in the answer. This silently attributes the first source to answers that don't cite any source, which could be misleading.

3. **[INFO]** Lines 98-117: Confidence scoring is heuristic-based. The hedging phrase list is bilingual (English + Vietnamese) which is good, but the formula (`0.5 + citation_ratio * 0.4 - hedge_penalty`) is somewhat arbitrary. A confidence of 0.5 is the baseline even for answers with no citations.

**Positives:**
- Prompt construction with `<context>` and `<question>` XML tags is clean
- Citation extraction correctly handles `[source:N]` patterns
- Confidence estimation considers both citation density and hedging language
- Graceful LLM failure handling with informative fallback message

---

### 2.11 `backend/app/rag/groundedness.py`

**Rating:** ✅ Good

Keyword-overlap groundedness validation. Simple but effective for MVP.

**Issues found:**

1. **[MINOR]** Line 115: `ratio = len(overlap) / len(claim_kw)` — When `claim_kw` is empty (all words are stopwords), the function correctly returns `supported` at line 111. But the ratio calculation itself could be division-by-zero if `claim_kw` is non-empty but all keywords are stopwords (the `_extract_keywords` filter removes them). Actually, `_extract_keywords` at line 44 returns only non-stopwords, so if all claim words are stopwords, `claim_kw` is empty and the check at line 110 catches it. This is correct.

2. **[INFO]** Line 37: Minimum claim length of 15 characters is somewhat arbitrary. A claim like "VAT is 10%" (12 chars) would be filtered out. Consider lowering to 10 or using word count instead.

3. **[INFO]** Line 12: `_TOKENIZE = re.compile(r"\b\w{3,}\b", re.UNICODE)` — Words shorter than 3 characters are excluded. This means short but important terms like "VAT", "USD", "VNĐ" (2 chars) are never extracted as keywords, potentially affecting groundedness accuracy for financial documents.

**Positives:**
- Bilingual stopword list (English + Vietnamese)
- Clean claim splitting with citation tag removal
- `_extract_keywords` correctly filters stopwords
- Score calculation is simple and interpretable

---

### 2.12 `backend/app/services/indexing_service.py`

**Rating:** ⚠️ Needs Work

Clean pipeline: load chunks → embed → upsert → update DB. Batch upsert with configurable batch size.

**Issues found:**

1. **[CRITICAL]** Line 144: `self._client.upsert()` is a synchronous call inside `async def _upsert_to_qdrant()`. The `qdrant_client.QdrantClient` SDK's `upsert` method is synchronous and will block the event loop. Same issue as the retriever.

   ```python
   # Current (BLOCKING):
   async def _upsert_to_qdrant(self, ...):
       for start in range(0, len(points), batch_size):
           batch = points[start : start + batch_size]
           self._client.upsert(...)  # BLOCKS event loop

   # Fix:
   async def _upsert_to_qdrant(self, ...):
       for start in range(0, len(points), batch_size):
           batch = points[start : start + batch_size]
           loop = asyncio.get_running_loop()
           await loop.run_in_executor(
               None, lambda b=batch: self._client.upsert(
                   collection_name=self._collection, points=b
               )
           )
   ```

2. **[MAJOR]** Lines 84-86: No transaction rollback on partial failure. If `_upsert_to_qdrant` succeeds but `_update_chunk_records` fails (e.g., DB connection lost), vectors are in Qdrant but DB records are not updated. There's no compensation logic to delete the orphaned Qdrant points. Conversely, if `_upsert_to_qdrant` fails, the DB records are unchanged (good), but the chunks may have been partially embedded.

   **Recommendation:** Wrap in try/except. On Qdrant failure, don't update DB. On DB failure after Qdrant success, attempt to delete the upserted points.

3. **[MINOR]** Line 165: `chunk.token_count = len(chunk.chunk_text.split())` — This is a rough word count, not a token count. For accurate token counting, use `tiktoken` or the model's tokenizer. The field is named `token_count` but stores word count.

4. **[INFO]** Line 163: `chunk.embedding_ref = f"{self._collection}:{chunk.id}"` — Format `"{collection}:{chunk_id}"` is not parsed anywhere. Ensure downstream consumers know this format.

**Positives:**
- Clean 4-step pipeline: load → embed → upsert → update DB
- Batch upsert with configurable batch size (100)
- Proper collection existence check before upsert
- `embedding_model` and `embedding_dim` are correctly set for downstream use
- Empty chunk check with early return is good defensive coding

---

## 3. Critical Issues (Must Fix)

### C-1: Synchronous Qdrant Client Blocks Event Loop

**Files:** `backend/app/rag/retriever.py:115,145`, `backend/app/services/indexing_service.py:144`

**Impact:** `self._client.query_points()` and `self._client.upsert()` are synchronous SDK calls inside `async def` methods. They block the entire event loop during Qdrant communication. Under load, this will cause request timeouts and poor concurrency.

**Scope:** 3 call sites across 2 files.

### C-2: Duplicate Embedding Computation in Retriever

**File:** `backend/app/rag/retriever.py:85-87`

**Impact:** Both `embed_query(query)` and `embed_texts([query])` are called for the same query. `embed_texts` already returns both dense and sparse vectors. The duplicate call doubles embedding latency and compute cost for every search request.

### C-3: NaN/inf in Fallback Encoder Vectors

**File:** `backend/app/rag/embedder.py:52-65`

**Impact:** `_FallbackEncoder.encode()` unpacks SHA-512 digest bytes as `float32`. Some byte patterns produce `NaN` or `inf`. The normalization at line 63-65 propagates these non-finite values. Qdrant will reject vectors containing `NaN`/`inf` during upsert, causing indexing failures when running without sentence-transformers.

### C-4: No Transaction Rollback on Partial Indexing Failure

**File:** `backend/app/services/indexing_service.py:84-86`

**Impact:** If Qdrant upsert succeeds but DB update fails, vectors are orphaned in Qdrant with no DB metadata. If Qdrant fails, no compensation is needed (DB is unchanged), but the partial embedding state is inconsistent. No try/except wraps the pipeline.

---

## 4. Major Issues (Should Fix)

### M-1: Duplicate LLMProvider Protocol

**Files:** `backend/app/rag/query_rewrite.py:49-52`, `backend/app/rag/answer_generator.py:16-19`

**Impact:** `LLMProvider` is defined twice with different default parameter values (`max_tokens=256/1024`, `temperature=0.3/0.1`). Changes to one won't propagate to the other. Any class implementing one protocol may not satisfy the other if defaults diverge further.

**Fix:** Extract to a shared `rag/protocols.py` module.

### M-2: Unused Imports in Retriever

**File:** `backend/app/rag/retriever.py:83,112`

**Impact:** `QueryResponse`, `Filter`, `FieldCondition`, `MatchValue` (line 83) and `NamedVector` (line 112) are imported but never used at their respective scopes. Clutters the namespace and may confuse static analysis.

### M-3: Fallback CrossEncoder Score Distribution

**File:** `backend/app/rag/reranker.py:34`

**Impact:** `abs(raw) / 10.0` produces essentially random scores. If the reranker is used for ranking, these scores produce arbitrary orderings that may differ from the original retrieval order. The reranker should at minimum preserve the input order when no real model is available, or document that fallback scores are not meaningful.

### M-4: Mutable Default in Chunk.metadata Shared References

**File:** `backend/app/rag/chunker.py:157,189`

**Impact:** `dict(metadata)` creates a shallow copy. If metadata contains nested dicts or lists, those are shared across chunks. A mutation on one chunk's metadata would affect others. Current usage appears safe (metadata is a simple dict), but this is fragile.

---

## 5. Minor Issues (Nice to Have)

### m-1: Token Count Heuristic in IndexingService

**File:** `backend/app/services/indexing_service.py:165`

`len(chunk.chunk_text.split())` is word count, not token count. The `token_count` column in `DocumentChunk` will contain inaccurate values. For English, word count ≈ 0.75 × token count. For CJK, the discrepancy is larger.

### m-2: Token Estimation in ContextCompiler

**File:** `backend/app/rag/context_compiler.py:67`

`len(text) // 4` is a rough heuristic. For CJK text, 1 character ≈ 1-2 tokens, so this overestimates token usage by 2-4x, potentially excluding valid context.

### m-3: Logging Framework Inconsistency

All RAG modules use `logging.getLogger(__name__)` (stdlib). The rest of the codebase (Phase 1 error handler, middleware) uses `structlog`. This inconsistency means RAG logs won't have structured context (request_id, etc.).

### m-4: Regex Style Inconsistency in query_understanding.py

**File:** `backend/app/rag/query_understanding.py:75-101`

Some patterns use `re.I` (inline flag) while the module also uses `re.IGNORECASE` (named constant). Both work but the style is inconsistent within the same file.

### m-5: _FallbackLLM Returns Static Response

**Files:** `backend/app/rag/query_rewrite.py:58-63`, `backend/app/rag/answer_generator.py:25-30`

Both `_FallbackLLM` implementations return the same generic response regardless of input. HyDE and answer generation produce identical outputs in fallback mode, making the pipeline effectively deterministic. This is expected but should be documented prominently.

### m-6: _extract_citations Fallback Attribution

**File:** `backend/app/rag/answer_generator.py:92-93`

When no `[source:N]` pattern is found in the answer, `[available_citations[0]]` is returned as a fallback. This silently attributes the first source to uncited answers, which could mislead users into thinking the first source supports the answer.

### m-7: Groundedness Short-Word Exclusion

**File:** `backend/app/rag/groundedness.py:12`

`\b\w{3,}\b` excludes words shorter than 3 characters. Important terms like "VAT", "USD", "Q1" (2 chars) are never extracted as keywords, potentially reducing groundedness accuracy for financial/quarterly documents.

### m-8: _PERSON_ORG Pattern Misses All-Caps Names

**File:** `backend/app/rag/query_understanding.py:37-41`

`[A-Z][a-zà-ỹ]+` only matches names starting with uppercase + lowercase. All-caps organization names like "VNPT", "EVN", "PTIT" are not matched.

---

## 6. What Was Done Well

### Architecture & Design
- **Clean decomposition** — Each RAG component (chunker, embedder, retriever, fusion, reranker, query_understanding, query_rewrite, context_compiler, answer_generator, groundedness) is independently testable with clear responsibilities
- **Consistent fallback pattern** — Both embedder and reranker use the same `_Fallback*` pattern when sentence-transformers is unavailable, maintaining API compatibility
- **Protocol-based design** — `LLMProvider` protocol enables dependency injection without concrete class imports
- **Lazy model loading** — `_get_model()` in both embedder and reranker defers model loading until first use

### RAG Pipeline
- **Industry-standard chunking** — Recursive separator strategy matches LangChain's well-tested approach
- **Hybrid retrieval** — Dense + sparse with RRF fusion is the correct architecture for high-recall retrieval
- **Token-budgeted context** — ContextCompiler correctly manages token budgets with system prompt + query + context
- **Groundedness validation** — Keyword-overlap heuristic is simple but effective for MVP
- **Bilingual support** — Vietnamese abbreviation expansion, entity patterns, and stopword lists are domain-appropriate

### Code Quality
- **Google-style docstrings** on all public classes and methods
- **Type annotations** on nearly all function signatures
- **Frozen dataclasses** for immutable value objects (`Chunk`, `SearchResult`, `Citation`, `ContextPack`)
- **Consistent naming** following Python conventions (snake_case, UPPER_CASE for constants)
- **No hardcoded secrets** — All configuration via constructor parameters

### Error Handling
- **Graceful degradation** — LLM failures fall back to original query/generic response
- **Per-component error isolation** — Dense search failure doesn't crash sparse search
- **Empty input handling** — All entry points check for empty/missing data

---

## 7. Summary

| Category | Count | Status |
|----------|-------|--------|
| Critical (must fix) | 4 | 🔴 |
| Major (should fix) | 4 | 🟡 |
| Minor (nice to have) | 8 | 🟢 |
| **Total** | **16** | — |
| Files reviewed | 12 | — |

### Critical Action Items
1. **`retriever.py:115,145` + `indexing_service.py:144`** — Wrap all synchronous Qdrant SDK calls in `asyncio.run_in_executor()` or migrate to the async `QdrantClientWrapper`
2. **`retriever.py:85-87`** — Call `embed_texts` once and extract dense/sparse from the result
3. **`embedder.py:52-65`** — Add `math.isfinite()` check before normalization in `_FallbackEncoder`
4. **`indexing_service.py:84-86`** — Wrap pipeline in try/except with compensation logic for partial failures

### Recommended Action
Fix all 4 critical issues before proceeding to Phase 5. The synchronous-in-async issues (C-1) are the highest priority — they will cause production failures under concurrent load. The duplicate embedding computation (C-2) is a quick fix with immediate performance benefit.
