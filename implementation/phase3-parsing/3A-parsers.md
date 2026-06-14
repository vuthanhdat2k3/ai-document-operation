# Phase 3A: PDF + DOCX + XLSX Parsers — Implementation Plan

## Task
Implement document parsers for PDF (PyMuPDF), DOCX (python-docx), and XLSX (openpyxl).

## Dependencies
Phase 2A (Document model)

## Files to Create

### 1. `backend/app/processing/__init__.py`
- Empty init

### 2. `backend/app/processing/parsers/__init__.py`
- Parser registry
- get_parser(mime_type: str) -> BaseParser

### 3. `backend/app/processing/parsers/base.py`
- BaseParser ABC
- parse(file_path: Path) -> ParseResult
- ParseResult: pages: list[PageResult], metadata: dict, quality_score: float
- PageResult: page_number, text, tables, images, confidence

### 4. `backend/app/processing/parsers/pdf_parser.py`
- PDFParser(BaseParser)
- Uses PyMuPDF (fitz) for text extraction
- Per-page text extraction
- Table detection (basic grid detection)
- Metadata extraction (title, author, pages)
- OCR fallback detection (< 50 chars per page → needs OCR)

### 5. `backend/app/processing/parsers/docx_parser.py`
- DOCXParser(BaseParser)
- Uses python-docx
- Paragraph extraction with style info
- Table extraction
- Header/footer extraction
- Metadata extraction

### 6. `backend/app/processing/parsers/xlsx_parser.py`
- XLSXParser(BaseParser)
- Uses openpyxl
- Sheet-by-sheet extraction
- Cell value extraction
- Merged cell handling
- Formula extraction (as text)

### 7. `backend/app/processing/detector.py`
- detect_file_type(file_path: Path) -> FileType
- Magic byte detection
- Extension fallback

### 8. `backend/app/processing/quality.py`
- QualityScorer class
- score(parsed: ParseResult) -> QualityScore
- Factors: text_density, structure_preservation, encoding_confidence, completeness, language_consistency
- Weighted average → 0.0-1.0

## Acceptance Criteria
- [ ] PDF text extraction works for text-based PDFs
- [ ] DOCX parsing preserves paragraph structure
- [ ] XLSX parsing extracts all sheets and cells
- [ ] Quality scores are between 0.0 and 1.0
- [ ] Parser registry returns correct parser for each MIME type

## Test Requirements
- `tests/processing/test_pdf_parser.py` — PDF extraction tests with sample files
- `tests/processing/test_docx_parser.py` — DOCX parsing tests
- `tests/processing/test_xlsx_parser.py` — XLSX parsing tests
- `tests/processing/test_quality.py` — quality scoring tests
- `tests/processing/test_detector.py` — file type detection tests
