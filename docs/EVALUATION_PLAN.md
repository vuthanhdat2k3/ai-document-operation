# Evaluation Plan — AI Document Operations Agent

## Table of Contents

1. [Evaluation Overview and Philosophy](#1-evaluation-overview-and-philosophy)
2. [Metrics](#2-metrics)
3. [Gold Dataset Specification](#3-gold-dataset-specification)
4. [Evaluation Framework](#4-evaluation-framework)
5. [LLM-as-Judge Design](#5-llm-as-judge-design)
6. [Regression Testing](#6-regression-testing)
7. [A/B Testing Framework](#7-ab-testing-framework)
8. [Cost Tracking](#8-cost-tracking)
9. [Evaluation Schedule](#9-evaluation-schedule)
10. [Implementation Checklist](#10-implementation-checklist)
11. [Acceptance Criteria](#11-acceptance-criteria)

---

## 1. Evaluation Overview and Philosophy

### 1.1 Purpose

This document defines the complete evaluation strategy for the AI Document Operations Agent. The system processes Vietnamese business documents (contracts, invoices, meeting minutes), retrieves relevant information via RAG, generates grounded answers, and orchestrates multi-step document operations through an agentic loop.

### 1.2 Evaluation Philosophy

- **Multi-layered evaluation**: Every component — document processing, retrieval, generation, and agent orchestration — is evaluated independently and as part of the end-to-end pipeline.
- **Quantitative-first**: All evaluation criteria are expressed as numeric metrics with explicit target thresholds. Qualitative human review supplements but never replaces quantitative measurement.
- **Automation by default**: Every metric must be computable in CI. Human evaluation is sampled, scheduled, and reserved for dimensions that resist formalization.
- **Reproducibility**: All evaluations run against versioned gold datasets with fixed random seeds. Results are stored as structured artifacts, not prose.
- **Cost-awareness**: Token and latency budgets are first-class evaluation dimensions, not afterthoughts.

### 1.3 Evaluation Layers

| Layer | Scope | Primary Responsibility |
|-------|-------|----------------------|
| Document Processing | OCR, classification, field extraction, risk detection | Accuracy and completeness of structured output |
| Retrieval | Vector search, hybrid search, reranking | Relevance and ranking quality of retrieved chunks |
| Generation | LLM answer synthesis, citation, summarization | Faithfulness, relevance, and groundedness of output |
| Agent | Tool selection, orchestration, loop control | Task completion and efficiency of multi-step workflows |
| System | End-to-end latency, cost, cache, throughput | Operational performance under production load |

### 1.4 Target Environment

- Model providers: OpenAI GPT-4o / GPT-4o-mini, Anthropic Claude 3.5 Sonnet (configurable)
- Embedding model: text-embedding-3-small (1536 dimensions)
- Vector database: Qdrant
- Document store: PostgreSQL + MinIO
- Evaluation runner: Python 3.11+, pytest, custom evaluation harness

---

## 2. Metrics

### 2.1 Document Processing Metrics

#### 2.1.1 Document Classification Accuracy

| Attribute | Value |
|-----------|-------|
| **Definition** | Fraction of documents correctly assigned to their type (contract, invoice, meeting_minutes, other) |
| **Formula** | `Accuracy = Correct Predictions / Total Documents` |
| **Target Threshold** | > 95% |
| **Measurement Method** | Compare predicted label against gold label in the gold dataset. Compute per-class and macro-averaged accuracy. Run on every evaluation cycle. |

**Implementation notes:**
- Multi-class single-label classification (4 classes).
- Confusion matrix computed per class to identify systematic misclassifications.
- Report both overall accuracy and per-class precision/recall/F1.

#### 2.1.2 Field Extraction F1

| Attribute | Value |
|-----------|-------|
| **Definition** | Token-level F1 score for extracted named fields from documents |
| **Formula** | `F1 = 2 * (Precision * Recall) / (Precision + Recall)` where Precision = correctly extracted tokens / total extracted tokens; Recall = correctly extracted tokens / total gold tokens |
| **Target Threshold** | > 0.85 |
| **Measurement Method** | For each document, compare extracted fields against gold annotations using exact-match and fuzzy-match (Levenshtein distance ≤ 2) scoring. Report macro F1 across all field types. |

**Implementation notes:**
- Field types include: party names, dates, amounts, contract terms, invoice line items, action items.
- Exact match and fuzzy match scores reported separately.
- Partial credit for correct field identification with minor value differences.

#### 2.1.3 OCR Character Error Rate

| Attribute | Value |
|-----------|-------|
| **Definition** | Rate of character-level errors introduced by the OCR pipeline |
| **Formula** | `CER = (S + D + I) / N` where S = substitutions, D = deletions, I = insertions, N = total characters in ground truth |
| **Target Threshold** | < 5% |
| **Measurement Method** | Compute character-level edit distance between OCR output and manually verified ground truth text. Sample 50 documents per document type for manual verification. |

**Implementation notes:**
- Vietnamese diacritical characters weighted equally with ASCII characters.
- Whitespace normalization applied before comparison (collapse multiple spaces, trim).
- Report CER per document type and overall.

### 2.2 Retrieval Metrics

#### 2.2.1 Recall@k

| Attribute | Value |
|-----------|-------|
| **Definition** | Fraction of relevant documents retrieved within the top-k results |
| **Formula** | `Recall@k = |Relevant ∩ Retrieved_top_k| / |Relevant|` |
| **Target Threshold** | Recall@5 > 0.7, Recall@10 > 0.8, Recall@20 > 0.9 |
| **Measurement Method** | For each query in the Q&A gold dataset, retrieve top-k chunks and check overlap with gold-relevant chunk IDs. Average across all queries. |

#### 2.2.2 Precision@k

| Attribute | Value |
|-----------|-------|
| **Definition** | Fraction of retrieved documents in top-k that are relevant |
| **Formula** | `Precision@k = |Relevant ∩ Retrieved_top_k| / k` |
| **Target Threshold** | Precision@5 > 0.6, Precision@10 > 0.5 |
| **Measurement Method** | For each query, compute the fraction of relevant chunks among top-k. Average across all queries. |

#### 2.2.3 Mean Reciprocal Rank (MRR)

| Attribute | Value |
|-----------|-------|
| **Definition** | Average reciprocal rank of the first relevant result |
| **Formula** | `MRR = (1/|Q|) * Σ (1 / rank_i)` where rank_i is the rank of the first relevant result for query i |
| **Target Threshold** | > 0.7 |
| **Measurement Method** | For each query, find the position of the first relevant result. If no relevant result in top-20, reciprocal rank = 0. Average across all queries. |

#### 2.2.4 Normalized Discounted Cumulative Gain (nDCG)

| Attribute | Value |
|-----------|-------|
| **Definition** | Measures ranking quality with graded relevance, normalized against ideal ranking |
| **Formula** | `nDCG@k = DCG@k / IDCG@k` where `DCG@k = Σ (rel_i / log2(i+1))` for i=1..k |
| **Target Threshold** | > 0.75 |
| **Measurement Method** | Assign graded relevance labels (0=irrelevant, 1=partially relevant, 2=highly relevant) to each chunk per query. Compute nDCG@10. Average across all queries. |

#### 2.2.5 Hit Rate

| Attribute | Value |
|-----------|-------|
| **Definition** | Fraction of queries where at least one relevant document appears in top-k |
| **Formula** | `Hit Rate@k = |Queries with at least 1 hit in top-k| / |Total Queries|` |
| **Target Threshold** | > 0.9 |
| **Measurement Method** | For each query, check if any relevant chunk appears in top-20. Report Hit Rate@5, @10, @20. |

### 2.3 Generation Metrics

#### 2.3.1 Answer Relevance

| Attribute | Value |
|-----------|-------|
| **Definition** | How well the generated answer addresses the user's question |
| **Formula** | Average score on a 1–5 Likert scale rated by LLM judge |
| **Target Threshold** | > 4.0 |
| **Measurement Method** | LLM-as-judge rates each (question, answer) pair. Human evaluation on a sampled subset (10%) for calibration. |

**Rating rubric:**
- 5: Directly and completely answers the question
- 4: Mostly answers with minor omissions
- 3: Partially answers, some relevant content
- 2: Tangentially related, does not directly answer
- 1: Off-topic or completely irrelevant

#### 2.3.2 Context Relevance

| Attribute | Value |
|-----------|-------|
| **Definition** | How relevant the retrieved context is to the question |
| **Formula** | Average score on a 1–5 Likert scale rated by LLM judge |
| **Target Threshold** | > 3.5 |
| **Measurement Method** | LLM-as-judge rates each (question, retrieved_contexts) pair. Measures whether retrieval returned useful material. |

**Rating rubric:**
- 5: All retrieved context is directly relevant and sufficient
- 4: Most context is relevant, minor noise
- 3: Some context is relevant, notable noise or gaps
- 2: Mostly irrelevant with some tangential relevance
- 1: Completely irrelevant context

#### 2.3.3 Groundedness

| Attribute | Value |
|-----------|-------|
| **Definition** | Degree to which the generated answer is supported by the retrieved context (faithfulness) |
| **Formula** | `Groundedness = Supported Claims / Total Claims` (0–1 scale) |
| **Target Threshold** | > 0.8 |
| **Measurement Method** | LLM judge decomposes the answer into atomic claims, then verifies each claim against the context. Reports fraction of supported claims. |

**Decomposition approach:**
1. Extract atomic factual claims from the answer
2. For each claim, check if it is directly stated, inferable, or unsupported by the context
3. Groundedness = (directly_stated + inferable) / total_claims

#### 2.3.4 Citation Accuracy

| Attribute | Value |
|-----------|-------|
| **Definition** | Fraction of citations in the generated answer that correctly reference the source document and are factually supported |
| **Formula** | `Citation Accuracy = Correct Citations / Total Citations` |
| **Target Threshold** | > 0.9 |
| **Measurement Method** | For each citation in the answer, verify: (1) the cited document ID exists in retrieved context, (2) the cited content is present in the cited document. Automated check with LLM verification for semantic match. |

### 2.4 Agent Metrics

#### 2.4.1 Tool Success Rate

| Attribute | Value |
|-----------|-------|
| **Definition** | Fraction of tool invocations that complete without error |
| **Formula** | `Tool Success Rate = Successful Tool Calls / Total Tool Calls` |
| **Target Threshold** | > 0.95 |
| **Measurement Method** | Instrument all tool calls with success/failure tracking. Log error categories (timeout, invalid input, API error, permission denied). Aggregate per tool and overall. |

#### 2.4.2 Agent Task Success Rate

| Attribute | Value |
|-----------|-------|
| **Definition** | Fraction of agent tasks that reach a correct final state |
| **Formula** | `Task Success Rate = Successfully Completed Tasks / Total Tasks` |
| **Target Threshold** | > 0.85 |
| **Measurement Method** | Define expected outcomes for each task type in the gold dataset. Compare agent final state against expected outcome. Automated for structured tasks, LLM-judged for open-ended tasks. |

#### 2.4.3 Agent Loop Rate

| Attribute | Value |
|-----------|-------|
| **Definition** | Fraction of agent executions that enter non-productive loops (repeating the same tool call with identical arguments) |
| **Formula** | `Loop Rate = Looped Executions / Total Executions` |
| **Target Threshold** | < 5% |
| **Measurement Method** | Detect consecutive identical tool calls (same tool name + same arguments hash). Flag if 3+ consecutive identical calls occur. |

#### 2.4.4 Max Iterations Hit Rate

| Attribute | Value |
|-----------|-------|
| **Definition** | Fraction of agent executions that hit the maximum iteration limit without reaching a final state |
| **Formula** | `Max Iterations Rate = Tasks Hitting Limit / Total Tasks` |
| **Target Threshold** | < 10% |
| **Measurement Method** | Track iteration count per task execution. Flag tasks that reach `MAX_ITERATIONS` (default: 15) without a final answer. Analyze root causes for flagged tasks. |

### 2.5 System Metrics

#### 2.5.1 Latency (P50, P95, P99)

| Attribute | Value |
|-----------|-------|
| **Definition** | End-to-end response time from user query to final answer delivery |
| **Formula** | Percentile distribution of `response_time_ms` across all requests |
| **Target Threshold** | P50 < 2s, P95 < 5s, P99 < 10s |
| **Measurement Method** | Instrument the request handler with high-resolution timestamps. Record wall-clock time including LLM calls, retrieval, and post-processing. Store in time-series format for percentile computation. |

**Sub-latency breakdown (also tracked):**
- Retrieval latency: time to query vector DB + rerank
- LLM latency: time for each LLM call (classification, generation, tool reasoning)
- Processing latency: OCR, field extraction, preprocessing

#### 2.5.2 Cost per Request

| Attribute | Value |
|-----------|-------|
| **Definition** | Total LLM API cost for a single end-to-end request |
| **Formula** | `Cost = Σ (input_tokens * input_price + output_tokens * output_price)` across all LLM calls in the request |
| **Target Threshold** | < $0.05 per request (average) |
| **Measurement Method** | Token counting at each LLM API call. Cost computed using provider-specific pricing tables. Stored per request for aggregation. |

#### 2.5.3 Cache Hit Rate

| Attribute | Value |
|-----------|-------|
| **Definition** | Fraction of requests served from cache (embedding cache, retrieval cache, response cache) |
| **Formula** | `Cache Hit Rate = Cache Hits / (Cache Hits + Cache Misses)` |
| **Target Threshold** | > 30% |
| **Measurement Method** | Instrument cache layers with hit/miss counters. Report per cache layer (embedding, retrieval, response) and aggregate. |

---

## 3. Gold Dataset Specification

### 3.1 Dataset Composition

| Dataset | Count | Source | Purpose |
|---------|-------|--------|---------|
| Contracts (Vietnamese) | 20 | Real anonymized Vietnamese business contracts | Classification, field extraction, risk detection, Q&A |
| Invoices (Vietnamese) | 20 | Real anonymized Vietnamese invoices (hóa đơn) | Classification, field extraction, Q&A |
| Meeting Minutes (Vietnamese) | 20 | Real anonymized Vietnamese meeting minutes (biên bản họp) | Classification, field extraction, action item extraction, Q&A |
| Q&A Pairs | 100 | Manually authored, document-grounded | Retrieval and generation evaluation |
| Field Extraction Labels | 100 | Manual annotation on the 60 documents | Field extraction evaluation |
| Risk Detection Cases | 50 | Curated from contracts + expert annotation | Risk detection evaluation |

### 3.2 Document Sourcing Guidelines

- All documents must be real or synthetically generated to match real-world distributions.
- Documents must be anonymized: replace all real party names, tax codes, addresses, and personal information with synthetic equivalents while preserving structural and semantic integrity.
- Document age distribution: 50% from 2023–2024, 50% from 2020–2022.
- Document complexity: 30% simple (few clauses, standard terms), 40% medium, 30% complex (many clauses, unusual terms, amendments).
- File formats: PDF (scanned and digital), DOCX, PNG/JPG images.

### 3.3 Q&A Pair Specification

Each Q&A pair contains:

```json
{
  "id": "qa_001",
  "question": "Tổng giá trị hợp đồng là bao nhiêu?",
  "answer": "Tổng giá trị hợp đồng là 500.000.000 VNĐ (năm trăm triệu đồng), đã bao gồm thuế VAT.",
  "question_type": "factual",
  "difficulty": "easy",
  "relevant_doc_ids": ["contract_003"],
  "relevant_chunk_ids": ["chunk_003_012", "chunk_003_015"],
  "answer_requires_multi_hop": false,
  "expected_citations": [
    {"doc_id": "contract_003", "chunk_id": "chunk_003_012", "quote": "Tổng giá trị hợp đồng: 500.000.000 VNĐ"}
  ],
  "language": "vi"
}
```

**Question type distribution:**
- Factual (40%): Direct fact lookup from a single document
- Comparative (15%): Compare information across documents
- Aggregation (15%): Summarize or aggregate across multiple documents
- Temporal (15%): Time-based queries (deadlines, durations, schedules)
- Multi-hop (15%): Require reasoning across multiple document sections

**Difficulty distribution:**
- Easy (30%): Single document, direct answer
- Medium (40%): May require inference or minor aggregation
- Hard (30%): Multi-hop, cross-document, or requires domain knowledge

### 3.4 Field Extraction Label Specification

Each extraction label:

```json
{
  "id": "ext_001",
  "doc_id": "contract_003",
  "fields": [
    {
      "field_name": "contract_value",
      "field_type": "currency",
      "value": "500000000",
      "currency": "VND",
      "text_span": "Tổng giá trị hợp đồng: 500.000.000 VNĐ",
      "start_offset": 45,
      "end_offset": 75
    },
    {
      "field_name": "effective_date",
      "field_type": "date",
      "value": "2024-01-15",
      "text_span": "ngày 15 tháng 01 năm 2024",
      "start_offset": 102,
      "end_offset": 130
    },
    {
      "field_name": "party_a",
      "field_type": "organization",
      "value": "Công ty TNHH ABC",
      "text_span": "Công ty TNHH ABC",
      "start_offset": 10,
      "end_offset": 27
    }
  ]
}
```

**Field types for contracts:**
- party_a, party_b (organization)
- contract_value (currency)
- effective_date, expiration_date (date)
- contract_type (enum: mua_bán, dịch_vụ, thuê, hợp_tác, other)
- governing_law (text)
- penalty_clause (text)

**Field types for invoices:**
- invoice_number (text)
- invoice_date (date)
- seller_name, buyer_name (organization)
- seller_tax_code, buyer_tax_code (text)
- total_amount, tax_amount, pre_tax_amount (currency)
- line_items (array of objects)

**Field types for meeting minutes:**
- meeting_date (date)
- attendees (array of names)
- agenda_items (array of text)
- decisions (array of text)
- action_items (array of {assignee, task, deadline})

### 3.5 Risk Detection Case Specification

```json
{
  "id": "risk_001",
  "doc_id": "contract_007",
  "risks": [
    {
      "risk_type": "unlimited_liability",
      "severity": "high",
      "description": "Điều khoản 5.2 quy định trách nhiệm bồi thường không giới hạn cho bên B.",
      "text_span": "Bên B chịu trách nhiệm bồi thường toàn bộ thiệt hại...",
      "clause_reference": "5.2",
      "recommendation": "Đề xuất giới hạn trách nhiệm bồi thường bằng tổng giá trị hợp đồng."
    }
  ]
}
```

**Risk types:**
- unlimited_liability (high)
- auto_renewal_without_notice (medium)
- ambiguous_termination (medium)
- missing_penalty_clause (medium)
- unfavorable_payment_terms (medium)
- ip_ownership_ambiguity (high)
- non_compliant_clause (high)
- missing_governing_law (low)

### 3.6 Dataset Format Specification

**File structure:**
```
gold_dataset/
├── v1.0/
│   ├── metadata.json
│   ├── documents/
│   │   ├── contracts/
│   │   │   ├── contract_001.pdf
│   │   │   ├── contract_001.json          # structured metadata
│   │   │   └── ...
│   │   ├── invoices/
│   │   └── meeting_minutes/
│   ├── labels/
│   │   ├── classification_labels.json
│   │   ├── extraction_labels.json
│   │   ├── risk_labels.json
│   │   └── qa_pairs.json
│   └── README.md
```

**metadata.json:**
```json
{
  "version": "1.0.0",
  "created_at": "2024-06-01T00:00:00Z",
  "num_documents": 60,
  "num_qa_pairs": 100,
  "num_extraction_labels": 100,
  "num_risk_cases": 50,
  "annotation_guidelines_version": "1.0",
  "annotators": ["annotator_1", "annotator_2", "annotator_3"],
  "inter_annotator_agreement": 0.87
}
```

### 3.7 Annotation Guidelines

**General rules:**
1. All annotations must be performed by native Vietnamese speakers with domain knowledge in business/legal documents.
2. Each document is annotated by at least 2 annotators. Disagreements are resolved by a third senior annotator.
3. Annotations must reference exact text spans with character-level offsets.
4. Dates normalized to ISO 8601 format (YYYY-MM-DD).
5. Currency values normalized to numeric VND (no dots, no currency symbol).

**Inter-annotator agreement targets:**
- Classification: Cohen's κ > 0.9
- Field extraction: F1 between annotators > 0.9
- Risk detection: F1 between annotators > 0.8
- Q&A relevance labels: Cohen's κ > 0.7

### 3.8 Dataset Versioning

- Semantic versioning: MAJOR.MINOR.PATCH
- MAJOR: Breaking changes to schema or annotation guidelines
- MINOR: New documents or labels added
- PATCH: Corrections to existing labels
- All versions stored in `gold_dataset/v{version}/`
- Version history tracked in `gold_dataset/CHANGELOG.md`
- Evaluation results tagged with dataset version used

---

## 4. Evaluation Framework

### 4.1 Automated Metrics (Code-Based)

All metrics in Sections 2.1–2.5 are implemented as Python functions in `eval/metrics/`:

```
eval/
├── metrics/
│   ├── document_processing.py    # accuracy, F1, CER
│   ├── retrieval.py              # recall@k, precision@k, MRR, nDCG, hit_rate
│   ├── generation.py             # answer_relevance, context_relevance, groundedness, citation_accuracy
│   ├── agent.py                  # tool_success_rate, task_success_rate, loop_rate, max_iterations_rate
│   └── system.py                 # latency, cost, cache_hit_rate
├── runners/
│   ├── run_document_processing.py
│   ├── run_retrieval.py
│   ├── run_generation.py
│   ├── run_agent.py
│   └── run_system.py
├── judges/
│   ├── llm_judge.py
│   ├── judge_prompts.py
│   └── calibration.py
├── datasets/
│   └── gold_dataset/
├── reports/
│   └── generate_report.py
└── conftest.py
```

**Automated evaluation pipeline:**

1. Load gold dataset version
2. Run system under evaluation against gold queries/documents
3. Collect raw outputs (predictions, retrieved contexts, generated answers, agent traces)
4. Compute metrics against gold labels
5. Generate structured report (JSON + HTML)
6. Compare against baselines and thresholds
7. Emit pass/fail status for CI

### 4.2 LLM-as-Judge (for Generation Quality)

Metrics requiring subjective judgment (answer relevance, context relevance, groundedness) use LLM-as-judge evaluation. See Section 5 for full design.

### 4.3 Human Evaluation (Sampled)

**Sampling strategy:**
- Sample 10% of evaluation cases for human review
- Stratified sampling: ensure coverage across document types, question types, and difficulty levels
- Priority sampling: always include cases where LLM judge and automated metrics disagree

**Human evaluation tasks:**
1. Rate answer relevance (1–5) for sampled Q&A pairs
2. Verify groundedness assessments for flagged cases
3. Review risk detection false positives and false negatives
4. Validate field extraction edge cases

**Annotator requirements:**
- Native Vietnamese speakers
- Minimum 2 annotators per case
- Annotators must complete calibration session (20 practice cases) before production evaluation
- Maximum 50 evaluations per annotator per session to prevent fatigue

### 4.4 Evaluation Pipeline Design

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Gold Dataset    │────▶│  System Under    │────▶│  Raw Outputs    │
│  (versioned)     │     │  Evaluation      │     │  (predictions,  │
│                  │     │                  │     │   traces, logs) │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                                                          ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  CI Gate /       │◀───│  Report          │◀───│  Metric         │
│  Acceptance      │     │  Generator       │     │  Computation    │
│  Check           │     │  (JSON + HTML)   │     │  Engine         │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

**Pipeline configuration (eval_config.yaml):**
```yaml
dataset_version: "1.0.0"
metrics:
  document_processing:
    enabled: true
    classification_accuracy: { threshold: 0.95 }
    field_extraction_f1: { threshold: 0.85 }
    ocr_cer: { threshold: 0.05 }
  retrieval:
    enabled: true
    recall_at_k: [5, 10, 20]
    precision_at_k: [5, 10]
    mrr: { threshold: 0.7 }
    ndcg: { threshold: 0.75 }
    hit_rate: { threshold: 0.9 }
  generation:
    enabled: true
    judge_model: "gpt-4o"
    answer_relevance: { threshold: 4.0 }
    context_relevance: { threshold: 3.5 }
    groundedness: { threshold: 0.8 }
    citation_accuracy: { threshold: 0.9 }
  agent:
    enabled: true
    tool_success_rate: { threshold: 0.95 }
    task_success_rate: { threshold: 0.85 }
    loop_rate: { threshold: 0.05 }
    max_iterations_rate: { threshold: 0.10 }
  system:
    enabled: true
    latency_p50_ms: { threshold: 2000 }
    latency_p95_ms: { threshold: 5000 }
    latency_p99_ms: { threshold: 10000 }
    cost_per_request_usd: { threshold: 0.05 }
    cache_hit_rate: { threshold: 0.30 }
```

---

## 5. LLM-as-Judge Design

### 5.1 Judge Model Selection

| Criterion | Choice | Rationale |
|-----------|--------|-----------|
| Primary judge | GPT-4o | Strong multilingual capability, reliable structured output, good Vietnamese understanding |
| Secondary judge | Claude 3.5 Sonnet | Cross-validation for inter-rater reliability |
| Fallback | GPT-4o-mini | Cost-effective for low-stakes metrics (cache hit, basic relevance) |

**Cost budget for judging:** Max $0.02 per evaluation case (judge calls). Budget enforced via token counting.

### 5.2 Rubric Definitions

#### Answer Relevance Rubric

```
Score 5 - Directly and completely answers the question.
  - All aspects of the question are addressed
  - No significant omissions
  - Answer is specific and actionable

Score 4 - Mostly answers the question with minor omissions.
  - Core question is answered
  - One minor aspect missing or slightly imprecise
  - Answer is still useful

Score 3 - Partially answers the question.
  - Addresses some aspects but misses key parts
  - May be too vague or tangential
  - Provides some useful information

Score 2 - Tangentially related but does not directly answer.
  - Contains some relevant keywords or concepts
  - Does not address the actual question
  - May be answering a different question

Score 1 - Completely irrelevant or wrong.
  - No connection to the question
  - Fabricated or hallucinated information
  - Completely unhelpful
```

#### Groundedness Rubric

```
For each atomic claim in the answer, classify as:
  - DIRECTLY_STATED: Claim is explicitly stated in the context (1.0)
  - INFERABLE: Claim can be logically inferred from the context (0.8)
  - UNSUPPORTED: Claim has no basis in the context (0.0)

Groundedness = Σ(claim_scores) / num_claims
```

### 5.3 Scoring Prompts

**Answer Relevance Judge Prompt (Vietnamese-optimized):**

```
You are evaluating the relevance of an AI-generated answer to a user question about a Vietnamese business document.

## Question
{question}

## Generated Answer
{answer}

## Rating Criteria
5 - Directly and completely answers the question
4 - Mostly answers with minor omissions
3 - Partially answers, some relevant content
2 - Tangentially related, does not directly answer
1 - Off-topic or completely irrelevant

## Instructions
1. Read the question carefully. Identify what specific information is being requested.
2. Read the answer. Determine what information it provides.
3. Rate the answer's relevance on a 1-5 scale.
4. Provide a brief justification (1-2 sentences).

Respond in JSON format:
{"score": <1-5>, "justification": "<brief explanation>"}
```

**Groundedness Judge Prompt:**

```
You are evaluating whether an AI-generated answer is grounded in the provided context (i.e., all claims are supported by the context).

## Context
{context}

## Question
{question}

## Generated Answer
{answer}

## Instructions
1. Decompose the answer into individual atomic claims.
2. For each claim, classify it as:
   - DIRECTLY_STATED: explicitly in the context
   - INFERABLE: logically derivable from the context
   - UNSUPPORTED: not supported by the context
3. Compute groundedness = (DIRECTLY_STATED + INFERABLE * 0.8) / total_claims

Respond in JSON format:
{
  "claims": [
    {"claim": "<text>", "classification": "DIRECTLY_STATED|INFERABLE|UNSUPPORTED", "evidence": "<relevant context excerpt>"}
  ],
  "groundedness_score": <0.0-1.0>
}
```

### 5.4 Inter-Rater Reliability

**Calibration process:**
1. Select 30 calibration cases spanning all score levels
2. Run both GPT-4o and Claude 3.5 Sonnet as independent judges
3. Compute Pearson correlation between judge scores
4. Target: r > 0.8 for continuous scores, Cohen's κ > 0.7 for categorical scores
5. If target not met, refine rubrics and re-calibrate

**Ongoing monitoring:**
- On every evaluation run, sample 10% of cases and run through both judges
- Flag cases where judges disagree by > 2 points (1–5 scale) or > 0.3 (0–1 scale)
- Disagreement cases sent to human adjudication
- Track agreement rate over time; trigger recalibration if it drops below threshold

---

## 6. Regression Testing

### 6.1 Baseline Establishment

**Baseline generation process:**
1. Run the full evaluation suite against the current production system
2. Record all metric values as the v1.0 baseline
3. Store in `eval/baselines/baseline_v1.0.json`
4. Baselines are immutable once established; new baselines created as new versions

**Baseline artifact format:**
```json
{
  "baseline_version": "1.0.0",
  "created_at": "2024-06-01T00:00:00Z",
  "dataset_version": "1.0.0",
  "system_config": { "model": "gpt-4o-mini", "embedding": "text-embedding-3-small" },
  "metrics": {
    "classification_accuracy": 0.93,
    "field_extraction_f1": 0.82,
    "ocr_cer": 0.045,
    "recall_at_10": 0.78,
    "precision_at_5": 0.58,
    "mrr": 0.68,
    "ndcg_at_10": 0.73,
    "hit_rate_at_20": 0.92,
    "answer_relevance": 3.8,
    "context_relevance": 3.4,
    "groundedness": 0.77,
    "citation_accuracy": 0.88,
    "tool_success_rate": 0.96,
    "task_success_rate": 0.82,
    "loop_rate": 0.03,
    "max_iterations_rate": 0.08,
    "latency_p50_ms": 1800,
    "latency_p95_ms": 4200,
    "latency_p99_ms": 8500,
    "cost_per_request_usd": 0.042,
    "cache_hit_rate": 0.35
  }
}
```

### 6.2 Regression Detection Thresholds

| Metric Category | Regression Threshold | Action |
|----------------|---------------------|--------|
| Document Processing | Drop > 2% absolute | Block merge, investigate |
| Retrieval | Drop > 3% absolute | Block merge, investigate |
| Generation | Drop > 0.2 points (1–5 scale) or > 0.05 (0–1 scale) | Block merge, investigate |
| Agent | Drop > 2% absolute (success rates) or increase > 2% (failure rates) | Block merge, investigate |
| System Latency | Increase > 20% from baseline | Warning, investigate |
| System Cost | Increase > 25% from baseline | Warning, investigate |

**Regression detection logic:**
```
for each metric:
    delta = current_value - baseline_value
    if is_higher_better(metric):
        if delta < -regression_threshold(metric):
            FAIL("Regression detected: {metric} dropped by {abs(delta)}")
    else:
        if delta > regression_threshold(metric):
            FAIL("Regression detected: {metric} increased by {delta}")
```

### 6.3 CI Integration

**GitHub Actions workflow (`eval_regression.yml`):**

```yaml
name: Evaluation Regression Check
on:
  pull_request:
    paths:
      - 'src/**'
      - 'eval/**'
      - 'prompts/**'

jobs:
  eval-regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run fast evaluation
        run: python -m eval.runners.run_all --mode fast --dataset gold_dataset/v1.0
      - name: Check regressions
        run: python -m eval.regression_check --baseline eval/baselines/latest.json --results eval/reports/latest.json
      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: eval-report
          path: eval/reports/
```

**Fast mode (per-commit):**
- Skips LLM-as-judge (expensive)
- Runs automated metrics only (classification, extraction, retrieval, agent, system)
- Completes in < 5 minutes
- Uses a reduced dataset subset (20% of gold data)

**Full mode (daily):**
- Runs all metrics including LLM-as-judge
- Uses complete gold dataset
- Generates comprehensive HTML report

---

## 7. A/B Testing Framework

### 7.1 Model Comparison

**Purpose:** Compare different LLM backends for generation quality, cost, and latency.

**Experimental design:**
- Independent variable: Model (e.g., GPT-4o vs GPT-4o-mini vs Claude 3.5 Sonnet)
- Dependent variables: All generation metrics + cost + latency
- Control: Current production model
- Sample size: Full gold dataset (100 Q&A pairs)

**Comparison matrix:**

| Model | Expected Strengths | Expected Weaknesses |
|-------|-------------------|---------------------|
| GPT-4o | Best quality, strong Vietnamese | Highest cost |
| GPT-4o-mini | Low cost, fast | Lower quality on complex tasks |
| Claude 3.5 Sonnet | Strong reasoning, good Vietnamese | Moderate cost |

**Decision criteria:**
- Primary: Generation quality metrics (answer relevance, groundedness)
- Secondary: Cost per request, latency P95
- Tertiary: Agent task success rate
- Trade-off: Accept ≤ 0.1 point quality drop for ≥ 30% cost reduction

### 7.2 Chunking Strategy Comparison

**Purpose:** Optimize document chunking for retrieval quality.

**Strategies to compare:**

| Strategy | Description |
|----------|-------------|
| Fixed-size | 512 tokens, 50 token overlap |
| Fixed-size (large) | 1024 tokens, 100 token overlap |
| Paragraph-based | Split on paragraph boundaries, max 512 tokens |
| Semantic | Split on semantic boundaries using sentence embeddings |
| Section-based | Split on document section headers (contracts: clauses, invoices: line items) |

**Evaluation:** Compare retrieval metrics (Recall@10, MRR, nDCG) across strategies.

### 7.3 Retrieval Strategy Comparison

**Purpose:** Optimize the retrieval pipeline.

**Strategies to compare:**

| Strategy | Description |
|----------|-------------|
| Dense only | Vector similarity search with embedding model |
| Sparse only | BM25 keyword search |
| Hybrid (RRF) | Reciprocal Rank Fusion of dense + sparse |
| Hybrid (weighted) | Linear combination of dense + sparse scores |
| Dense + Rerank | Dense retrieval followed by cross-encoder reranking |
| Hybrid + Rerank | Hybrid retrieval followed by cross-encoder reranking |

**Evaluation:** Compare retrieval metrics + latency overhead of each strategy.

### 7.4 A/B Test Execution

```python
# eval/ab_testing/run_ab_test.py
class ABTest:
    def __init__(self, name: str, variants: list[str]):
        self.name = name
        self.variants = variants
        self.results = {v: [] for v in variants}

    def run(self, dataset, pipeline_factory):
        for variant in self.variants:
            pipeline = pipeline_factory(variant)
            for case in dataset:
                result = pipeline.execute(case.query)
                self.results[variant].append({
                    "case_id": case.id,
                    "metrics": compute_metrics(result, case.gold),
                    "latency_ms": result.latency_ms,
                    "cost_usd": result.cost_usd
                })

    def report(self):
        # Generate statistical comparison report
        # Include p-values for significance testing (paired t-test or Wilcoxon)
        pass
```

**Statistical significance:**
- Use paired t-test for normally distributed metrics
- Use Wilcoxon signed-rank test for non-normal distributions
- Significance level: α = 0.05
- Report effect size (Cohen's d) alongside p-values

---

## 8. Cost Tracking

### 8.1 Token Counting per Request

**Instrumentation:**

```python
# src/monitoring/token_tracker.py
@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int
    model: str
    operation: str  # "classification", "generation", "tool_reasoning", "judge"

class TokenTracker:
    def record(self, usage: TokenUsage):
        """Record token usage for a single LLM call."""
        self._store.append(usage)

    def get_request_total(self, request_id: str) -> dict:
        """Aggregate all token usage for a request."""
        usages = self._get_by_request(request_id)
        return {
            "total_input_tokens": sum(u.input_tokens for u in usages),
            "total_output_tokens": sum(u.output_tokens for u in usages),
            "by_operation": group_by(usages, key=lambda u: u.operation),
            "by_model": group_by(usages, key=lambda u: u.model),
            "num_llm_calls": len(usages)
        }
```

### 8.2 Model Cost Calculation

**Pricing table (configurable):**

```json
{
  "models": {
    "gpt-4o": {
      "input_price_per_1k": 0.0025,
      "output_price_per_1k": 0.01,
      "currency": "USD"
    },
    "gpt-4o-mini": {
      "input_price_per_1k": 0.00015,
      "output_price_per_1k": 0.0006,
      "currency": "USD"
    },
    "claude-3-5-sonnet": {
      "input_price_per_1k": 0.003,
      "output_price_per_1k": 0.015,
      "currency": "USD"
    },
    "text-embedding-3-small": {
      "input_price_per_1k": 0.00002,
      "output_price_per_1k": 0.0,
      "currency": "USD"
    }
  }
}
```

**Cost computation:**
```python
def compute_cost(usage: TokenUsage, pricing: dict) -> float:
    model_pricing = pricing["models"][usage.model]
    input_cost = (usage.input_tokens / 1000) * model_pricing["input_price_per_1k"]
    output_cost = (usage.output_tokens / 1000) * model_pricing["output_price_per_1k"]
    return input_cost + output_cost
```

### 8.3 Storage Cost Tracking

**Components tracked:**
- Vector database storage (Qdrant): estimated by collection size × price per GB/month
- Document storage (MinIO): actual bucket size × price per GB/month
- PostgreSQL: row count estimation for metadata tables
- Cache storage: Redis memory usage

**Monthly cost estimate formula:**
```
Monthly_Storage_Cost = VectorDB_GB * $0.50 + ObjectStorage_GB * $0.023 + PostgreSQL_GB * $0.10 + Cache_GB * $0.15
```

### 8.4 Cost Budget Alerts

| Alert Level | Threshold | Action |
|------------|-----------|--------|
| Info | Cost/request > $0.03 | Log warning in evaluation report |
| Warning | Cost/request > $0.04 | Notify team via Slack |
| Critical | Cost/request > $0.05 | Block deployment, require optimization |
| Emergency | Daily total > $50 | Automatic circuit breaker, halt non-essential LLM calls |

**Budget monitoring dashboard metrics:**
- Total cost per day, week, month
- Cost per request (moving average, P50, P95)
- Cost breakdown by operation (classification, generation, tool reasoning, judging)
- Cost breakdown by model
- Cost trend (7-day rolling)

---

## 9. Evaluation Schedule

### 9.1 Per-Commit (Fast Metrics)

| Metric | Included | Rationale |
|--------|----------|-----------|
| Classification Accuracy | Yes | Fast, automated, critical |
| Field Extraction F1 | Yes | Fast, automated, critical |
| OCR CER | No | Requires full document processing pipeline |
| Retrieval Metrics | Yes (reduced set) | Fast subset available |
| Generation Metrics | No | Requires LLM judge (expensive) |
| Agent Metrics | Yes | Fast, automated |
| System Latency | Yes | Fast measurement |
| Cost per Request | Yes | Token counting is cheap |
| Cache Hit Rate | Yes | Counter-based, instant |

**Trigger:** Every pull request to `main`
**Duration target:** < 5 minutes
**Dataset:** 20% stratified sample of gold dataset
**Gate:** Must pass all thresholds to merge

### 9.2 Daily (Full Evaluation)

| Metric | Included | Rationale |
|--------|----------|-----------|
| All document processing metrics | Yes | Full pipeline |
| All retrieval metrics | Yes | Full retrieval pipeline |
| All generation metrics (LLM judge) | Yes | Complete generation evaluation |
| All agent metrics | Yes | Full agent traces |
| All system metrics | Yes | Full system measurement |

**Trigger:** Scheduled cron job (daily at 02:00 UTC) or manual
**Duration target:** < 30 minutes
**Dataset:** Full gold dataset (100%)
**Gate:** Regression check against baseline; results posted to Slack channel

### 9.3 Weekly (Human Evaluation)

| Task | Included | Rationale |
|------|----------|-----------|
| Human rating of sampled answers | Yes | Quality assurance |
| Inter-rater reliability check | Yes | Judge calibration |
| Edge case review | Yes | Catch systematic errors |
| Cost trend analysis | Yes | Budget planning |
| A/B test result review | Yes | Decision making |

**Trigger:** Scheduled (every Monday at 10:00 local time)
**Duration:** 2–4 hours (annotator time)
**Sample:** 10% stratified from daily evaluation results
**Output:** Human evaluation report, calibration metrics, action items

### 9.4 Evaluation Calendar

```
Monday:    Full daily eval + Human evaluation + A/B test review
Tuesday:   Full daily eval
Wednesday: Full daily eval + Inter-rater check
Thursday:  Full daily eval
Friday:    Full daily eval + Weekly summary report generation
Saturday:  Full daily eval (automated only)
Sunday:    Full daily eval (automated only)
```

---

## 10. Implementation Checklist

### Phase 1: Foundation (Week 1–2)

- [ ] Set up `eval/` directory structure
- [ ] Implement metric computation functions in `eval/metrics/`
  - [ ] `document_processing.py`: classification_accuracy, field_extraction_f1, ocr_cer
  - [ ] `retrieval.py`: recall_at_k, precision_at_k, mrr, ndcg, hit_rate
  - [ ] `generation.py`: answer_relevance, context_relevance, groundedness, citation_accuracy
  - [ ] `agent.py`: tool_success_rate, task_success_rate, loop_rate, max_iterations_rate
  - [ ] `system.py`: latency_percentiles, cost_per_request, cache_hit_rate
- [ ] Write unit tests for all metric functions
- [ ] Create `eval/conftest.py` with shared fixtures

### Phase 2: Gold Dataset (Week 2–3)

- [ ] Source and anonymize 20 contracts
- [ ] Source and anonymize 20 invoices
- [ ] Source and anonymize 20 meeting minutes
- [ ] Create annotation guidelines document
- [ ] Recruit and train 3 annotators
- [ ] Annotate classification labels (60 documents)
- [ ] Annotate field extraction labels (100 labels across 60 documents)
- [ ] Author 100 Q&A pairs with difficulty and type tags
- [ ] Annotate 50 risk detection cases
- [ ] Compute inter-annotator agreement
- [ ] Create `metadata.json` and version the dataset as v1.0.0

### Phase 3: Evaluation Pipeline (Week 3–4)

- [ ] Implement evaluation runners
  - [ ] `run_document_processing.py`
  - [ ] `run_retrieval.py`
  - [ ] `run_generation.py`
  - [ ] `run_agent.py`
  - [ ] `run_system.py`
  - [ ] `run_all.py` (orchestrator)
- [ ] Implement report generator (`generate_report.py`)
  - [ ] JSON output for programmatic consumption
  - [ ] HTML output for human review
- [ ] Create `eval_config.yaml` with all thresholds
- [ ] Implement baseline comparison logic

### Phase 4: LLM-as-Judge (Week 4–5)

- [ ] Implement judge prompts in `eval/judges/judge_prompts.py`
- [ ] Implement `llm_judge.py` with GPT-4o primary judge
- [ ] Implement secondary judge with Claude 3.5 Sonnet
- [ ] Run calibration on 30-case calibration set
- [ ] Implement inter-rater reliability computation
- [ ] Implement cost tracking for judge calls

### Phase 5: CI/CD Integration (Week 5–6)

- [ ] Create GitHub Actions workflow for per-commit fast eval
- [ ] Create GitHub Actions workflow for daily full eval
- [ ] Implement regression check script
- [ ] Establish initial baseline from production system
- [ ] Set up Slack notifications for evaluation results
- [ ] Set up cost budget alerts

### Phase 6: A/B Testing and Monitoring (Week 6–7)

- [ ] Implement A/B testing framework
- [ ] Run initial model comparison (GPT-4o vs GPT-4o-mini vs Claude 3.5 Sonnet)
- [ ] Run chunking strategy comparison
- [ ] Run retrieval strategy comparison
- [ ] Set up cost monitoring dashboard
- [ ] Document A/B test results and decisions

### Phase 7: Human Evaluation Process (Week 7–8)

- [ ] Set up human evaluation interface (annotation tool or spreadsheet)
- [ ] Create calibration materials (20 practice cases)
- [ ] Run first weekly human evaluation session
- [ ] Calibrate human ratings against LLM judge
- [ ] Establish ongoing human evaluation schedule
- [ ] Document human evaluation SOP

---

## 11. Acceptance Criteria

### 11.1 System-Level Acceptance

The system is considered production-ready when **ALL** of the following criteria are met:

| # | Criterion | Threshold | Measurement |
|---|-----------|-----------|-------------|
| AC-1 | Document Classification Accuracy | ≥ 95% | Automated, full gold dataset |
| AC-2 | Field Extraction F1 | ≥ 0.85 | Automated, full gold dataset |
| AC-3 | OCR Character Error Rate | ≤ 5% | Automated, 50-sample verification |
| AC-4 | Recall@10 | ≥ 0.8 | Automated, full Q&A dataset |
| AC-5 | Precision@5 | ≥ 0.6 | Automated, full Q&A dataset |
| AC-6 | MRR | ≥ 0.7 | Automated, full Q&A dataset |
| AC-7 | nDCG@10 | ≥ 0.75 | Automated, full Q&A dataset |
| AC-8 | Hit Rate@20 | ≥ 0.9 | Automated, full Q&A dataset |
| AC-9 | Answer Relevance | ≥ 4.0 / 5.0 | LLM-as-judge, full Q&A dataset |
| AC-10 | Context Relevance | ≥ 3.5 / 5.0 | LLM-as-judge, full Q&A dataset |
| AC-11 | Groundedness | ≥ 0.8 | LLM-as-judge, full Q&A dataset |
| AC-12 | Citation Accuracy | ≥ 0.9 | Automated + LLM verification |
| AC-13 | Tool Success Rate | ≥ 0.95 | Automated, agent trace logs |
| AC-14 | Agent Task Success Rate | ≥ 0.85 | Automated + LLM-judged tasks |
| AC-15 | Agent Loop Rate | ≤ 5% | Automated, agent trace logs |
| AC-16 | Max Iterations Hit Rate | ≤ 10% | Automated, agent trace logs |
| AC-17 | Latency P50 | ≤ 2s | Automated, system metrics |
| AC-18 | Latency P95 | ≤ 5s | Automated, system metrics |
| AC-19 | Latency P99 | ≤ 10s | Automated, system metrics |
| AC-20 | Cost per Request | ≤ $0.05 | Automated, token tracking |
| AC-21 | Cache Hit Rate | ≥ 30% | Automated, cache counters |

### 11.2 Process-Level Acceptance

| # | Criterion | Requirement |
|---|-----------|-------------|
| PC-1 | Gold dataset complete | All 60 documents annotated, 100 Q&A pairs authored, 50 risk cases labeled |
| PC-2 | Inter-annotator agreement | Cohen's κ > 0.8 for classification, F1 > 0.85 for extraction |
| PC-3 | Evaluation pipeline operational | All runners produce valid reports in < 30 min |
| PC-4 | CI integration working | Per-commit evaluation gates functional |
| PC-5 | Baseline established | v1.0 baseline recorded with all metric values |
| PC-6 | LLM judge calibrated | Inter-rater r > 0.8 between primary and secondary judges |
| PC-7 | Human evaluation process | First weekly session completed with 2+ annotators |
| PC-8 | Cost tracking operational | Per-request cost recorded and aggregated daily |
| PC-9 | Regression detection | Demonstrated that regression check correctly blocks a simulated regression |
| PC-10 | Documentation complete | This evaluation plan reviewed and approved by the team |

### 11.3 Acceptance Gate Logic

```
IF all AC-1 through AC-21 are met
  AND all PC-1 through PC-10 are met
THEN
  System is APPROVED for production deployment
ELSE
  System is NOT APPROVED
  Generate gap analysis report
  Identify highest-priority improvements
  Schedule re-evaluation after improvements
```

### 11.4 Conditional Acceptance

If the system meets 90% of acceptance criteria (19/21 ACs), a conditional approval may be granted with:
- Documented remediation plan for failing criteria
- Monitoring and alerting for failing metrics in production
- Scheduled re-evaluation within 2 weeks
- Sign-off from engineering lead and product owner

---

*Document version: 1.0.0*
*Last updated: 2024-06-01*
*Owner: AI Document Operations Agent Team*
*Review cycle: Monthly or on significant system changes*
