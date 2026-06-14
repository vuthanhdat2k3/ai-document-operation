# RAG Pipeline Design — AI Document Operations Agent

## 1. RAG Overview and Design Philosophy

### Why Pure Vector Search Is Not Enough

Vector similarity search (dense retrieval) alone suffers from several critical limitations in enterprise document operations:

- **Vocabulary mismatch**: Dense embeddings capture semantic similarity but fail when the user query uses different terminology than the document. A query for "termination clause" may miss a section titled "contract cancellation provisions" if the embedding model lacks domain-specific training.
- **Exact match failures**: Numeric values, dates, contract IDs, and legal references require exact matching. Dense retrieval approximates meaning and can return semantically similar but factually incorrect results.
- **Recency bias without metadata**: Vector search has no notion of document freshness, authority, or relevance to a specific project unless metadata filtering is applied.
- **Poor precision on short queries**: Short or ambiguous queries produce broad vector matches that dilute precision.

### Hybrid Retrieval Approach

This system implements a **hybrid retrieval pipeline** combining:

| Method | Strength | Weakness |
|--------|----------|----------|
| Dense (vector) | Semantic understanding, paraphrase handling | Vocabulary mismatch, exact match |
| Sparse (BM25) | Exact term matching, keyword precision | No semantic understanding |
| Metadata filtering | Precise scope narrowing | Requires structured metadata |
| Cross-encoder reranking | High relevance judgment | Slow for large candidate sets |

Each method compensates for the weaknesses of others. Reciprocal Rank Fusion (RRF) merges their ranked lists into a single robust ranking.

### Enterprise RAG vs Simple Chatbot RAG

| Dimension | Simple Chatbot RAG | Enterprise RAG (This System) |
|-----------|-------------------|------------------------------|
| Document volume | < 100 docs | Thousands of documents |
| Document types | Plain text | PDF, Word, Excel, scanned images |
| Language | English only | Vietnamese + English + mixed |
| Accuracy requirement | "Good enough" | Grounded, citable, auditable |
| Hallucination tolerance | Low | Zero — financial/legal consequences |
| Chunking | Fixed-size | Semantic, table-aware, section-aware |
| Retrieval | Single vector search | Hybrid multi-stage pipeline |
| Evaluation | Manual spot-check | Automated metrics (Recall@k, nDCG) |

---

## 2. Full RAG Pipeline

The pipeline consists of 11 sequential stages. Each stage is designed as an independent, testable module.

```
User Query
    │
    ▼
┌─────────────────────┐
│ Stage 1: Query       │
│ Understanding        │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ Stage 2: Query       │
│ Rewrite              │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ Stage 3: Metadata    │
│ Filtering            │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ Stage 4: Hybrid      │
│ Search               │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ Stage 5: RRF Fusion  │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ Stage 6: Cross-Encoder│
│ Reranking            │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ Stage 7: Context     │
│ Compression          │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ Stage 8: Context Pack│
│ Compilation          │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ Stage 9: Grounded    │
│ Answer Generation    │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ Stage 10: Citation   │
│ Generation           │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ Stage 11: Groundedness│
│ Validation           │
└─────────┬───────────┘
          ▼
      Final Response
```

---

### Stage 1: Query Understanding

**Purpose**: Analyze the incoming user query to determine intent, extract key entities, detect language, and assess complexity. This metadata drives all downstream stages.

#### Intent Classification

Classify the query into one of the following intent categories:

| Intent | Description | Example |
|--------|-------------|---------|
| `FACTUAL_LOOKUP` | Specific fact retrieval | "What is the contract value?" |
| `SUMMARIZATION` | Summarize a section or document | "Summarize section 3 of the contract" |
| `COMPARISON` | Compare across documents | "Compare the penalty clauses in Contract A vs B" |
| `EXTRACTION` | Extract structured data | "List all payment milestones" |
| `PROCEDURAL` | How-to or process questions | "What is the approval process for budget changes?" |
| `TEMPORAL` | Time-bound queries | "What deadlines are in Q3 2025?" |
| `EXPLORATORY` | Open-ended exploration | "What are the risks mentioned in this project?" |

Implementation: Use a lightweight classifier (few-shot LLM prompt or fine-tuned small model) to avoid adding latency. Cache classification results for repeated query patterns.

#### Entity Extraction

Extract the following entity types from the query:

- **Document references**: document names, IDs, contract numbers
- **Person/Organization names**: parties mentioned in contracts
- **Dates and date ranges**: "last quarter", "before March 2025"
- **Numeric values**: amounts, percentages, quantities
- **Section references**: "section 3.2", "appendix B", "page 15"

Use regex patterns for structured entities (dates, numbers, section refs) and NER for unstructured entities (names, organizations).

#### Language Detection

Detect the primary language of the query:

```python
def detect_language(query: str) -> LanguageResult:
    """
    Returns: LanguageResult(language, confidence, is_mixed)
    
    Supported languages:
    - Vietnamese (vi)
    - English (en)
    - Mixed (vi-en)
    
    Detection method:
    1. Check for Vietnamese diacritical marks (ă, â, ê, ô, ơ, ư, đ)
    2. Check for Vietnamese word patterns (người, hợp đồng, dự án)
    3. Calculate ratio of Vietnamese vs English tokens
    4. If ratio is between 0.3-0.7, classify as mixed
    """
```

