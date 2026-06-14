# Phase 8: Risk Detection + Checklist — Implementation Plan

## Task
Identify risks, missing clauses, anomalies and generate actionable checklists.

## Dependencies
Phase 7 (extracted fields)

## Files Created

### 1. `backend/app/services/risk_detector.py`
- RiskDetector class
- 6 rule-based detection methods:
  * High-value amounts (>1 billion VND / >500M VND contracts)
  * Missing payment terms
  * Unusual penalty clauses (>20%)
  * Short deadlines (<7 days)
  * Missing signatures
  * Expired dates
- Categories: financial, legal, temporal, compliance, operational
- Severity levels: critical, high, medium, low, info

### 2. `backend/app/services/clause_detector.py`
- ClauseDetector class
- Template-based detection for contracts (10 clause types) and invoices (7 clause types)
- Keyword matching with Vietnamese support
- Severity assignment based on clause importance

### 3. `backend/app/services/anomaly_detector.py`
- AnomalyDetector class
- Z-score analysis (>2σ from historical norms)
- Per-field anomaly scoring

### 4. `backend/app/services/checklist_generator.py`
- ChecklistGenerator class
- Merge risks + missing clauses + anomalies into prioritized items
- Due-day SLAs based on severity
- Deduplication

### 5. `backend/app/services/risk_service.py`
- RiskService class
- Pipeline: load doc → detect risks → detect missing → detect anomalies → generate checklist → save

### 6. `backend/app/api/v1/risks.py`
- POST /{document_id}/analyze — run risk analysis
- GET /{document_id}/risks — get risk items
- GET /{document_id}/checklist — get checklist

### 7. `backend/app/api/schemas/risks.py`
- RiskItemResponse, ChecklistItemResponse, AnalysisResultResponse

## Acceptance Criteria
- [x] Risk detection identifies financial, legal, temporal categories
- [x] Missing clause detection compares against templates
- [x] Checklist items include description, severity, suggested action
- [x] Vietnamese document support

## Test Results
- 22 risk detector tests
- 14 clause detector tests
- 19 checklist generator tests
- **Total: 55 tests passing**
