# Code Review Report — Phase 7-9: Extraction, Risk Analysis, Reports

**Reviewer:** Kilo Code Review Agent  
**Date:** 2026-06-12  
**Scope:** 16 files across extraction, risk analysis, and report generation services

---

## Executive Summary

Phases 7-9 implement the core document intelligence pipeline: field extraction, risk analysis, and report generation/export. The codebase is well-structured with clear separation of concerns, proper use of dataclasses, and consistent error handling. Several issues were identified that should be addressed before production deployment.

**Overall Rating: B+ (Good)**

| Area | Rating | Notes |
|------|--------|-------|
| Architecture | A | Clean pipeline pattern, proper DI |
| Error Handling | B+ | Custom exceptions, but some gaps |
| Type Safety | B | Good typing, some `Any` overuse |
| Testing | C | No tests for Phase 7-9 until now |
| Security | B | No secrets exposed, but input validation gaps |
| Performance | B- | Text normalization could be expensive at scale |

---

## Phase 7 — Field Extraction

### 7.1 `classifier.py` — Document Classifier

**Strengths:**
- Comprehensive Vietnamese + English keyword coverage
- Weighted scoring with pattern boosting is well-designed
- Confidence calculation considers text length factor
- Subtype detection via threshold ratio

**Issues:**

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 1 | Medium | `classifier.py:136` | `_normalize_text` only lowercases and collapses whitespace — Vietnamese diacritics are preserved, which is correct, but duplicated keywords with/without diacritics (e.g. "hợp đồng" / "hop dong") create separate match counts. This is intentional but could produce unexpected scoring when both appear. |
| 2 | Low | `classifier.py:199` | `text_length_factor = min(len(text) / 500, 1.0)` — short documents (<500 chars) get penalised confidence. For invoice line items or short dispatches, this may under-report confidence. Consider a document-type-aware threshold. |
| 3 | Low | `classifier.py:146` | `text.count(keyword)` counts overlapping occurrences. For short keywords like "đ" or "v/v", this could inflate scores spuriously. The current keyword list avoids single-char keywords, but future additions might break this. |
| 4 | Info | `classifier.py:92` | `SUBTYPE_THRESHOLD_RATIO = 0.6` is a class constant but never documented. Consider adding a docstring. |

### 7.2 `field_extractor.py` — Field Extractor

**Strengths:**
- LLM-with-rule-based-fallback pattern is robust
- JSON parsing handles markdown code fences and nested objects
- Vietnamese field name mappings are comprehensive
- Type casting handles comma-separated numbers

**Issues:**

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 5 | High | `field_extractor.py:86` | LLM failure is silently caught and falls back to rules. No metrics/logging for LLM failures — could mask systematic LLM issues in production. |
| 6 | Medium | `field_extractor.py:100` | Text is truncated to 8000 chars for LLM prompt. No warning logged when truncation occurs. Long contracts may lose critical information in the truncated portion. |
| 7 | Medium | `field_extractor.py:278` | `_cast_value` for numeric types strips `[^\d.\-]` which removes currency symbols but also removes trailing text like "VND". This is correct for casting but the raw_text should preserve the original. |
| 8 | Low | `field_extractor.py:136-145` | JSON parsing falls back to regex `\[.*\]` with `re.DOTALL` — this could match a JSON array embedded in a larger response incorrectly if the LLM returns explanation text containing brackets. |
| 9 | Low | `field_extractor.py:232` | `_get_extraction_patterns` rebuilds patterns on every call. These could be cached per (field_name, field_type, document_type) tuple. |

### 7.3 `field_validator.py` — Field Validator

**Strengths:**
- Comprehensive type validation (string, number, integer, boolean, date)
- Format validation for dates, emails, phones, currency, and custom patterns
- Min/max value and maxLength constraints
- Low-confidence field warnings