Language detection affects:
- Which tokenizer is used for BM25 search
- Which prompt template is selected for answer generation
- Whether OCR error correction is applied

#### Query Complexity Assessment

Rate query complexity on a scale of 1-3:

| Level | Criteria | Pipeline Behavior |
|-------|----------|-------------------|
| 1 - Simple | Single entity, clear intent, single doc | Skip HyDE, skip decomposition, skip reranking |
| 2 - Moderate | Multiple entities, single doc or cross-doc | Apply HyDE, skip decomposition, apply reranking |
| 3 - Complex | Multi-hop reasoning, comparison, aggregation | Apply HyDE, apply decomposition, apply reranking |

---

### Stage 2: Query Rewrite

**Purpose**: Transform the user's original query into forms that improve retrieval recall and precision.

#### HyDE (Hypothetical Document Embeddings)

Generate a hypothetical document passage that would answer the user's query. Embed this hypothetical document instead of (or in addition to) the raw query.

```
Original query: "What are the penalty clauses in the construction contract?"
Hypothetical document: "The penalty clause states that the contractor shall pay 
a penalty of 0.5% of the total contract value for each day of delay beyond the 
agreed completion date, capped at 10% of the total contract value..."
```

Why HyDE works:
- The hypothetical document contains domain-specific terminology
- Its embedding is closer to actual document passages than the question embedding
- It bridges the question-answer semantic gap

Configuration:
- Model: Same LLM used for generation (e.g., gpt-4o-mini for cost efficiency)
- Temperature: 0.3 (some variation to capture multiple possible answer forms)
- Max tokens: 256 (keep it focused)
- Apply when query complexity >= 2

#### Query Expansion

Generate 2-3 alternative phrasings of the query to improve recall:

```python
def expand_query(query: str, intent: str) -> list[str]:
    """
    Generate alternative phrasings.
    
    Example:
    Input: "hình phạt vi phạm hợp đồng"
    Output: [
        "điều khoản phạt vi phạm hợp đồng",
        "biện pháp chế tài khi phá vỡ hợp đồng",
        "mức bồi thường thiệt hại do vi phạm hợp đồng"
    ]
    """
```

#### Query Decomposition for Complex Questions

Break complex multi-hop queries into sub-questions:

```
Complex query: "Compare the penalty clauses and payment terms between 
Contract A and Contract B"

Decomposed:
  Q1: "What are the penalty clauses in Contract A?"
  Q2: "What are the penalty clauses in Contract B?"
  Q3: "What are the payment terms in Contract A?"
  Q4: "What are the payment terms in Contract B?"
```

Each sub-question is retrieved independently, then results are merged in the context compilation stage.

#### Vietnamese Query Normalization

Apply the following normalizations to Vietnamese queries:

1. **Diacritics correction**: Fix common OCR/input errors (e.g., "đ" vs "d", "ơ" vs "o")
2. **Tone mark normalization**: Ensure proper Unicode composition (NFC normalization)
3. **Abbreviation expansion**: "HĐ" → "hợp đồng", "ĐV" → "đơn vị", "PCT" → "phó chủ tịch"
4. **Legal term standardization**: Map colloquial Vietnamese legal terms to formal terms

---

### Stage 3: Metadata Filtering

**Purpose**: Narrow the search space before retrieval to improve precision and reduce latency.

#### Available Filters

| Filter | Type | Example |
|--------|------|---------|
| `document_id` | Exact match | `"doc_abc123"` |
| `document_type` | Exact match / enum | `"contract"`, `"report"`, `"policy"` |
| `date_range` | Range (ISO 8601) | `{"from": "2024-01-01", "to": "2024-12-31"}` |
| `section` | Exact / prefix match | `"3.2"`, `"appendix_B"` |
| `page` | Range | `{"from": 5, "to": 10}` |
| `project_id` | Exact match | `"proj_xyz"` |
| `language` | Exact match | `"vi"`, `"en"` |
| `access_level` | Exact match | `"public"`, `"internal"`, `"confidential"` |

#### Dynamic Filter Generation

Automatically extract filters from the query understanding stage:

```python
def generate_filters(query_entities: dict, query_intent: str) -> dict:
    """
    Convert extracted entities into metadata filters.
    
    Examples:
    - Entity "Contract ABC-2024" → document_id filter
    - Entity "March 2025" → date_range filter  
    - Entity "section 3.2" → section filter
    - Intent COMPARISON → skip document_id filter (need multiple docs)
    """
```

Filters are applied as pre-filters in the vector database query (Qdrant filter conditions) and as post-filters for BM25 results.

---

### Stage 4: Hybrid Search

**Purpose**: Execute parallel dense and sparse retrieval to maximize recall.

#### Dense Retrieval (Vector Search)

- **Model**: `bge-m3` (BAAI)
- **Dimension**: 1024
- **Distance metric**: Cosine similarity
- **Vector database**: Qdrant
- **When to use**: Always — primary retrieval method for semantic matching

