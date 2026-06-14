# Phase 9: Report Export — Implementation Plan

## Task
Generate summary reports and export as Markdown/PDF.

## Dependencies
Phase 7 (extracted fields), Phase 8 (risks)

## Files Created

### 1. `backend/app/services/report_generator.py`
- ReportGenerator class
- 3 report types: summary, detailed, risk_assessment
- Sections: overview, key_findings, extracted_fields, risks, checklist, recommendations
- Content trimming for summary type

### 2. `backend/app/services/markdown_export.py`
- MarkdownExporter class
- Proper Markdown with headers, tables, lists
- Severity icons, confidence indicators
- Vietnamese formatting

### 3. `backend/app/services/pdf_export.py`
- PdfExporter class
- Markdown → HTML conversion
- Professional CSS template (A4, headers, footers, page numbers)
- weasyprint with HTML fallback

### 4. `backend/app/services/report_service.py`
- ReportService class
- create_report, get_report, export_report
- Store exports in MinIO

### 5. `backend/app/api/v1/reports.py`
- POST /documents/{document_id}/report — generate
- GET /{report_id} — metadata
- GET /{report_id}/download?format=markdown|pdf — download

### 6. `backend/app/api/schemas/reports.py`
- ReportCreateRequest, ReportResponse, ReportDownloadResponse

## Acceptance Criteria
- [x] Report includes all sections
- [x] Markdown renders correctly
- [x] PDF has professional formatting
- [x] Reports stored in MinIO

## Test Results
- 24 report generator tests
- 48 markdown export tests
- **Total: 72 tests passing**