**Issues:**

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 10 | Medium | `field_validator.py:136-149` | Number validation for string values strips non-numeric chars and tries `float()`. A value like "123abc" would become `123` after stripping — this silently accepts malformed input. Consider rejecting strings that contain significant non-numeric portions. |
| 11 | Medium | `field_validator.py:28-30` | `PHONE_PATTERN` is very permissive — `^[\+]?[(]?[0-9]{1,4}[)]?[-\s./0-9]*$` matches strings like "+1" or "(0)". The separate length check at line 214 helps but only for the phone format branch. |
| 12 | Low | `field_validator.py:32-34` | `VND_MONEY_PATTERN` is defined but never used in any validation method. Dead code. |
| 13 | Low | `field_validator.py:80` | `fv.field_value.get("value")` assumes `field_value` is always a dict. If an LLM returns a non-dict `field_value`, this raises `AttributeError`. |

### 7.4 `field_normalizer.py` — Field Normalizer

**Strengths:**
- Comprehensive date format handling including Vietnamese format ("15 tháng 6 năm 2024")
- Currency normalization handles mixed separators (European vs US formats)
- Phone normalization handles +84, 84, and 0-prefix Vietnamese numbers
- Address normalization standardizes Vietnamese abbreviations (TP., Q., P.)

**Issues:**

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 14 | High | `field_normalizer.py:20-21` | `DATE_FORMATS` has ambiguity: `%d/%m/%Y` and `%m/%d/%Y` patterns both match `^\d{1,2}/\d{1,2}/\d{4}$`. Since `%d/%m/%Y` comes first, all dates are interpreted as DD/MM/YYYY. This is correct for Vietnamese documents but wrong for US-format dates. No disambiguation logic exists. |
| 15 | Medium | `field_normalizer.py:199-209` | Currency separator disambiguation: when both `,` and `.` are present, the code checks which appears last. This handles "1.000.000,50" (European) vs "1,000,000.50" (US). However, for Vietnamese documents that commonly use "1.000.000" (dot as thousands separator, no decimal), the single-comma branch at line 204-209 could misinterpret "1,5" as 1.5 instead of treating comma as thousands separator when there's only one comma and 1-2 digits after it. |
| 16 | Medium | `field_normalizer.py:95` | Long line — the currency keyword check exceeds 120 chars. Consider breaking into a helper or extracting keywords to a constant. |
| 17 | Low | `field_normalizer.py:216-218` | VND formatting uses `f"{amount:,.0f} VND".replace(",", ".")` which replaces ALL commas with dots. For amounts >= 1 billion, this produces "1.000.000.000 VND" which is correct Vietnamese formatting but the replace is fragile. |

### 7.5 `extraction_service.py` — Extraction Service

**Strengths:**
- Clean pipeline orchestration (classify → extract → validate → normalize → save)
- Upsert logic for re-extraction avoids duplicates
- Document text retrieval checks multiple metadata keys
- Proper use of dependency injection

**Issues:**

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 18 | High | `extraction_service.py:86` | Bare `except Exception` at line 86 in `field_extractor.py` (called by this service) — the extraction service doesn't distinguish between LLM failures and rule-engine bugs. Both silently fall back to rules. |
| 19 | Medium | `extraction_service.py:163-166` | `extracted_count` counts fields with non-null values, but `valid_count` at line 178 counts fields with `confidence >= 0.5`. These two metrics measure different things and could confuse API consumers. |
| 20 | Low | `extraction_service.py:328-355` | `_get_document_text` tries 5 different metadata keys then pages. No logging for which key was used — makes debugging extraction issues harder. |

### 7.6 `extraction.py` — Extraction API

**Strengths:**
- Clean REST endpoints with proper HTTP methods
- Error mapping from service exceptions to HTTP errors
- Pydantic response models

**Issues:**

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 21 | Medium | `extraction.py:35` | Hardcoded `CURRENT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")` — placeholder auth that should be replaced before production. |
| 22 | Medium | `extraction.py:90` | `id=""` for ExtractedFieldResponse — the extracted fields from the pipeline don't have DB IDs yet (they're computed). The API returns empty string IDs which could confuse clients. |
| 23 | Low | `extraction.py:208-211` | Error handling for `update_field` uses string matching `"not found" in str(exc).lower()` — fragile. Should catch specific `ExtractionServiceError` subclass. |

---

## Phase 8 — Risk Analysis

### 8.1 `risk_detector.py` — Risk Detector

**Strengths:**
- Well-structured rule engine with clear separation of each risk category
- Severity-based sorting (critical → info)
- Evidence capture with raw match text and page estimation
- Vietnamese keyword coverage for penalty, payment, and signature terms