```python
def dense_search(
    query_embedding: list[float],
    filters: dict,
    top_k: int = 50
) -> list[SearchResult]:
    """
    Execute vector similarity search in Qdrant.
    
    Parameters:
    - query_embedding: 1024-dim vector from bge-m3
    - filters: metadata filters from Stage 3
    - top_k: number of candidates to retrieve (50 default for reranking)
    """
```

#### BM25 / Sparse Retrieval

- **Library**: `rank_bm25` or Elasticsearch with BM25 scoring
- **Tokenizer**: Custom Vietnamese tokenizer using `underthesea` or `pyvi`
- **When to use**: Always — complements dense retrieval for exact matches

```python
def sparse_search(
    query: str,
    filters: dict,
    top_k: int = 50
) -> list[SearchResult]:
    """
    BM25 search with Vietnamese tokenization.
    
    Tokenization pipeline:
    1. Lowercase
    2. Vietnamese word segmentation (underthesea.word_tokenize)
    3. Remove stopwords (Vietnamese + English)
    4. Apply BM25 scoring
    """
```

#### When to Use Which Strategy

| Query Type | Dense Weight | Sparse Weight | Rationale |
|------------|-------------|---------------|-----------|
| Semantic/exploratory | 0.7 | 0.3 | Meaning matters more than exact terms |
| Exact lookup (IDs, numbers) | 0.3 | 0.7 | Exact matching is critical |
| Vietnamese legal terms | 0.5 | 0.5 | Both semantics and exact terms matter |
| Mixed language | 0.6 | 0.4 | Dense handles cross-lingual better |

---

### Stage 5: RRF Fusion

**Purpose**: Merge ranked lists from dense and sparse retrieval into a single unified ranking.

#### Reciprocal Rank Fusion Formula

```
RRF_score(d) = Σ 1/(k + rank_i(d))
```

Where:
- `d` is a document chunk
- `rank_i(d)` is the rank of document `d` in the i-th retrieval method's result list
- `k` is a constant (default: 60)
- The sum is over all retrieval methods (dense + sparse)

#### Parameter k=60 Explanation

The constant `k=60` was empirically determined (Cormack et al., 2009) and serves to:
- **Smooth rank differences**: Prevents top-ranked items from dominating excessively
- **Penalize low ranks gently**: A document ranked 100th still contributes meaningfully (1/160 vs 1/61 for rank 1)
- **Balance precision and recall**: Lower k values (e.g., 10) over-emphasize top results; higher k values (e.g., 100) flatten the distribution too much

```python
def reciprocal_rank_fusion(
    ranked_lists: list[list[str]], 
    k: int = 60
) -> list[tuple[str, float]]:
    """
    Fuse multiple ranked lists using RRF.
    
    Parameters:
    - ranked_lists: [[doc_id_1, doc_id_2, ...], [doc_id_3, doc_id_1, ...], ...]
    - k: smoothing constant (default 60)
    
    Returns: [(doc_id, rrf_score), ...] sorted by score descending
    """
    scores = {}
    for ranked_list in ranked_lists:
        for rank, doc_id in enumerate(ranked_list, start=1):
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

#### Score Normalization

After RRF fusion, normalize scores to [0, 1] range for downstream thresholding:

```python
def normalize_scores(scored_docs: list[tuple]) -> list[tuple]:
    """Min-max normalization of RRF scores."""
    if not scored_docs:
        return []
    min_score = min(s for _, s in scored_docs)
    max_score = max(s for _, s in scored_docs)
    range_score = max_score - min_score
    if range_score == 0:
        return [(doc, 1.0) for doc, _ in scored_docs]
    return [(doc, (s - min_score) / range_score) for doc, s in scored_docs]
```

---

### Stage 6: Cross-Encoder Reranking

**Purpose**: Re-score the top candidates from RRF fusion using a cross-encoder model that jointly encodes query and document for higher relevance accuracy.

#### bge-reranker-v2-m3 Configuration

- **Model**: `BAAI/bge-reranker-v2-m3`
- **Max input length**: 512 tokens (query + document concatenated)
- **Batch size**: 32
- **Precision**: fp16 for inference
- **Device**: GPU (CUDA) when available, CPU fallback

```python
from FlagEmbedding import FlagReranker

reranker = FlagReranker('BAAI/bge-reranker-v2-m3', use_fp16=True)

def rerank(
    query: str, 
    documents: list[str], 
    top_k: int = 10
) -> list[tuple[int, float]]:
    """
    Rerank documents by relevance score.
    
    Returns: [(original_index, relevance_score), ...] sorted by score descending
    """
    pairs = [[query, doc] for doc in documents]
    scores = reranker.compute_score(pairs)
    scored = list(enumerate(scores))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
