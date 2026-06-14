# Phase 4A: Chunking + Embedding + Vector Store — Implementation Plan

## Task
Implement text chunking, bge-m3 embedding, Qdrant indexing, and hybrid search.

## Dependencies
Phase 3A (parsers), Phase 1C (Qdrant client)

## Files to Create

### 1. `backend/app/rag/__init__.py`
- Empty init

### 2. `backend/app/rag/chunker.py`
- TextChunker class
- recursive_split(text: str, chunk_size: int = 512, overlap: int = 64) -> list[Chunk]
- semantic_split(text: str, threshold: float = 0.5) -> list[Chunk]
- Chunk dataclass: text, start_offset, end_offset, page, metadata

### 3. `backend/app/rag/embedder.py`
- EmbeddingPipeline class
- embed_texts(texts: list[str]) -> EmbeddingResult
- Uses sentence-transformers with BAAI/bge-m3
- Returns dense vectors (1024-dim) and sparse vectors
- Batch processing

### 4. `backend/app/rag/retriever.py`
- HybridRetriever class
- search(query: str, filters: dict, top_k: int) -> list[SearchResult]
- Dense search: cosine similarity on dense vectors
- Sparse search: dot product on sparse vectors
- RRF fusion

### 5. `backend/app/rag/fusion.py`
- rrf_fusion(results: list[list[SearchResult]], k: int = 60) -> list[SearchResult]
- Reciprocal Rank Fusion formula

### 6. `backend/app/rag/reranker.py`
- Reranker class
- rerank(query: str, documents: list[str], top_k: int) -> list[ScoredResult]
- Uses bge-reranker-v2-m3

### 7. Update `backend/app/vector/collections.py`
- create_chunks_collection() with dense + sparse vector configs

### 8. `backend/app/services/indexing_service.py`
- IndexingService class
- index_document(document_id: UUID) -> None
  - Load parsed chunks
  - Generate embeddings
  - Upsert to Qdrant
  - Update chunk records with embedding IDs

## Acceptance Criteria
- [ ] Chunking produces chunks within size limits
- [ ] Embeddings have correct dimensionality (1024)
- [ ] Qdrant collection created with dense + sparse vectors
- [ ] Hybrid search returns relevant results
- [ ] RRF fusion correctly combines rankings
- [ ] Reranking improves result quality

## Test Requirements
- `tests/rag/test_chunker.py` — chunking strategy tests
- `tests/rag/test_embedder.py` — embedding generation tests (mocked model)
- `tests/rag/test_retriever.py` — hybrid search tests
- `tests/rag/test_fusion.py` — RRF fusion tests
- `tests/rag/test_reranker.py` — reranking tests