**Issues:**

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 24 | High | `risk_detector.py:268-270` | `_detect_expired_dates` imports `date` from `datetime` inside the method. This is unusual and could cause issues if the module-level import is expected. More importantly, it uses `date.today()` which makes the test non-deterministic — expired date detection depends on the current date. |
| 25 | Medium | `risk_detector.py:100` | Amount parsing: `raw_number.replace(",", "").replace(".", "")` treats both `,` and `.` as thousands separators. For "1.5 tỷ" this produces "15" then multiplies by 1 billion → 15 billion, but the original was 1.5 billion. The regex `\d{1,3}(?:[.,]\d{3})*` only matches groups of 3 digits, so "1.5" wouldn't match. This is actually correct for the pattern but the comment-worthy logic is fragile. |
| 26 | Medium | `risk_detector.py:160-163` | Penalty context window is fixed at [-50, +150] chars. For documents with dense text, the percentage match could capture a number from an unrelated clause. |
| 27 | Low | `risk_detector.py:20-22` | `_DEADLINE_PATTERN` captures `(\d{1,2})\s*(?:ngày|day|days)` but the Vietnamese word "ngày" also means "date". False positives possible for patterns like "ngày 5 tháng 6" (June 5th). |
| 28 | Low | `risk_detector.py:329-333` | `_estimate_page` uses form-feed `\f` characters as page breaks. If the source text doesn't use form-feeds, all items are on page 1. |

### 8.2 `clause_detector.py` — Clause Detector

**Strengths:**
- Template-based approach is extensible
- Separate templates for contracts and invoices
- Fallback to combined templates for unknown document types
- `min_matches` threshold prevents false positives from single keyword matches

**Issues:**

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 29 | Medium | `clause_detector.py:241-243` | For unknown document types, ALL contract + invoice clauses are checked. This produces many false "missing" clauses for documents like reports or dispatches that don't need contract terms. |
| 30 | Low | `clause_detector.py:249` | `sum(1 for kw in tpl.keywords if kw in text_lower)` is O(n*m) where n=keywords and m=text length. For large documents with many keywords, this could be slow. Using `re.search` with alternation or Aho-Corasick would be more efficient. |
| 31 | Low | `clause_detector.py:33-141` | Clause template keyword lists don't include common English terms for some categories (e.g., "confidentiality" has "confidential" but not "non-compete", "trade secret"). |

### 8.3 `anomaly_detector.py` — Anomaly Detector

**Strengths:**
- Z-score based statistical approach is sound
- Configurable norms per document type
- Handles nested field values (dict with "value", "amount", etc.)
- Graceful handling of missing norms for document types

**Issues:**

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 32 | Medium | `anomaly_detector.py:11-49` | Hard-coded statistical norms. These should be derived from actual historical data or at minimum be configurable via environment/database. The current values are assumptions that may not reflect real-world distributions. |
| 33 | Low | `anomaly_detector.py:120` | `std = norms_std.get(field_name, expected_mean * 0.5)` — defaulting to 50% of mean is a rough heuristic. For fields with mean=0, this would produce std=0 and skip the field. |
| 34 | Low | `anomaly_detector.py:163` | String-to-numeric conversion `cleaned.replace(",", "")` doesn't handle European format (1.000.000). If a Vietnamese number with dots is passed, it becomes "1000000" which is correct, but "1,5" becomes "15" instead of "1.5". |

### 8.4 `checklist_generator.py` — Checklist Generator

**Strengths:**
- Merges inputs from three sources (risks, clauses, anomalies)
- Deduplication by category:description key
- Priority sorting by severity then due_days
- Smart action text based on risk title keywords

**Issues:**

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 35 | Low | `checklist_generator.py:43-45` | `generate` uses `list` type hints instead of specific types. Should use `list[RiskItem]`, `list[MissingClause]`, `list[Anomaly]` for type safety. |
| 36 | Low | `checklist_generator.py:132-150` | `_risk_action` uses string matching on title substrings. If risk titles change, the action text defaults to a generic message. Consider using the risk category + a mapping. |

### 8.5 `risk_service.py` — Risk Service

**Strengths:**
- Clean orchestration of all risk analysis components
- Separation of `analyze` (full pipeline) and `get_risks`/`get_checklist` (retrieval)
- Proper UUID validation
- Risk persistence with ORM mapping