```

#### When to Apply Reranking

| Condition | Apply Reranking? | Reason |
|-----------|-----------------|--------|
| Query complexity = 1 | No | Simple queries benefit less; save latency |
| Candidate count < 5 | No | Too few candidates to benefit from reranking |
| Candidate count >= 5 | Yes | Reranking provides significant precision gain |
| Latency budget exceeded | Skip | Fall back to RRF-only ranking |

#### Reranking Latency Considerations

| Top-K candidates | Latency (GPU) | Latency (CPU) |
|-----------------|---------------|---------------|
| 10 | ~15ms | ~80ms |
| 20 | ~25ms | ~150ms |
| 50 | ~50ms | ~350ms |
| 100 | ~90ms | ~700ms |

Target: Keep reranking under 100ms. Use top_k=50 from RRF, rerank to top_k=10.

---

### Stage 7: Context Compression

**Purpose**: Remove redundant and low-relevance information from retrieved chunks to fit within the token budget.

#### Redundancy Removal

Detect and remove near-duplicate chunks:

```python
def remove_redundancy(
    chunks: list[Chunk], 
    similarity_threshold: float = 0.92
) -> list[Chunk]:
    """
    Remove chunks with high cosine similarity to already-included chunks.
    
    Process:
    1. Sort by relevance score (descending)
    2. For each chunk, compute similarity to all kept chunks
    3. If max similarity > threshold, discard
    """
```

#### Relevance Filtering

Remove chunks below a relevance threshold:

- **Reranked chunks**: Keep if score > 0.3 (model-dependent threshold)
- **Non-reranked chunks**: Keep if RRF normalized score > 0.5
- **Cross-check**: Verify at least 3 chunks survive filtering; if fewer, relax threshold

#### Token Budget Management

```python
TOKEN_BUDGET = {
    "system_prompt": 500,
    "context": 3000,       # Retrieved chunks
    "conversation_history": 500,
    "metadata": 200,
    "response": 1000,
    "total_model_context": 8192,  # Model context window
}

def fit_to_budget(chunks: list[Chunk], max_tokens: int) -> list[Chunk]:
    """
    Greedily add chunks by relevance score until token budget is reached.
    Truncate the last chunk at a sentence boundary if needed.
    """
```

---

### Stage 8: Context Pack Compilation

**Purpose**: Assemble all components into a structured context pack for the LLM.

#### Context Pack Structure

```python
@dataclass
class ContextPack:
    system_prompt: str
    retrieved_context: list[CitationContext]
    conversation_history: list[Message]
    metadata: dict
    token_count: int
```

#### System Prompt

```
You are an AI Document Operations Assistant. Your role is to answer questions 
based ONLY on the provided document context. 

Rules:
1. Only use information from the provided context. Do not use external knowledge.
2. Always cite your sources using the format [source:doc_id:page:chunk_id].
3. If the context does not contain enough information to answer, say 
   "I don't have enough information in the provided documents to answer this question."
4. Respond in the same language as the user's question.
5. For Vietnamese responses, use formal Vietnamese appropriate for business/legal contexts.
```

#### Retrieved Context with Citations

```
--- Retrieved Context ---

[Context 1] (source: contract_abc.pdf, page: 5, chunk: c_012, relevance: 0.92)
The penalty clause states that the contractor shall pay a penalty of 0.5% 
of the total contract value for each day of delay...

[Context 2] (source: contract_abc.pdf, page: 6, chunk: c_015, relevance: 0.87)
The maximum penalty shall not exceed 10% of the total contract value...

[Context 3] (source: policy_def.pdf, page: 12, chunk: c_089, relevance: 0.71)
All contracts must include a penalty clause as per the standard template...
```

#### Conversation History

Include the last N turns (default: 5) of conversation for multi-turn context:

```
--- Conversation History ---
User: What is the total contract value?
Assistant: The total contract value is 50 billion VND [source:contract_abc.pdf:3:c_005].
```

#### Token Counting

```python
import tiktoken

def count_tokens(text: str, model: str = "cl100k_base") -> int:
    """Count tokens using tiktoken for accurate budget management."""
    encoder = tiktoken.get_encoding(model)
    return len(encoder.encode(text))
```

---

### Stage 9: Grounded Answer Generation

**Purpose**: Generate an answer that is strictly grounded in the provided context.

#### Prompt Engineering for Groundedness

The generation prompt enforces grounding through:

1. **Explicit instruction**: "Only use the provided context"
2. **Citation requirement**: "Always cite sources"
3. **Hedging language**: "If unsure, say you don't know"
4. **Context anchoring**: "Refer to specific passages"

```python
GENERATION_PROMPT = """
Based ONLY on the following context, answer the user's question.

{context}

Question: {question}

Instructions:
- Answer using ONLY the information provided in the context above
- Cite each claim using [source:doc_id:page:chunk_id] format
- If the context does not contain sufficient information, state that clearly
- Respond in {language}
- Be precise and factual
"""
```

#### Citation Format

Every factual claim must include a citation in the format:

```
[source:{doc_id}:{page}:{chunk_id}]
```

Examples:
- "The penalty rate is 0.5% per day [source:contract_abc.pdf:5:c_012]."
- "The maximum penalty is capped at 10% [source:contract_abc.pdf:6:c_015]."

#### Handling "I Don't Know" Cases

The LLM must return a structured refusal when:

1. No context chunks are relevant to the query
2. The context contains partial information but not enough for a complete answer
3. The query requires information outside the document scope

Refusal templates:
- Vietnamese: "Tôi không có đủ thông tin trong các tài liệu được cung cấp để trả lời câu hỏi này."
- English: "I don't have enough information in the provided documents to answer this question."

#### Vietnamese Language Support

- Detect query language from Stage 1
- Use Vietnamese prompt template when language is `vi` or `mixed`
- Ensure Vietnamese legal/business terminology is used correctly
- Handle mixed-language documents (Vietnamese body with English terms)

---

### Stage 10: Citation Generation

**Purpose**: Extract, validate, and format citations from the LLM output.

#### Citation Extraction from LLM Output

```python
import re

