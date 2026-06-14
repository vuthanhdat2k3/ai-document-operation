# AI Document Operations Agent — Harness Design

## Table of Contents

1. [Agent Harness Overview](#1-agent-harness-overview)
2. [Environment (E)](#2-environment-e)
3. [Tool Registry (T)](#3-tool-registry-t)
4. [Context Pipeline (C)](#4-context-pipeline-c)
5. [State (S)](#5-state-s)
6. [Logic / Orchestration (L)](#6-logic--orchestration-l)
7. [Validation (V)](#7-validation-v)
8. [Agent Safety](#8-agent-safety)
9. [Agent Task Types](#9-agent-task-types)
10. [Implementation Checklist](#10-implementation-checklist)
11. [Acceptance Criteria](#11-acceptance-criteria)

---

## 1. Agent Harness Overview

### 1.1 Agent Formula

The agent harness is formally defined as:

```
H = (E, T, C, S, L, V)
```

Each component is a distinct concern that composes into a fully autonomous document operations agent. The separation ensures testability, substitutability, and independent evolution of each layer.

### 1.2 Component Responsibilities

| Component | Symbol | Responsibility |
|-----------|--------|----------------|
| **Environment** | E | Runtime configuration, model selection, resource limits, API keys, feature flags |
| **Tool Registry** | T | Registration, discovery, schema validation, sandboxed execution of all tools |
| **Context Pipeline** | C | Context window management, compression, pack compilation, token budget allocation |
| **State** | S | Typed state schema, transitions, persistence, checkpointing, rollback |
| **Logic / Orchestration** | L | LangGraph graph definition, node routing, edge conditions, loop detection, fallbacks |
| **Validation** | V | Input/output validation, tool call validation, groundedness checks, citation verification |

### 1.3 Data Flow

```
User Request
     │
     ▼
┌─────────┐     ┌──────────┐     ┌─────────────────┐
│ E: Env  │────▶│ S: State │────▶│ L: Orchestration │
└─────────┘     └──────────┘     └────────┬────────┘
     │                                     │
     ▼                                     ▼
┌─────────┐     ┌──────────┐     ┌─────────────────┐
│ T: Tools│◀───▶│ C: Ctx   │◀───│ V: Validation    │
└─────────┘     └──────────┘     └─────────────────┘
     │
     ▼
Agent Response
```

### 1.4 Design Principles

- **Typed contracts** — Every interface between components is defined via Pydantic models.
- **Idempotency** — Mutating tool calls carry an idempotency key to prevent duplicate side-effects.
- **Observability** — Every node emits structured logs and OpenTelemetry spans.
- **Graceful degradation** — Each node has a fallback path when a sub-step fails.
- **Human override** — Any node can pause execution and request human approval.

---

## 2. Environment (E)

### 2.1 Runtime Environment

```python
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
import os


class RuntimeEnvironment(str, Enum):
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"


class EnvironmentConfig(BaseModel):
    env: RuntimeEnvironment = RuntimeEnvironment.LOCAL
    debug: bool = False
    log_level: str = "INFO"
    data_dir: str = "/data"
    temp_dir: str = "/tmp/agent"
```

### 2.2 Available Models

```python
class ModelRole(str, Enum):
    PRIMARY = "primary"           # Main reasoning model
    FAST = "fast"                 # Lightweight model for classification / routing
    EXTRACTION = "extraction"     # Fine-tuned extraction model
    EMBEDDING = "embedding"       # Embedding model for vector search


class ModelConfig(BaseModel):
    primary: str = "gpt-4o"
    fast: str = "gpt-4o-mini"
    extraction: str = "gpt-4o"
    embedding: str = "text-embedding-3-large"
    temperature: float = 0.0
    max_output_tokens: int = 4096
    request_timeout_seconds: int = 120
```

### 2.3 Configuration Sources

Configuration is loaded in ascending priority:

1. Default values (hardcoded)
2. `config/agent.yaml` (project config)
3. Environment variables (`AGENT_*` prefix)
4. Runtime overrides (API request headers)

```python
class AgentConfig(BaseModel):
    environment: EnvironmentConfig
    models: ModelConfig
    tools: ToolConfig
    context: ContextConfig
    safety: SafetyConfig
    validation: ValidationConfig
```

### 2.4 Resource Limits

```python
class ResourceLimits(BaseModel):
    max_tokens_per_request: int = 128_000
    max_tool_calls_per_turn: int = 20
    max_tool_calls_total: int = 100
    max_concurrent_tool_calls: int = 5
    max_iterations: int = 10
    max_wall_clock_seconds: int = 300
    max_cost_usd: float = 5.00
    max_context_tokens: int = 120_000
    max_state_size_bytes: int = 1_000_000
```

### 2.5 Feature Flags

```python
class FeatureFlags(BaseModel):
    enable_risk_detection: bool = True
    enable_auto_checklist: bool = True
    enable_report_generation: bool = True
    enable_human_in_the_loop: bool = True
    enable_reranking: bool = True
    enable_caching: bool = True
    enable_telemetry: bool = True
```

---

## 3. Tool Registry (T)

### 3.1 Tool Registration Mechanism

Every tool is registered via a decorator that captures its schema, timeout, retry policy, and sandbox configuration.

```python
from typing import Any, Callable
from pydantic import BaseModel
from enum import Enum


class ToolCategory(str, Enum):
    PARSING = "parsing"
    CLASSIFICATION = "classification"
    EXTRACTION = "extraction"
    SEARCH = "search"
    RISK = "risk"
    TASK = "task"
    REPORT = "report"
    UTILITY = "utility"


class RetryPolicy(BaseModel):
    max_retries: int = 2
    backoff_base_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    retryable_errors: list[str] = ["TimeoutError", "RateLimitError"]


class ToolMeta(BaseModel):
    name: str
    description: str
    category: ToolCategory
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    timeout_seconds: int = 60
    retry_policy: RetryPolicy = RetryPolicy()
    requires_approval: bool = False
    idempotent: bool = True
    side_effects: bool = False
    sandbox: bool = True
```

### 3.2 Tool Discovery

```python
class ToolRegistry:
    """Central registry for all agent tools."""

    def __init__(self):
        self._tools: dict[str, tuple[ToolMeta, Callable]] = {}

    def register(self, meta: ToolMeta):
        def decorator(fn: Callable) -> Callable:
            self._tools[meta.name] = (meta, fn)
            return fn
        return decorator

    def get(self, name: str) -> tuple[ToolMeta, Callable]:
        if name not in self._tools:
            raise ToolNotFoundError(f"Tool '{name}' not registered")
        return self._tools[name]

    def list_tools(self, category: ToolCategory | None = None) -> list[ToolMeta]:
        metas = [m for m, _ in self._tools.values()]
        if category:
            metas = [m for m in metas if m.category == category]
        return metas

    def to_llm_tools(self) -> list[dict]:
        """Export tool schemas in OpenAI function-calling format."""
        ...

registry = ToolRegistry()
```

### 3.3 Tool Schema Validation

All tool inputs and outputs are validated against their Pydantic schemas before and after execution.

```python
def validate_tool_input(meta: ToolMeta, raw_input: dict) -> BaseModel:
    try:
        return meta.input_schema(**raw_input)
    except ValidationError as e:
        raise ToolInputValidationError(meta.name, e)


def validate_tool_output(meta: ToolMeta, raw_output: Any) -> BaseModel:
    try:
        return meta.output_schema.model_validate(raw_output)
    except ValidationError as e:
        raise ToolOutputValidationError(meta.name, e)
```

### 3.4 Tool Execution Sandbox

Each tool executes inside a sandboxed context with enforced timeouts, resource limits, and error isolation.

```python
import asyncio
from contextlib import asynccontextmanager


@asynccontextmanager
async def tool_sandbox(meta: ToolMeta):
    """Execute a tool within resource and time boundaries."""
    start = asyncio.get_event_loop().time()
    try:
        yield
    except asyncio.TimeoutError:
        raise ToolTimeoutError(meta.name, meta.timeout_seconds)
    except Exception as e:
        raise ToolExecutionError(meta.name, str(e))
    finally:
        elapsed = asyncio.get_event_loop().time() - start
        emit_tool_telemetry(meta.name, elapsed)
```

### 3.5 Complete Tool Inventory

#### 3.5.1 `parse_document(file_id)`

```python
class ParseDocumentInput(BaseModel):
    file_id: str = Field(..., description="Unique document file identifier")
    ocr_enabled: bool = Field(False, description="Enable OCR for scanned documents")
    language: str = Field("en", description="Primary document language")


class ParseDocumentOutput(BaseModel):
    document_id: str
    raw_text: str
    page_count: int
    mime_type: str
    metadata: dict
    parse_warnings: list[str]
```

- **Category**: PARSING
- **Timeout**: 120s
- **Side effects**: None
- **Idempotent**: Yes

#### 3.5.2 `classify_document(document_id)`

```python
class ClassifyDocumentInput(BaseModel):
    document_id: str
    candidate_categories: list[str] | None = None


class ClassifyDocumentOutput(BaseModel):
    document_id: str
    category: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    sub_category: str | None = None
    reasoning: str
```

- **Category**: CLASSIFICATION
- **Timeout**: 30s
- **Side effects**: None
- **Idempotent**: Yes

#### 3.5.3 `extract_fields(document_id, schema_name)`

```python
class ExtractFieldsInput(BaseModel):
    document_id: str
    schema_name: str = Field(..., description="Name of the extraction schema to apply")
    strict: bool = Field(True, description="Fail if required fields are missing")


class FieldValue(BaseModel):
    field_name: str
    value: Any
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_location: str | None = None


class ExtractFieldsOutput(BaseModel):
    document_id: str
    schema_name: str
    fields: list[FieldValue]
    extraction_warnings: list[str]
```

- **Category**: EXTRACTION
- **Timeout**: 60s
- **Side effects**: None
- **Idempotent**: Yes

#### 3.5.4 `search_documents(query, filters, top_k)`

```python
class SearchFilters(BaseModel):
    categories: list[str] | None = None
    date_range: tuple[str, str] | None = None
    authors: list[str] | None = None
    tags: list[str] | None = None


class SearchDocumentsInput(BaseModel):
    query: str
    filters: SearchFilters = SearchFilters()
    top_k: int = Field(10, ge=1, le=100)


class SearchResult(BaseModel):
    document_id: str
    chunk_id: str
    text: str
    score: float
    metadata: dict


class SearchDocumentsOutput(BaseModel):
    results: list[SearchResult]
    total_candidates: int
```

- **Category**: SEARCH
- **Timeout**: 15s
- **Side effects**: None
- **Idempotent**: Yes

#### 3.5.5 `rerank_evidence(query, candidate_chunks)`

```python
class RerankInput(BaseModel):
    query: str
    candidate_chunks: list[SearchResult]


class RerankedChunk(BaseModel):
    chunk_id: str
    text: str
    relevance_score: float
    original_score: float


class RerankOutput(BaseModel):
    reranked_chunks: list[RerankedChunk]
```

- **Category**: SEARCH
- **Timeout**: 20s
- **Side effects**: None
- **Idempotent**: Yes

#### 3.5.6 `compile_context_pack(query, evidence_chunks)`

```python
class CompileContextPackInput(BaseModel):
    query: str
    evidence_chunks: list[RerankedChunk]
    token_budget: int = Field(8000, ge=1000, le=100000)
    include_citations: bool = True


class ContextChunk(BaseModel):
    chunk_id: str
    text: str
    document_id: str
    citation_ref: str
    token_count: int


class CompileContextPackOutput(BaseModel):
    context_chunks: list[ContextChunk]
    total_tokens: int
    truncated: bool
    compression_applied: bool
```

- **Category**: UTILITY
- **Timeout**: 10s
- **Side effects**: None
- **Idempotent**: Yes

#### 3.5.7 `detect_risks(document_id, evidence)`

```python
class DetectRisksInput(BaseModel):
    document_id: str
    evidence: CompileContextPackOutput | None = None


class RiskItem(BaseModel):
    risk_id: str
    category: str
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    description: str
    source_citation: str | None = None
    recommended_action: str


class DetectRisksOutput(BaseModel):
    document_id: str
    risks: list[RiskItem]
    risk_summary: str
```

- **Category**: RISK
- **Timeout**: 60s
- **Side effects**: None
- **Idempotent**: Yes

#### 3.5.8 `generate_checklist(document_id, risk_items)`

```python
class GenerateChecklistInput(BaseModel):
    document_id: str
    risk_items: list[RiskItem]
    include_deadlines: bool = True


class ChecklistItem(BaseModel):
    item_id: str
    description: str
    priority: str = Field(..., pattern="^(low|medium|high|critical)$")
    due_date: str | None = None
    assigned_to: str | None = None
    related_risk_id: str | None = None


class GenerateChecklistOutput(BaseModel):
    document_id: str
    checklist: list[ChecklistItem]
    total_items: int
```

- **Category**: UTILITY
- **Timeout**: 30s
- **Side effects**: None
- **Idempotent**: Yes

#### 3.5.9 `create_task(task_payload, idempotency_key)`

```python
class TaskPayload(BaseModel):
    title: str
    description: str
    assignee: str | None = None
    due_date: str | None = None
    priority: str = "medium"
    labels: list[str] = []
    related_document_id: str | None = None


class CreateTaskInput(BaseModel):
    task_payload: TaskPayload
    idempotency_key: str = Field(..., description="Unique key to prevent duplicate task creation")


class CreateTaskOutput(BaseModel):
    task_id: str
    status: str
    created_at: str
```

- **Category**: TASK
- **Timeout**: 15s
- **Side effects**: Yes
- **Idempotent**: Yes (via idempotency_key)
- **Requires approval**: Configurable

#### 3.5.10 `save_extracted_fields(document_id, fields, idempotency_key)`

```python
class SaveExtractedFieldsInput(BaseModel):
    document_id: str
    fields: list[FieldValue]
    idempotency_key: str


class SaveExtractedFieldsOutput(BaseModel):
    document_id: str
    saved_count: int
    updated_at: str
```

- **Category**: TASK
- **Timeout**: 15s
- **Side effects**: Yes (writes to database)
- **Idempotent**: Yes (via idempotency_key)

#### 3.5.11 `generate_report(document_id, report_type)`

```python
class ReportType(str, Enum):
    SUMMARY = "summary"
    RISK_ASSESSMENT = "risk_assessment"
    COMPLIANCE = "compliance"
    EXTRACTION = "extraction"
    FULL = "full"


class GenerateReportInput(BaseModel):
    document_id: str
    report_type: ReportType
    include_evidence: bool = True
    include_checklist: bool = True


class GenerateReportOutput(BaseModel):
    report_id: str
    report_type: ReportType
    title: str
    sections: list[dict]
    generated_at: str
```

- **Category**: REPORT
- **Timeout**: 60s
- **Side effects**: Yes (creates report record)
- **Idempotent**: No

#### 3.5.12 `export_report(report_id, format)`

```python
class ExportFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"


class ExportReportInput(BaseModel):
    report_id: str
    format: ExportFormat


class ExportReportOutput(BaseModel):
    report_id: str
    format: ExportFormat
    file_path: str
    file_size_bytes: int
    exported_at: str
```

- **Category**: REPORT
- **Timeout**: 30s
- **Side effects**: Yes (writes file)
- **Idempotent**: No

---

## 4. Context Pipeline (C)

### 4.1 Context Window Management

The context pipeline manages what information enters the LLM context window at each step.

```python
class ContextConfig(BaseModel):
    max_context_tokens: int = 120_000
    reserved_output_tokens: int = 4_096
    system_prompt_tokens: int = 2_000
    state_tokens: int = 4_000
    available_for_evidence: int = 109_904  # max - reserved - system - state
    compression_threshold: float = 0.85
    chunk_overlap_tokens: int = 200
```

### 4.2 Context Compression

When evidence exceeds the available token budget, the pipeline applies progressive compression:

1. **Deduplication** — Remove near-duplicate chunks (cosine similarity > 0.95).
2. **Truncation** — Trim low-relevance chunks (rerank score < threshold).
3. **Summarization** — Compress remaining chunks via extractive summarization.
4. **Priority packing** — Highest-relevance chunks are placed closest to the query.

```python
class CompressionStrategy(str, Enum):
    DEDUPLICATE = "deduplicate"
    TRUNCATE = "truncate"
    SUMMARIZE = "summarize"
    PRIORITY_PACK = "priority_pack"


class ContextCompressor:
    def compress(
        self,
        chunks: list[ContextChunk],
        token_budget: int,
        strategies: list[CompressionStrategy],
    ) -> tuple[list[ContextChunk], bool]:
        """Apply compression strategies until within budget."""
        ...
```

### 4.3 Context Pack Compilation

The compiled context pack is a structured block of text injected into the LLM prompt.

```python
CONTEXT_PACK_TEMPLATE = """
## Evidence Context

{citations_block}

## Document Metadata

{metadata_block}

## Task Instructions

{task_instructions}
"""
```

Each chunk in the pack includes a citation reference:

```
[Doc:DOC-001, Chunk:7, Page:3] The contract specifies a termination clause...
```

### 4.4 Token Budget Allocation

```
Total Context Window: 128,000 tokens
├── System Prompt:        2,000 tokens  (fixed)
├── State Snapshot:       4,000 tokens  (variable, capped)
├── Evidence Context:   109,904 tokens  (dynamic)
├── Conversation Hist:    8,000 tokens  (rolling window)
└── Reserved Output:      4,096 tokens  (fixed)
```

---

## 5. State (S)

### 5.1 State Schema Definition

```python
from pydantic import BaseModel, Field
from enum import Enum
from typing import Any
from datetime import datetime


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ToolCallRecord(BaseModel):
    tool_name: str
    input_args: dict
    output: Any
    started_at: datetime
    completed_at: datetime
    success: bool
    error: str | None = None
    idempotency_key: str | None = None


class AgentState(BaseModel):
    """Core agent state — single source of truth."""

    # Session
    session_id: str
    task_type: str
    status: AgentStatus = AgentStatus.IDLE

    # Input
    user_query: str
    document_id: str | None = None
    file_id: str | None = None

    # Working memory
    classification: str | None = None
    extracted_fields: list[FieldValue] = []
    risks: list[RiskItem] = []
    checklist: list[ChecklistItem] = []
    search_results: list[SearchResult] = []
    context_pack: CompileContextPackOutput | None = None

    # Output
    report_id: str | None = None
    task_ids: list[str] = []
    response_text: str | None = None

    # Execution tracking
    iteration: int = 0
    tool_calls: list[ToolCallRecord] = []
    errors: list[str] = []
    cost_usd: float = 0.0
    tokens_used: int = 0

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

### 5.2 State Transitions

```
IDLE ──▶ RUNNING ──▶ COMPLETED
  │         │
  │         ├──▶ WAITING_APPROVAL ──▶ RUNNING
  │         │
  │         └──▶ FAILED
  │
  └──▶ CANCELLED
```

State transitions are validated:

```python
VALID_TRANSITIONS = {
    AgentStatus.IDLE: [AgentStatus.RUNNING, AgentStatus.CANCELLED],
    AgentStatus.RUNNING: [
        AgentStatus.COMPLETED,
        AgentStatus.FAILED,
        AgentStatus.WAITING_APPROVAL,
        AgentStatus.CANCELLED,
    ],
    AgentStatus.WAITING_APPROVAL: [
        AgentStatus.RUNNING,
        AgentStatus.CANCELLED,
    ],
    AgentStatus.COMPLETED: [],
    AgentStatus.FAILED: [AgentStatus.RUNNING],  # retry
    AgentStatus.CANCELLED: [],
}
```

### 5.3 State Persistence

State is persisted to a durable store after every node execution.

```python
class StateStore(Protocol):
    async def save(self, state: AgentState) -> None: ...
    async def load(self, session_id: str) -> AgentState: ...
    async def delete(self, session_id: str) -> None: ...


class PostgresStateStore(StateStore):
    """Primary production state store backed by PostgreSQL."""
    ...


class RedisStateStore(StateStore):
    """Fast cache layer for active sessions."""
    ...
```

### 5.4 Checkpointing

The orchestrator creates a checkpoint snapshot before each tool call, enabling rollback on failure.

```python
class Checkpoint(BaseModel):
    checkpoint_id: str
    session_id: str
    iteration: int
    state_snapshot: AgentState
    created_at: datetime


class CheckpointManager:
    async def create_checkpoint(self, state: AgentState) -> Checkpoint:
        """Snapshot current state before a mutating operation."""
        ...

    async def rollback(self, checkpoint_id: str) -> AgentState:
        """Restore state from a checkpoint."""
        ...
```

---

## 6. Logic / Orchestration (L)

### 6.1 LangGraph Graph Definition

The agent orchestration is implemented as a LangGraph `StateGraph`.

```python
from langgraph.graph import StateGraph, END


def build_agent_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("classify_task", classify_task_node)
    graph.add_node("parse_document", parse_document_node)
    graph.add_node("classify_document", classify_document_node)
    graph.add_node("extract_fields", extract_fields_node)
    graph.add_node("search_evidence", search_evidence_node)
    graph.add_node("rerank_evidence", rerank_evidence_node)
    graph.add_node("compile_context", compile_context_node)
    graph.add_node("detect_risks", detect_risks_node)
    graph.add_node("generate_checklist", generate_checklist_node)
    graph.add_node("create_tasks", create_tasks_node)
    graph.add_node("generate_report", generate_report_node)
    graph.add_node("export_report", export_report_node)
    graph.add_node("generate_response", generate_response_node)
    graph.add_node("validate_output", validate_output_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("error_handler", error_handler_node)

    # Entry point
    graph.set_entry_point("classify_task")

    # Compile
    return graph.compile()
```

### 6.2 Node Definitions

Each node is a pure function: `state → state`.

```python
async def classify_task_node(state: AgentState) -> AgentState:
    """Route the request to the correct task pipeline."""
    ...

async def parse_document_node(state: AgentState) -> AgentState:
    """Parse the uploaded document into structured text."""
    ...

async def classify_document_node(state: AgentState) -> AgentState:
    """Classify the document into a category."""
    ...

async def extract_fields_node(state: AgentState) -> AgentState:
    """Extract structured fields from the document."""
    ...

async def search_evidence_node(state: AgentState) -> AgentState:
    """Search for relevant evidence chunks."""
    ...

async def rerank_evidence_node(state: AgentState) -> AgentState:
    """Rerank search results by relevance."""
    ...

async def compile_context_node(state: AgentState) -> AgentState:
    """Compile evidence into a context pack."""
    ...

async def detect_risks_node(state: AgentState) -> AgentState:
    """Identify risks in the document."""
    ...

async def generate_checklist_node(state: AgentState) -> AgentState:
    """Generate an action checklist from risks."""
    ...

async def create_tasks_node(state: AgentState) -> AgentState:
    """Create external tasks from checklist items."""
    ...

async def generate_report_node(state: AgentState) -> AgentState:
    """Generate a structured report."""
    ...

async def export_report_node(state: AgentState) -> AgentState:
    """Export report to the requested format."""
    ...

async def generate_response_node(state: AgentState) -> AgentState:
    """Generate the final user-facing response."""
    ...

async def validate_output_node(state: AgentState) -> AgentState:
    """Run all output validations."""
    ...

async def human_review_node(state: AgentState) -> AgentState:
    """Pause for human approval."""
    ...

async def error_handler_node(state: AgentState) -> AgentState:
    """Handle errors and attempt recovery."""
    ...
```

### 6.3 Edge Conditions

```python
def route_after_classify(state: AgentState) -> str:
    task_type = state.task_type
    routing = {
        "document_classification": "parse_document",
        "field_extraction": "parse_document",
        "risk_detection": "parse_document",
        "qa_over_document": "search_evidence",
        "checklist_generation": "parse_document",
        "report_generation": "generate_report",
        "task_creation": "create_tasks",
        "email_draft_generation": "search_evidence",
        "database_update": "extract_fields",
    }
    return routing.get(task_type, "error_handler")


def route_after_parse(state: AgentState) -> str:
    routing = {
        "document_classification": "classify_document",
        "field_extraction": "extract_fields",
        "risk_detection": "search_evidence",
        "checklist_generation": "detect_risks",
    }
    return routing.get(state.task_type, "error_handler")


def route_after_search(state: AgentState) -> str:
    if state.search_results:
        return "rerank_evidence"
    return "generate_response"


def route_after_rerank(state: AgentState) -> str:
    routing = {
        "qa_over_document": "compile_context",
        "risk_detection": "detect_risks",
        "email_draft_generation": "compile_context",
    }
    return routing.get(state.task_type, "compile_context")


def should_continue(state: AgentState) -> str:
    if state.iteration >= 10:
        return "error_handler"
    if state.status == AgentStatus.FAILED:
        return "error_handler"
    return "generate_response"
```

### 6.4 Task Type Routing

| Task Type | Pipeline |
|-----------|----------|
| `document_classification` | parse → classify → respond |
| `field_extraction` | parse → extract → save → respond |
| `risk_detection` | parse → search → rerank → detect_risks → respond |
| `qa_over_document` | search → rerank → compile_context → respond |
| `checklist_generation` | parse → detect_risks → generate_checklist → respond |
| `report_generation` | generate_report → export → respond |
| `task_creation` | create_tasks → respond |
| `email_draft_generation` | search → rerank → compile_context → respond |
| `database_update` | parse → extract → save → respond |

### 6.5 Loop Detection

```python
MAX_ITERATIONS = 10

class LoopDetector:
    def __init__(self, max_iterations: int = MAX_ITERATIONS):
        self.max_iterations = max_iterations

    def check(self, state: AgentState) -> None:
        if state.iteration >= self.max_iterations:
            raise MaxIterationsExceeded(
                f"Agent exceeded {self.max_iterations} iterations. "
                f"Session: {state.session_id}"
            )

    def detect_cycle(self, state: AgentState, window: int = 3) -> bool:
        """Detect if the agent is cycling through the same nodes."""
        if len(state.tool_calls) < window * 2:
            return False
        recent = [tc.tool_name for tc in state.tool_calls[-window:]]
        previous = [tc.tool_name for tc in state.tool_calls[-window*2:-window]]
        return recent == previous
```

### 6.6 Fallback Strategies

```python
class FallbackStrategy:
    @staticmethod
    async def retry_with_backoff(fn, max_retries=2, base_delay=1.0):
        for attempt in range(max_retries + 1):
            try:
                return await fn()
            except RetryableError:
                if attempt == max_retries:
                    raise
                await asyncio.sleep(base_delay * (2 ** attempt))

    @staticmethod
    def use_cached_result(state: AgentState, tool_name: str) -> Any:
        """Return the most recent successful result for this tool."""
        for tc in reversed(state.tool_calls):
            if tc.tool_name == tool_name and tc.success:
                return tc.output
        return None

    @staticmethod
    async def degrade_gracefully(state: AgentState, failed_node: str) -> AgentState:
        """Continue pipeline with reduced functionality."""
        state.errors.append(f"Degraded: {failed_node} failed, continuing without")
        return state
```

---

## 7. Validation (V)

### 7.1 Input Validation

All user inputs are validated before entering the pipeline.

```python
class InputValidator:
    @staticmethod
    def validate_query(query: str) -> str:
        if not query or not query.strip():
            raise InvalidInputError("Query must not be empty")
        if len(query) > 50_000:
            raise InvalidInputError("Query exceeds maximum length (50,000 chars)")
        return query.strip()

    @staticmethod
    def validate_file_id(file_id: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]{1,128}$", file_id):
            raise InvalidInputError(f"Invalid file_id format: {file_id}")
        return file_id

    @staticmethod
    def validate_document_id(document_id: str) -> str:
        if not re.match(r"^doc-[a-zA-Z0-9]{8,64}$", document_id):
            raise InvalidInputError(f"Invalid document_id format: {document_id}")
        return document_id
```

### 7.2 Output Validation

Every node output is validated against its expected schema.

```python
class OutputValidator:
    @staticmethod
    def validate_state_coherence(state: AgentState) -> list[str]:
        warnings = []
        if state.task_type == "field_extraction" and not state.extracted_fields:
            warnings.append("field_extraction task completed with no extracted fields")
        if state.task_type == "risk_detection" and not state.risks:
            warnings.append("risk_detection task completed with no risks found")
        if state.status == AgentStatus.COMPLETED and not state.response_text:
            warnings.append("Completed agent has no response text")
        return warnings

    @staticmethod
    def validate_tool_output_safety(output: Any) -> bool:
        """Ensure tool output does not contain sensitive data leaks."""
        if isinstance(output, str):
            if re.search(r"(?i)(password|secret|token|api[_-]?key)\s*[:=]", output):
                return False
        return True
```

### 7.3 Tool Call Validation

```python
class ToolCallValidator:
    @staticmethod
    def validate_call_order(state: AgentState, tool_name: str) -> None:
        """Ensure tools are called in a valid sequence."""
        prerequisites = {
            "extract_fields": ["parse_document"],
            "detect_risks": ["parse_document"],
            "save_extracted_fields": ["extract_fields"],
            "export_report": ["generate_report"],
        }
        completed = {tc.tool_name for tc in state.tool_calls if tc.success}
        required = prerequisites.get(tool_name, [])
        missing = set(required) - completed
        if missing:
            raise ToolCallOrderError(
                f"Cannot call {tool_name}: missing prerequisites {missing}"
            )

    @staticmethod
    def validate_idempotency_key(key: str) -> None:
        if not key or len(key) < 8:
            raise InvalidIdempotencyKeyError("Idempotency key must be at least 8 chars")
```

### 7.4 Groundedness Validation

Every claim in the agent's response must be traceable to source evidence.

```python
class GroundednessValidator:
    def validate(
        self,
        response_text: str,
        context_pack: CompileContextPackOutput,
        threshold: float = 0.7,
    ) -> tuple[bool, list[str]]:
        """
        Check that each sentence in the response is grounded in the context.
        Returns (is_grounded, list_of_ungrounded_claims).
        """
        claims = self._extract_claims(response_text)
        ungrounded = []
        for claim in claims:
            score = self._compute_groundedness_score(claim, context_pack)
            if score < threshold:
                ungrounded.append(claim)
        return len(ungrounded) == 0, ungrounded

    def _extract_claims(self, text: str) -> list[str]:
        """Split response into individual factual claims."""
        ...

    def _compute_groundedness_score(
        self, claim: str, context: CompileContextPackOutput
    ) -> float:
        """Score how well a claim is supported by the evidence."""
        ...
```

### 7.5 Citation Validation

```python
class CitationValidator:
    def validate_citations(
        self,
        response_text: str,
        valid_chunk_ids: set[str],
    ) -> tuple[bool, list[str]]:
        """
        Verify that all citations in the response reference valid chunks.
        Returns (is_valid, list_of_invalid_citations).
        """
        citation_pattern = r"\[Doc:([^,]+), Chunk:(\d+)(?:, Page:(\d+))?\]"
        citations = re.findall(citation_pattern, response_text)
        invalid = []
        for doc_id, chunk_id, _ in citations:
            full_id = f"{doc_id}:{chunk_id}"
            if full_id not in valid_chunk_ids:
                invalid.append(full_id)
        return len(invalid) == 0, invalid
```

---

## 8. Agent Safety

### 8.1 Max Iteration Limits

```python
class SafetyConfig(BaseModel):
    max_iterations: int = 10
    max_tool_calls: int = 100
    max_concurrent_tool_calls: int = 5
    max_wall_clock_seconds: int = 300
```

The agent will halt with `FAILED` status if any limit is exceeded.

### 8.2 Cost Budgets

```python
class CostBudget(BaseModel):
    max_cost_per_session: float = 5.00       # USD
    max_cost_per_tool_call: float = 1.00      # USD
    warning_threshold_pct: float = 80.0        # Warn at 80% of budget
    hard_stop: bool = True                     # Stop execution at limit


class CostTracker:
    def __init__(self, budget: CostBudget):
        self.budget = budget
        self.total_cost: float = 0.0

    def record(self, cost: float) -> None:
        self.total_cost += cost
        if self.total_cost >= self.budget.max_cost_per_session:
            raise CostBudgetExceeded(
                f"Session cost ${self.total_cost:.2f} exceeds "
                f"budget ${self.budget.max_cost_per_session:.2f}"
            )

    def is_approaching_limit(self) -> bool:
        threshold = self.budget.max_cost_per_session * (self.budget.warning_threshold_pct / 100)
        return self.total_cost >= threshold
```

### 8.3 Tool Execution Guards

```python
class ToolExecutionGuard:
    def __init__(self, config: SafetyConfig):
        self.config = config
        self.call_count = 0

    async def execute(self, meta: ToolMeta, fn: Callable, args: dict) -> Any:
        self.call_count += 1
        if self.call_count > self.config.max_tool_calls:
            raise ToolCallLimitExceeded()

        if meta.requires_approval:
            await self.request_human_approval(meta.name, args)

        async with tool_sandbox(meta):
            result = await asyncio.wait_for(
                fn(**args),
                timeout=meta.timeout_seconds,
            )
        return result
```

### 8.4 Human-in-the-Loop Triggers

```python
class HITLTrigger(BaseModel):
    trigger_name: str
    condition: str
    message: str
    auto_approve_after_seconds: int | None = None


HITL_TRIGGERS = [
    HITLTrigger(
        trigger_name="high_risk_task_creation",
        condition="task.priority == 'critical'",
        message="Creating a critical-priority task. Please confirm.",
        auto_approve_after_seconds=300,
    ),
    HITLTrigger(
        trigger_name="large_report_export",
        condition="report.page_count > 50",
        message="Report exceeds 50 pages. Please confirm export.",
        auto_approve_after_seconds=600,
    ),
    HITLTrigger(
        trigger_name="sensitive_data_detected",
        condition="'pii_detected' in extraction_warnings",
        message="PII detected in extracted fields. Please review.",
        auto_approve_after_seconds=None,
    ),
]
```

### 8.5 Rollback Capabilities

```python
class RollbackManager:
    def __init__(self, checkpoint_manager: CheckpointManager, state_store: StateStore):
        self.checkpoint_manager = checkpoint_manager
        self.state_store = state_store

    async def rollback_to_last_checkpoint(self, session_id: str) -> AgentState:
        """Revert state to the most recent checkpoint."""
        checkpoints = await self.checkpoint_manager.list_checkpoints(session_id)
        if not checkpoints:
            raise NoCheckpointError(f"No checkpoints for session {session_id}")
        latest = checkpoints[-1]
        state = await self.checkpoint_manager.rollback(latest.checkpoint_id)
        state.status = AgentStatus.RUNNING
        state.errors.append(f"Rolled back to checkpoint {latest.checkpoint_id}")
        await self.state_store.save(state)
        return state

    async def rollback_tool_call(self, session_id: str, tool_call_index: int) -> AgentState:
        """Rollback to the state before a specific tool call."""
        ...
```

---

## 9. Agent Task Types

### 9.1 document_classification

| Aspect | Detail |
|--------|--------|
| **Input** | `file_id` (required) |
| **Output** | `classification`, `confidence`, `sub_category` |
| **Tool Sequence** | `parse_document` → `classify_document` |
| **Validation Rules** | confidence >= 0.5; category must be in allowed set |
| **Success Criteria** | Classification returned with confidence >= threshold |
| **Failure Handling** | Return "unknown" classification with warning |

### 9.2 field_extraction

| Aspect | Detail |
|--------|--------|
| **Input** | `file_id`, `schema_name` (required) |
| **Output** | `extracted_fields` (list of field-value pairs) |
| **Tool Sequence** | `parse_document` → `extract_fields` → `save_extracted_fields` |
| **Validation Rules** | All required schema fields present; confidence >= 0.6 |
| **Success Criteria** | All required fields extracted and saved |
| **Failure Handling** | Return partial results with warnings for missing fields |

### 9.3 risk_detection

| Aspect | Detail |
|--------|--------|
| **Input** | `file_id` (required) |
| **Output** | `risks` (list of risk items with severity) |
| **Tool Sequence** | `parse_document` → `search_documents` → `rerank_evidence` → `detect_risks` |
| **Validation Rules** | Each risk must have severity and source citation |
| **Success Criteria** | At least one risk identified, or explicit "no risks found" |
| **Failure Handling** | Return empty risk list with warning |

### 9.4 qa_over_document

| Aspect | Detail |
|--------|--------|
| **Input** | `query`, `document_id` (required) |
| **Output** | `response_text` with citations |
| **Tool Sequence** | `search_documents` → `rerank_evidence` → `compile_context_pack` → generate response |
| **Validation Rules** | Response must be grounded; all citations valid |
| **Success Criteria** | Answer with at least one valid citation |
| **Failure Handling** | Return "insufficient evidence" response |

### 9.5 checklist_generation

| Aspect | Detail |
|--------|--------|
| **Input** | `file_id` (required) |
| **Output** | `checklist` (list of actionable items) |
| **Tool Sequence** | `parse_document` → `search_documents` → `detect_risks` → `generate_checklist` |
| **Validation Rules** | Each item must have priority and description |
| **Success Criteria** | Checklist with at least one item, or "no action needed" |
| **Failure Handling** | Return generic checklist template |

### 9.6 report_generation

| Aspect | Detail |
|--------|--------|
| **Input** | `document_id`, `report_type` (required) |
| **Output** | `report_id`, report sections |
| **Tool Sequence** | `generate_report` → `export_report` (optional) |
| **Validation Rules** | Report must have title and at least one section |
| **Success Criteria** | Report generated and optionally exported |
| **Failure Handling** | Return partial report with warnings |

### 9.7 task_creation

| Aspect | Detail |
|--------|--------|
| **Input** | `task_payload` (required) |
| **Output** | `task_id`, `status` |
| **Tool Sequence** | `create_task` |
| **Validation Rules** | Title non-empty; idempotency key valid |
| **Success Criteria** | Task created in external system |
| **Failure Handling** | Return error with retry suggestion; may trigger HITL |

### 9.8 email_draft_generation

| Aspect | Detail |
|--------|--------|
| **Input** | `query`, optional `document_id` |
| **Output** | `response_text` (email draft) |
| **Tool Sequence** | `search_documents` → `rerank_evidence` → `compile_context_pack` → generate email |
| **Validation Rules** | Email must have subject, greeting, body, closing |
| **Success Criteria** | Complete email draft with grounded content |
| **Failure Handling** | Return template email with placeholders |

### 9.9 database_update

| Aspect | Detail |
|--------|--------|
| **Input** | `file_id`, `schema_name` (required) |
| **Output** | `saved_count` |
| **Tool Sequence** | `parse_document` → `extract_fields` → `save_extracted_fields` |
| **Validation Rules** | Fields must match target schema; idempotency key required |
| **Success Criteria** | All fields persisted |
| **Failure Handling** | Return partial save count with error details; rollback available |

---

## 10. Implementation Checklist

### Phase 1: Foundation

- [ ] Define all Pydantic models for State, Tool inputs/outputs, Config
- [ ] Implement `ToolRegistry` with decorator-based registration
- [ ] Implement `EnvironmentConfig` loading from YAML + env vars
- [ ] Implement `PostgresStateStore` and `RedisStateStore`
- [ ] Implement `CheckpointManager`

### Phase 2: Tools

- [ ] Implement `parse_document` tool
- [ ] Implement `classify_document` tool
- [ ] Implement `extract_fields` tool
- [ ] Implement `search_documents` tool (vector search)
- [ ] Implement `rerank_evidence` tool
- [ ] Implement `compile_context_pack` tool
- [ ] Implement `detect_risks` tool
- [ ] Implement `generate_checklist` tool
- [ ] Implement `create_task` tool
- [ ] Implement `save_extracted_fields` tool
- [ ] Implement `generate_report` tool
- [ ] Implement `export_report` tool
- [ ] Write unit tests for each tool

### Phase 3: Orchestration

- [ ] Implement all LangGraph nodes
- [ ] Define all edge conditions and routing logic
- [ ] Implement `LoopDetector`
- [ ] Implement `FallbackStrategy`
- [ ] Wire up the complete `StateGraph`
- [ ] Write integration tests for each task type pipeline

### Phase 4: Context Pipeline

- [ ] Implement `ContextCompressor` with all strategies
- [ ] Implement context pack template rendering
- [ ] Implement token budget allocation logic
- [ ] Test with documents exceeding context window

### Phase 5: Validation

- [ ] Implement `InputValidator`
- [ ] Implement `OutputValidator`
- [ ] Implement `ToolCallValidator`
- [ ] Implement `GroundednessValidator`
- [ ] Implement `CitationValidator`

### Phase 6: Safety

- [ ] Implement `CostTracker` and `CostBudget`
- [ ] Implement `ToolExecutionGuard`
- [ ] Implement HITL triggers and approval flow
- [ ] Implement `RollbackManager`
- [ ] Write safety regression tests

### Phase 7: Observability

- [ ] Add OpenTelemetry tracing to all nodes and tools
- [ ] Add structured logging (JSON format)
- [ ] Add Prometheus metrics (latency, cost, error rate)
- [ ] Build Grafana dashboards

### Phase 8: Deployment

- [ ] Docker containerization
- [ ] CI/CD pipeline
- [ ] Staging environment deployment
- [ ] Load testing
- [ ] Production deployment

---

## 11. Acceptance Criteria

### AC-1: Core Functionality

- [ ] All 9 task types execute end-to-end successfully
- [ ] Each tool produces valid output matching its Pydantic schema
- [ ] State persists correctly across node transitions
- [ ] Checkpointing and rollback work for failed tool calls

### AC-2: Validation

- [ ] Invalid inputs are rejected with clear error messages
- [ ] Groundedness validation catches ungrounded claims with > 90% precision
- [ ] Citation validation catches all invalid references
- [ ] Tool call order is enforced (no calling `extract_fields` before `parse_document`)

### AC-3: Safety

- [ ] Agent halts when iteration limit (10) is reached
- [ ] Agent halts when cost budget is exceeded
- [ ] HITL triggers fire for all defined conditions
- [ ] No sensitive data (API keys, passwords) appears in logs or responses

### AC-4: Performance

- [ ] Average end-to-end latency < 30 seconds for simple tasks
- [ ] Average end-to-end latency < 120 seconds for complex tasks
- [ ] Tool calls complete within their defined timeouts
- [ ] Context compression activates when evidence exceeds 85% of budget

### AC-5: Reliability

- [ ] Failed tool calls retry up to 2 times with exponential backoff
- [ ] Fallback strategies allow the pipeline to continue on non-critical failures
- [ ] No duplicate side-effects (verified by idempotency key tests)
- [ ] State corruption does not occur under concurrent access

### AC-6: Observability

- [ ] Every node execution emits a structured log entry
- [ ] Every tool call emits an OpenTelemetry span
- [ ] Cost, latency, and error rate metrics are available in Prometheus
- [ ] Full execution trace is available for debugging any session