**Issues:**

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 37 | Medium | `risk_service.py:296-315` | `_persist_risks` always creates new RiskItemORM entries. If `analyze` is called multiple times for the same document, risks accumulate without deduplication or archival of old entries. |
| 38 | Medium | `risk_service.py:177-219` | `get_checklist` re-runs the entire analysis pipeline instead of just generating a checklist from persisted risks. This is wasteful and produces potentially different results than the original analysis. |
| 39 | Low | `risk_service.py:101` | `doc_type = document.document_type or "contract"` defaults to "contract" for unclassified documents. This could apply contract-specific risk rules to non-contract documents. |

### 8.6 `risks.py` — Risks API

**Strengths:**
- Clean REST endpoints
- Proper error mapping

**Issues:**

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 40 | Medium | `risks.py:30-32` | Same hardcoded auth pattern as extraction API — creates new `RiskService()` per request instead of using a singleton or scoped dependency. |
| 41 | Low | `risks.py:61` | `uuid.uuid4()` is generated for each risk item in the response, but these IDs don't match the persisted IDs. The response IDs are ephemeral and can't be used for subsequent API calls. |

---

## Phase 9 — Reports

### 9.1 `report_generator.py` — Report Generator

**Strengths:**
- Three report types (summary, detailed, risk_assessment) with distinct content
- Comprehensive checklist generation (6 automated checks)
- Smart recommendations based on field verification status and risk severity
- Summary trimming removes verbose fields from extracted data

**Issues:**

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 42 | Medium | `report_generator.py:142` | Risk items are sorted by `severity.desc()` which sorts alphabetically (medium > low > high > critical > info). Should use a custom severity order. |
| 43 | Medium | `report_generator.py:306-311` | Checklist status logic for "All fields verified" has a subtle bug: if `unverified` is empty AND `extracted_fields` is also empty, it returns "warning" (because `extracted_fields and not unverified` is falsy). An empty document with no fields should arguably be "pending" not "warning". |
| 44 | Low | `report_generator.py:36-38` | `VALID_REPORT_TYPES` is a module-level set. Adding a new report type requires editing this set AND the `_build_content` method. Consider an enum or registry pattern. |

### 9.2 `markdown_export.py` — Markdown Export

**Strengths:**
- Clean section-based rendering
- Proper table formatting with metadata
- Risk summary section for risk_assessment reports
- Status icons for checklist items
- File size formatting (B, KB, MB, GB)

**Issues:**

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 45 | Medium | `markdown_export.py:108` | Risk summary uses emoji icons (`🔴🟠🟡🔵⚪`) but line 109 only appends the severity name without the icon. The icon variable `icon` is computed but unused — it should be included in the table row. |
| 46 | Low | `markdown_export.py:140` | Checklist uses `✅` and `❌` emojis which may not render correctly in all Markdown viewers. |
| 47 | Low | `markdown_export.py:52-53` | `_render_title` always adds `\n` after the title, but `_render_metadata` also adds `\n` at the end. This creates a double newline between title and metadata. |

### 9.3 `pdf_export.py` — PDF Export

**Strengths:**
- Graceful degradation (weasyprint → HTML fallback)
- Built-in Markdown-to-HTML converter with no external dependencies
- Professional CSS template with headers/footers
- Handles code blocks, tables, lists, inline formatting

**Issues:**

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 48 | Medium | `pdf_export.py:139-151` | List detection: numbered lists use `^\d+\.\s+` but the code doesn't close `<ol>` properly — it falls through to `</ul>` at line 155. Mixed list types in the same document will produce invalid HTML. |
| 49 | Low | `pdf_export.py:171` | `_inline_format` applies `_escape_html` first, then regex substitutions. If the original text contains `**`, the escape won't affect it, but if it contains `<strong>`, it gets escaped to `&lt;strong&gt;` before the bold regex runs. This is correct behavior but worth noting. |
| 50 | Low | `pdf_export.py:65` | The Markdown-to-HTML converter doesn't handle nested lists or blockquotes. For complex report content, this could produce formatting issues. |

### 9.4 `report_service.py` — Report Service