CITATION_PATTERN = r'\[source:([^:]+):(\d+):([^\]]+)\]'

def extract_citations(text: str) -> list[Citation]:
    """
    Extract all citations from generated text.
    
    Returns: [Citation(doc_id, page, chunk_id, position_in_text), ...]
    """
    matches = re.finditer(CITATION_PATTERN, text)
    return [
        Citation(
            doc_id=m.group(1),
            page=int(m.group(2)),
            chunk_id=m.group(3),
            position=m.start()
        )
        for m in matches
    ]
```

#### Citation Validation Against Source Chunks

```python
def validate_citations(
    citations: list[Citation], 
    source_chunks: list[Chunk]
) -> list[ValidationResult]:
    """
    Verify each citation references a chunk that was actually provided in context.
    
    Checks:
    1. doc_id exists in source chunks
    2. page number matches the source chunk
    3. chunk_id exists in source chunks
    4. The cited claim is supported by the chunk content (semantic check)
    """
```

#### Citation Formatting

Format citations for display to the user:

```python
def format_citation_display(citation: Citation, chunk: Chunk) -> str:
    """
    Human-readable citation format:
    
    [1] contract_abc.pdf, page 5, section 3.2
    """
```

---

### Stage 11: Groundedness Validation

**Purpose**: Verify that the generated answer is fully grounded in the source documents. This is the final quality gate before returning the response.

#### Claim Extraction

Extract individual claims/facts from the generated answer:

```python
def extract_claims(answer: str) -> list[str]:
    """
    Break the answer into individual factual claims.
    
    Example:
    Answer: "The penalty is 0.5% per day, capped at 10%, and applies 
    to all contractors."
    
    Claims:
    1. "The penalty is 0.5% per day"
    2. "The penalty is capped at 10%"
    3. "The penalty applies to all contractors"
    """
```

#### Evidence Matching

For each claim, find supporting evidence in the source chunks:

```python
def match_evidence(
    claims: list[str], 
    source_chunks: list[Chunk]
) -> list[EvidenceMatch]:
    """
    For each claim, compute semantic similarity to all source chunks.
    
    Returns: EvidenceMatch(claim, best_chunk, similarity_score, is_supported)
    """
```

#### Confidence Scoring

Compute an overall groundedness score:

```python
def compute_groundedness(
    evidence_matches: list[EvidenceMatch]
) -> GroundednessResult:
    """
    Groundedness score = (number of supported claims) / (total claims)
    
    Thresholds:
    - score >= 0.9: HIGH confidence — return answer with citations
    - score >= 0.7: MEDIUM confidence — return answer with disclaimer
    - score < 0.7: LOW confidence — return "insufficient information" response
    """
```

#### Hallucination Detection

Flag potential hallucinations:

```python
def detect_hallucinations(
    claims: list[str],
    evidence_matches: list[EvidenceMatch]
) -> list[HallucinationFlag]:
    """
    Flag claims that:
    1. Have no matching evidence (similarity < 0.5)
    2. Contradict source evidence
    3. Contain specific numbers not found in sources
    4. Reference entities not present in context
    """
```

---

## 3. Chunking Strategy

### Recursive Character Splitting

Primary chunking method using LangChain's `RecursiveCharacterTextSplitter`:

```python
CHUNK_CONFIG = {
    "chunk_size": 512,       # tokens
    "chunk_overlap": 50,     # tokens
    "separators": [
        "\n\n",              # Paragraph breaks (highest priority)
        "\n",                # Line breaks
        "。",                # Vietnamese/Chinese sentence endings
        ".",                 # English sentence endings
        " ",                 # Word boundaries
        ""                   # Character fallback
    ],
    "length_function": tiktoken_len,  # Token-based, not character-based
}
```

### Semantic Chunking

For documents where section boundaries matter (legal contracts, technical reports):

```python
def semantic_chunk(document: str) -> list[Chunk]:
    """
    Split at semantic boundaries:
    1. Section headers (numbered: "1.", "1.1", "3.2.1")
    2. Clause boundaries in legal documents
    3. Paragraph boundaries with topic shift detection
    
    Each chunk includes header context prepended:
    "[Section 3.2 - Penalty Clauses] The contractor shall..."
    """
