# Phase 7: Field Extraction + Validation — Implementation Plan

## Task
Extract structured fields from documents (contract parties, dates, amounts) and validate against schemas.

## Dependencies
Phase 3 (parsing), Phase 5 (LLM integration)

## Files Created

### 1. `backend/app/services/classifier.py`
- DocumentClassifier class
- classify(text: str) -> ClassificationResult
- Rule-based + keyword classification for 6 types: contract, invoice, report, minutes, regulation, dispatch
- Vietnamese + English keyword matching with weighted scoring
- Pattern boost for structured patterns (dates, amounts, signatures)

### 2. `backend/app/services/field_extractor.py`
- FieldExtractor class
- extract(text: str, schema: dict, document_type: str) -> list[ExtractedFieldValue]
- LLM prompt construction with schema definition
- JSON response parsing
- Rule-based fallback when LLM unavailable

### 3. `backend/app/services/field_validator.py`
- FieldValidator class
- validate(fields, schema) -> ValidationResult
- Type checking: string, number, integer, boolean, date
- Required field checking
- Format validation: date patterns, email regex, phone regex
- Min/max constraints

### 4. `backend/app/services/field_normalizer.py`
- FieldNormalizer class
- normalize(fields) -> list[ExtractedFieldValue]
- Date normalization to ISO 8601 (7 Vietnamese + international formats)
- Currency normalization (VND: "1.500.000 đồng", USD: "$1,500")
- Phone normalization (+84, 84, 0 prefixes)
- Address standardization

### 5. `backend/app/services/extraction_service.py`
- ExtractionService class
- Pipeline: classify → extract → validate → normalize → save
- get_fields(document_id, db)
- update_field(field_id, updates, user_id, db) — manual correction with verification tracking

### 6. `backend/app/api/v1/extraction.py`
- POST /{document_id}/extract — run extraction
- GET /{document_id}/fields — get extracted fields
- PUT /{document_id}/fields/{field_id} — manual correction

### 7. `backend/app/api/schemas/extraction.py`
- ExtractRequest, ExtractedFieldResponse, ExtractionResultResponse, FieldUpdateRequest

## Acceptance Criteria
- [x] Classification works for 6 document types (Vietnamese + English)
- [x] Field extraction produces structured output
- [x] Validation catches type errors and missing required fields
- [x] Dates normalized to ISO 8601
- [x] Manual corrections tracked with verification metadata

## Test Results
- 17 classifier tests
- 25 field validator tests
- 27 field normalizer tests
- **Total: 69 tests passing**