**Strengths:**
- Clean orchestration of generation, export, and storage
- Auto-generates markdown export on report creation
- Supports both markdown and PDF export
- Safe filename sanitization

**Issues:**

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 51 | High | `report_service.py:56-57` | `get_settings()` is called in `__init__`, which means settings are loaded at import time if the service is instantiated globally. This can cause issues in testing and when settings aren't available. |
| 52 | Medium | `report_service.py:155-164` | MinIO upload failure is logged but doesn't propagate — the report is still returned successfully. This means reports could appear to be "generated" but have no stored export. |
| 53 | Low | `report_service.py:227-231` | `_safe_filename` replaces non-alphanumeric chars with `_` then joins with `_`. Multiple consecutive underscores are collapsed to one, but the max_length truncation could cut mid-word. |

### 9.5 `reports.py` — Reports API

**Strengths:**
- Clean REST endpoints with proper status codes (201 for creation)
- Query parameter for export format
- Direct file download with Content-Disposition header

**Issues:**

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 54 | Medium | `reports.py:67` | `set(ReportType)` comparison — `ReportType` is likely a string enum, so this works, but using `ReportType.__members__` or `ReportType._value2member_map_` would be more explicit. |
| 55 | Low | `reports.py:39-41` | Same pattern as other APIs — creates new service instance per request instead of using dependency injection container. |

---

## Cross-Cutting Concerns

### Security
- No authentication beyond placeholder UUIDs
- No rate limiting on extraction/risk analysis endpoints
- No input size limits on document text processing
- PDF export uses custom HTML rendering — potential XSS if document content contains malicious HTML (mitigated by `_escape_html`)

### Performance
- `text.count(keyword)` in classifier is O(n*k) per classification
- Clause detection is O(n*k) per document
- Risk detection compiles regex patterns at module level (good) but penalty context extraction uses string slicing
- Report generation queries DB 3 times (document, fields, risks) — could be optimized with a single join

### Testing
- No existing tests for any Phase 7-9 code
- Tests should mock DB sessions and external services
- Date-dependent tests (expired dates) need `freezegun` or date mocking

---

## Recommendations

### P0 (Must Fix)
1. **#24** — Import `date` at module level in `risk_detector.py` and inject `today` for testability
2. **#45** — Fix unused `icon` variable in `markdown_export.py` risk summary
3. **#48** — Fix `<ol>` vs `</ul>` mismatch in `pdf_export.py` list rendering

### P1 (Should Fix)
4. **#14** — Document the DD/MM/YYYY assumption in `field_normalizer.py` or add locale-aware parsing
5. **#29** — Don't apply all clause templates for unknown document types
6. **#37** — Add deduplication or archival when re-running risk analysis
7. **#42** — Fix severity sort order in `report_generator.py`
8. **#51** — Lazy-load settings in `report_service.py`

### P2 (Nice to Have)
9. **#5** — Add LLM failure metrics/logging
10. **#12** — Remove unused `VND_MONEY_PATTERN`
11. **#32** — Make anomaly norms configurable
12. **#35** — Use specific type hints in `checklist_generator.py`

---

## Test Coverage

The following test files have been created to cover Phase 7-9:

| Test File | Coverage |
|-----------|----------|
| `tests/services/test_classifier.py` | Document classification (Vietnamese + English), empty text, confidence scores, subtypes |
| `tests/services/test_field_validator.py` | Type validation, required fields, date/email/phone format, min/max, patterns |
| `tests/services/test_field_normalizer.py` | Date normalization (multiple formats + Vietnamese), currency (VND/USD), phone (+84), email, address |
| `tests/services/test_risk_detector.py` | High-value amounts, missing payment terms, penalty clauses, short deadlines, missing signatures, low-confidence fields |
| `tests/services/test_clause_detector.py` | Contract clauses, invoice clauses, unknown types, complete vs incomplete documents |
| `tests/services/test_checklist_generator.py` | Risk-to-checklist, clause-to-checklist, anomaly-to-checklist, deduplication, priority sorting |
| `tests/services/test_report_generator.py` | Report content building, summary trimming, risk emphasis, checklist statuses, recommendations |
| `tests/services/test_markdown_export.py` | Title, metadata, overview, key findings, fields, risks, checklist, recommendations, footer |

All tests use `pytest` + `unittest.mock` and run without external services.