```

### Overlap Strategy

- **Overlap size**: 50 tokens (approximately 1-2 sentences in Vietnamese)
- **Overlap content**: Last N tokens of previous chunk prepended to next chunk
- **Context window**: Each chunk includes the section header regardless of position

### Table-Aware Chunking

Tables are handled differently from text:

```python
def chunk_table(table: TableData) -> list[Chunk]:
    """
    Table chunking rules:
    1. Small tables (< 20 rows): Keep as single chunk
    2. Large tables: Split by row groups, keeping header in every chunk
    3. Each table chunk includes:
       - Table caption/title
       - Column headers
       - Row data
       - Table metadata (source page, table index)
    
    Format:
    [TABLE] Source: contract_abc.pdf, Page 12, Table 3
    | Milestone | Amount (VND) | Due Date |
    |-----------|-------------|----------|
    | Phase 1   | 5,000,000,000 | 2025-03-01 |
    """
```

### Image/Diagram Handling

```python
def handle_image(image: ImageData, ocr_text: str) -> Chunk:
    """
    Image chunking:
    1. Run OCR on the image (Vietnamese + English)
    2. Generate a description using a vision model (if available)
    3. Combine OCR text + description into a chunk
    4. Tag chunk with modality='image'
    
    Format:
    [IMAGE] Source: contract_abc.pdf, Page 8, Figure 2
    Description: Organizational chart showing project structure
    OCR Text: "Ban Giám đốc → Trưởng phòng Kỹ thuật →..."
    """
```

### Chunk Size: 512 Tokens, Overlap: 50 Tokens

Rationale:
- **512 tokens**: Balances context richness with embedding quality. bge-m3 performs optimally on passages of this length. Longer chunks dilute the embedding signal; shorter chunks lose context.
- **50 tokens overlap**: Prevents information loss at chunk boundaries. 50 tokens ≈ 1-2 sentences, sufficient to bridge mid-sentence splits.

---

## 4. Embedding Strategy

### bge-m3 Configuration

```python
from FlagEmbedding import BGEM3FlagModel

model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)

def embed_texts(texts: list[str]) -> dict:
    """
    bge-m3 produces three types of embeddings:
    1. Dense: 1024-dim float vector (semantic)
    2. Sparse: dict of token_id → weight (lexical)
    3. ColBERT: token-level vectors (fine-grained)
    
    This system uses Dense + Sparse for hybrid retrieval.
    """
    output = model.encode(
        texts,
        batch_size=32,
        max_length=512,
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False
    )
    return output
```

### Dense + Sparse Hybrid

- **Dense embeddings**: Stored in Qdrant for vector similarity search
- **Sparse embeddings**: Stored in BM25 index for lexical matching
- bge-m3's native sparse representation outperforms traditional TF-IDF for Vietnamese text

### Batch Embedding

```python
def batch_embed(
    texts: list[str], 
    batch_size: int = 32
) -> list[dict]:
    """
    Process embeddings in batches to:
    1. Maximize GPU utilization
    2. Avoid OOM errors
    3. Enable progress tracking
    
    For 10,000 chunks: ~313 batches, ~5 minutes on A100
    """
```

### Embedding Cache

```python
def get_embedding(text: str) -> dict:
    """
    Cache embeddings in Redis/PostgreSQL to avoid recomputation.
    
    Cache key: SHA256(text)
    TTL: 30 days
    Hit rate expected: ~40% for repeated queries, ~80% for re-indexed docs
    """
```

---

## 5. Vietnamese Language Support

### Tokenization

```python
from underthesea import word_tokenize

def tokenize_vietnamese(text: str) -> list[str]:
    """
    Vietnamese word segmentation using underthesea.
    
    Example:
    Input:  "hợp đồng xây dựng"
    Output: ["hợp đồng", "xây dựng"]
    
    Note: "hợp đồng" is one word (contract), not two separate words.
    Without proper segmentation, BM25 would treat "hợp" and "đồng" separately.
    """
    return word_tokenize(text, format="text").split()
```

### Diacritics Handling

```python
import unicodedata

def normalize_diacritics(text: str) -> str:
    """
    Vietnamese diacritics normalization:
    1. NFC Unicode normalization (compose combining marks)
    2. Fix common OCR errors:
       - "d" ↔ "đ" (check context)
       - "a" vs "ă" vs "â"
       - "o" vs "ô" vs "ơ"
    3. Restore missing diacritics using context (optional, model-based)
    """
    text = unicodedata.normalize('NFC', text)
    # Apply domain-specific corrections
    return text
```

### Mixed Language Documents

Many Vietnamese enterprise documents contain mixed Vietnamese-English content:

```python
def handle_mixed_language(text: str) -> str:
    """
    Strategy for mixed-language documents:
    1. Detect language per sentence (not per document)
    2. Embed Vietnamese and English segments together (bge-m3 is multilingual)
    3. For BM25: tokenize Vietnamese segments with underthesea, English with standard tokenizer
    4. Maintain sentence boundaries during chunking to avoid mixing languages in one chunk
    """
```

### OCR Error Correction

```python
def correct_ocr_errors(text: str) -> str:
    """
    Common OCR errors in Vietnamese documents:
    1. Missing diacritics: "hop dong" → "hợp đồng"
    2. Wrong diacritics: "họp đồng" → "hợp đồng"
    3. Character confusion: "l" → "1", "O" → "0" in numeric contexts
    4. Broken words: "hợp đ ồng" → "hợp đồng"
    
    Correction approach:
    - Dictionary-based lookup for common terms
    - Context-aware correction using language model
    - Preserve uncertain corrections with confidence flag
    """
