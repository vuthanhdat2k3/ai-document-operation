# Phase 5A: RAG Q&A Pipeline — Implementation Plan

## Task
Implement RAG Q&A with query understanding, HyDE, context compilation, grounded answer generation, and citation extraction.

## Dependencies
Phase 4A (chunking, embedding, retrieval)

## Files to Create

### 1. `backend/app/rag/query_understanding.py`
- QueryAnalyzer class
- analyze(query: str) -> QueryAnalysis
- Intent classification (factual, summary, comparison, extraction)
- Entity extraction
- Language detection

### 2. `backend/app/rag/query_rewrite.py`
- QueryRewriter class
- hyde_rewrite(query: str) -> str — Hypothetical Document Embeddings
- expand_query(query: str) -> list[str] — query expansion

### 3. `backend/app/rag/context_compiler.py`
- ContextCompiler class
- compile(query: str, chunks: list[SearchResult]) -> ContextPack
- Token budget management
- Citation formatting: [source:doc_id:page:chunk_id]
- System prompt assembly

### 4. `backend/app/rag/answer_generator.py`
- AnswerGenerator class
- generate(query: str, context: ContextPack) -> Answer
- Grounded answer generation
- Citation extraction
- Groundedness scoring

### 5. `backend/app/rag/groundedness.py`
- GroundednessValidator class
- validate(answer: str, sources: list[str]) -> GroundednessResult
- Claim extraction
- Evidence matching
- Score calculation

### 6. `backend/app/services/qa_service.py`
- QAService class
- ask(document_id: UUID, query: str, session_id: UUID | None) -> QAResult
  - Query understanding
  - HyDE rewrite
  - Hybrid retrieval
  - Reranking
  - Context compilation
  - Answer generation
  - Groundedness validation
  - Save to session

### 7. `backend/app/api/v1/qa.py`
- POST /api/v1/documents/{document_id}/ask
- GET /api/v1/qa/sessions/{session_id}

### 8. `backend/app/api/schemas/qa.py`
- QARequest, QAResponse, QASessionResponse, Citation model

## Acceptance Criteria
- [ ] Q&A returns answers with citations
- [ ] Citations include doc_id, page, chunk_id
- [ ] Groundedness score between 0.0 and 1.0
- [ ] HyDE improves retrieval recall
- [ ] Hallucination flagged when groundedness < 0.5

## Test Requirements
- `tests/rag/test_query_understanding.py`
- `tests/rag/test_query_rewrite.py`
- `tests/rag/test_context_compiler.py`
- `tests/rag/test_answer_generator.py`
- `tests/rag/test_groundedness.py`
- `tests/api/test_qa.py`