```

---

## 6. Complex Document Handling

### Table Extraction and Indexing

```python
def extract_tables(pdf_path: str) -> list[TableData]:
    """
    Table extraction pipeline:
    1. Detect table regions using layout analysis (pdfplumber or Unstructured)
    2. Extract cell contents with coordinates
    3. Detect merged cells and reconstruct structure
    4. Convert to structured format (Markdown table or JSON)
    5. Generate chunk with table metadata
    
    Tools: pdfplumber, camelot, or Unstructured.io
    """
```

### Image/Diagram Description

```python
def describe_image(image: bytes) -> str:
    """
    Generate textual description of images/diagrams:
    1. Charts: "Bar chart showing monthly revenue from Jan-Dec 2024..."
    2. Diagrams: "Flowchart depicting the approval process..."
    3. Photos: "Photo of the construction site at Phase 2..."
    4. Signatures: "Signature block for [name] dated [date]"
    
    Model: GPT-4 Vision or equivalent for description generation
    """
```

### Multi-Column Layout

```python
def handle_multicolumn(page: PageData) -> str:
    """
    Multi-column detection and reading order:
    1. Detect column regions using layout analysis
    2. Determine reading order (left-to-right for Vietnamese, top-to-bottom)
    3. Merge columns in correct reading order
    4. Handle column-spanning elements (headers, figures)
    
    Tools: LayoutParser, Unstructured.io, or custom detection
    """
```

### Header/Footer Extraction

```python
def extract_header_footer(page: PageData) -> dict:
    """
    Extract and catalog headers/footers:
    1. Detect repeating text across pages
    2. Extract page numbers, document titles, dates
    3. Remove from main content to avoid duplication
    4. Store as metadata for citation purposes
    
    Returns: {
        "header": "Contract No. ABC-2024",
        "footer": "Page 5 of 20",
        "confidentiality": "CONFIDENTIAL"
    }
    """
```

---

## 7. Retrieval Evaluation Metrics

### Recall@k

```
Recall@k = (number of relevant docs in top-k) / (total relevant docs)
```

- **Target**: Recall@10 >= 0.85
- **Measurement**: Against human-annotated ground truth for a test query set

### Precision@k

```
Precision@k = (number of relevant docs in top-k) / k
```

- **Target**: Precision@5 >= 0.70
- **Trade-off**: Higher precision may reduce recall; tune via reranking

### MRR (Mean Reciprocal Rank)

```
MRR = (1/|Q|) Σ 1/rank_i
```

Where `rank_i` is the rank of the first relevant document for query i.

- **Target**: MRR >= 0.80
- **Significance**: Measures how quickly the user finds relevant information

### nDCG (Normalized Discounted Cumulative Gain)

```
nDCG@k = DCG@k / IDCG@k
DCG@k = Σ (2^rel_i - 1) / log2(i + 1)
```

- **Target**: nDCG@10 >= 0.75
- **Advantage**: Accounts for graded relevance (highly relevant > somewhat relevant)

### Hit Rate

```
Hit Rate = (queries with at least 1 relevant result in top-k) / (total queries)
```

- **Target**: Hit Rate@10 >= 0.95
- **Significance**: Basic sanity check — nearly every query should find something

### Evaluation Pipeline

```python
def evaluate_retrieval(test_queries: list[GroundTruthQuery]) -> dict:
    """
    Run evaluation suite:
    1. Execute full retrieval pipeline on test queries
    2. Compare results against ground truth annotations
    3. Compute all metrics
    4. Generate report with per-query breakdown
    
    Test set: Minimum 100 queries, covering all intent types
    Annotation: 3 human annotators per query, majority vote
    """
```

---

## 8. Anti-Hallucination Measures

### Groundedness Scoring

Every generated answer receives a groundedness score:

```python
@dataclass
class GroundednessResult:
    score: float           # 0.0 to 1.0
    level: str             # HIGH, MEDIUM, LOW
    supported_claims: int  # Number of claims with evidence
    total_claims: int      # Total claims in answer
    flags: list[str]       # Hallucination warning flags
```

### Citation Requirement

**Policy**: Every factual claim MUST have a citation. Claims without citations are treated as potential hallucinations.

Enforcement:
1. Post-generation check: Count claims vs citations
2. If citation_count < claim_count * 0.8, flag for review
3. If citation_count < claim_count * 0.5, reject the answer and regenerate

### Confidence Thresholds

| Confidence Level | Score Range | Action |
|-----------------|-------------|--------|
| HIGH | >= 0.9 | Return answer directly |
| MEDIUM | >= 0.7 | Return answer with disclaimer: "Based on limited context..." |
| LOW | < 0.7 | Return: "I don't have sufficient information..." |

### "I Don't Know" Policy

The system MUST refuse to answer when:

1. **No relevant context**: All retrieved chunks score below relevance threshold
2. **Contradictory evidence**: Source documents contain conflicting information
3. **Out-of-scope query**: Question requires information not in the document corpus
4. **Low groundedness**: Generated answer cannot be verified against sources
5. **Ambiguous reference**: Query references entities that cannot be resolved

Refusal must be honest and specific:
- ❌ Bad: "I cannot answer this question."
- ✅ Good: "The provided documents do not contain information about penalty clauses for subcontractor violations. Please check if there are additional documents that cover this topic."

---

## 9. Implementation Checklist

### Infrastructure
- [ ] Qdrant vector database deployed and configured
- [ ] Redis cache for embeddings and query results
- [ ] PostgreSQL for document metadata and audit logs
- [ ] GPU-enabled inference server for bge-m3 and bge-reranker

### Document Processing
- [ ] PDF parser with table extraction (pdfplumber/Unstructured)
- [ ] OCR pipeline for scanned documents (Vietnamese + English)
- [ ] Multi-column layout detection
- [ ] Header/footer extraction
- [ ] Image description generation

### Chunking
- [ ] Recursive character splitter (512 tokens, 50 overlap)
- [ ] Semantic chunking for legal/structured documents
- [ ] Table-aware chunking
- [ ] Section header context injection
- [ ] Chunk deduplication

### Embedding & Indexing
- [ ] bge-m3 model loaded (dense + sparse)
- [ ] Batch embedding pipeline
- [ ] Embedding cache (Redis)
- [ ] Qdrant collection created with proper schema
- [ ] BM25 index built with Vietnamese tokenizer

### Retrieval Pipeline
- [ ] Query understanding module (intent, entities, language)
- [ ] Query rewrite (HyDE, expansion, decomposition)
- [ ] Metadata filter generation
- [ ] Dense retrieval (Qdrant)
- [ ] Sparse retrieval (BM25)
- [ ] RRF fusion (k=60)
- [ ] Cross-encoder reranking (bge-reranker-v2-m3)
- [ ] Context compression
- [ ] Context pack compilation

### Generation & Validation
- [ ] LLM integration with groundedness prompt
- [ ] Citation extraction and validation
- [ ] Groundedness scoring
- [ ] Hallucination detection
- [ ] "I don't know" policy enforcement

### Vietnamese Support
- [ ] Vietnamese tokenizer (underthesea/pyvi)
- [ ] Diacritics normalization
- [ ] OCR error correction
- [ ] Mixed language handling
- [ ] Vietnamese prompt templates

### Evaluation
- [ ] Test query set (100+ queries)
- [ ] Ground truth annotations
- [ ] Automated metric computation (Recall@k, MRR, nDCG)
- [ ] Latency benchmarking
- [ ] A/B testing framework

### Monitoring
- [ ] Retrieval latency tracking
- [ ] Groundedness score distribution
- [ ] Hallucination rate monitoring
- [ ] User feedback collection
- [ ] Query failure analysis

---

## 10. Acceptance Criteria

### Retrieval Quality
- [ ] **Recall@10 >= 0.85**: At least 85% of relevant documents found in top 10
- [ ] **Precision@5 >= 0.70**: At least 70% of top 5 results are relevant
- [ ] **MRR >= 0.80**: First relevant result appears in top 1.25 positions on average
- [ ] **nDCG@10 >= 0.75**: High-quality ranking with graded relevance
- [ ] **Hit Rate@10 >= 0.95**: Nearly every query returns at least one relevant result

### Answer Quality
- [ ] **Groundedness score >= 0.9** for 90% of answers
- [ ] **Citation accuracy >= 0.95**: 95% of citations reference valid source chunks
- [ ] **Hallucination rate < 2%**: Fewer than 2% of answers contain unsupported claims
- [ ] **"I don't know" accuracy >= 0.90**: System correctly identifies unanswerable queries 90% of the time

### Vietnamese Language
- [ ] **Vietnamese query understanding accuracy >= 0.85**
- [ ] **Diacritics handling**: Zero data loss from diacritics errors
- [ ] **Mixed language support**: Correct handling of Vietnamese-English documents
- [ ] **OCR correction**: 90% accuracy on common OCR error patterns

### Performance
- [ ] **End-to-end latency < 3 seconds** (P95) for simple queries
- [ ] **End-to-end latency < 5 seconds** (P95) for complex queries
- [ ] **Embedding latency < 50ms** per query
- [ ] **Reranking latency < 100ms** for top-50 candidates
- [ ] **Chunking throughput > 100 pages/minute** during indexing

### Robustness
- [ ] **Graceful degradation**: System returns partial results if any stage fails
- [ ] **Fallback paths**: If reranking fails, use RRF-only ranking; if dense search fails, use sparse-only
- [ ] **Input validation**: Reject malformed queries with helpful error messages
- [ ] **Rate limiting**: Handle concurrent requests without degradation

### Observability
- [ ] **Full pipeline tracing**: Every query is traceable through all 11 stages
- [ ] **Metric dashboards**: Real-time monitoring of retrieval and generation quality
- [ ] **Audit log**: Every answer is logged with its context, citations, and groundedness score
- [ ] **Feedback loop**: User corrections are captured and used to improve the system
