# Agent Harness — Kiến trúc hệ thống

> **Kiến trúc đã implement** — ✅ Phase 1 (Agent Harness Core) + ✅ Phase 2 (Multi-Agent Orchestration).
> Chi tiết tại [Implementation Notes](#12-implementation-notes).

---

## 1. Tổng quan System Architecture

```mermaid
flowchart TB
    subgraph Clients["Client Layer"]
        UI["Next.js UI / Dashboard"]
        CLI["CLI / API Clients"]
        WEB["Webhook / External Systems"]
    end

    subgraph API["API Gateway Layer"]
        AGW["FastAPI Gateway"]
        AUTH["Auth / RBAC Middleware"]
        RATE["Rate Limiter"]
        WS["WebSocket Manager"]
    end

    subgraph Core["Agent Harness Core"]
        direction TB
        
        subgraph Registry["Registry & Definitions"]
            AREG["AgentRegistry<br/>đăng ký / discovery agent"]
            TREG["ToolRegistry<br/>đăng ký / schema validation"]
            ASPEC["AgentSpec<br/>declarative agent định nghĩa"]
        end

        subgraph Execution["Execution Engine"]
            AG["AgentGraph<br/>LangGraph + Fallback Engine"]
            AS["AgentService<br/>session lifecycle, persistence"]
            MUX["AgentRouter<br/>route request → agent phù hợp"]
            CHAIN["AgentChain<br/>pipeline nhiều agent"]
        end

        subgraph Safety["Safety & Guardrails"]
            IG["IterationGuard"]
            CG["CostGuard"]
            WCG["WallClockGuard"]
            LD["LoopDetector"]
            HIL["Human-in-the-Loop Gates"]
        end

        subgraph Tools["Tool System"]
            TPLUG["Plugin Loader<br/>load tool từ external"]
            TDEP["Dependency Injector<br/>DB, API, Retriever, ..."]
            TEXEC["Tool Executor<br/>validate + execute + retry"]
        end

        subgraph LLM["LLM Layer"]
            LPROV["LLMProvider Factory"]
            OAI["OpenAI Provider"]
            ANT["Anthropic Provider"]
            XIAO["Xiaomi Provider"]
            LOC["Local / Ollama Provider"]
            FALL["Fallback / Mock"]
        end
    end

    subgraph Agents["Agent Library (Built-in Templates)"]
        DQA["doc-qa<br/>Q&A trên tài liệu"]
        DEXT["doc-extract<br/>Trích xuất metadata"]
        SUM["summarize<br/>Tóm tắt văn bản"]
        CODE["code-review<br/>Review code"]
        CHAT["chat<br/>Conversation"]
        CUST["custom<br/>User-defined"]
    end

    subgraph Persistence["Data Layer"]
        PSQL[("PostgreSQL<br/>sessions, steps, templates")]
        QDR[("Qdrant<br/>document vectors")]
        REDIS[("Redis<br/>cache, queue, realtime")]
        MINIO[("MinIO<br/>file storage")]
    end

    subgraph Observability["Observability"]
        LF["Langfuse<br/>traces, cost, eval"]
        OTEL["OpenTelemetry<br/>metrics, tracing"]
        LOG["Structured Logging"]
        PROM["Prometheus Metrics"]
    end

    subgraph Workers["Background Workers"]
        ARQ["ARQ Task Queue"]
        DOCP["process-document"]
        AGT["run-agent (async)"]
    end

    %% Connections
    Clients --> API
    API --> Core
    API --> AUTH
    API --> WS
    
    Core --> Agents
    
    AREG <--> ASPEC
    TREG <--> ASPEC
    
    MUX --> AREG
    MUX --> AG
    
    AG --> AS
    AG -.-> Safety
    AG -.-> Tools
    AG --> LLM
    
    CHAIN --> AG
    CHAIN --> MUX
    
    Tools --> TREG
    TEXEC --> TDEP
    
    AS --> Persistence
    AG --> Workers
    
    Core -.-> Observability
    Workers --> Persistence
    Workers --> Observability
```

---

## 2. Agent Definition Schema

```mermaid
classDiagram
    class AgentSpec {
        +String name
        +String description
        +String version
        +String system_prompt
        +List~String~ tools
        +ModelConfig model
        +GuardrailConfig guardrails
        +Int max_iterations
        +BaseModel input_schema
        +BaseModel output_schema
        +List~String~ allowed_edges
        +Dict metadata
        +validate()
        +compile_prompt()
    }

    class ModelConfig {
        +String provider
        +String model_name
        +Float temperature
        +Int max_tokens
        +Int timeout
    }

    class GuardrailConfig {
        +Int max_iterations
        +Float max_cost_usd
        +Int max_wall_clock_sec
        +Int max_tool_repeats
        +List~HILGate~ hil_gates
    }

    class HILGate {
        +String gate_type
        +String trigger_condition
        +Int timeout_seconds
        +String on_timeout_action
    }

    class AgentRegistry {
        -Dict~String, AgentSpec~ _agents
        +register(spec)
        +get(name) AgentSpec
        +list() List~AgentSpec~
        +find_by_capability(query) List~AgentSpec~
    }

    AgentSpec --> ModelConfig
    AgentSpec --> GuardrailConfig
    GuardrailConfig --> HILGate
    AgentRegistry --> AgentSpec
```

---

## 3. Agent Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> PENDING : submit request

    PENDING --> QUEUED : validate input
    PENDING --> REJECTED : validation fail

    QUEUED --> RUNNING : worker picks up

    RUNNING --> RETRIEVE : context gathering
    RUNNING --> TOOL_CALL : execute tool
    RUNNING --> REASONING : LLM decide next step
    RUNNING --> SYNTHESIZE : generate final answer

    RETRIEVE --> REASONING
    TOOL_CALL --> REASONING : loop back
    REASONING --> TOOL_CALL : LLM decides tool needed
    REASONING --> SYNTHESIZE : LLM decides done
    
    SYNTHESIZE --> PAUSED : HIL gate triggered
    SYNTHESIZE --> COMPLETED : no gate / approved

    PAUSED --> RUNNING : human approves
    PAUSED --> RUNNING : human edits & resubmits
    PAUSED --> CANCELLED : human rejects

    RUNNING --> FAILED : error / guardrail hit
    RUNNING --> CANCELLED : user cancels
    RUNNING --> TIMEOUT : wall clock exceeded

    COMPLETED --> [*]
    FAILED --> [*]
    CANCELLED --> [*]
    TIMEOUT --> [*]
    REJECTED --> [*]
```

---

## 4. Multi-Agent Orchestration Patterns

### 4.1 Router Agent Pattern

```mermaid
sequenceDiagram
    actor User
    participant Router as RouterAgent
    participant Registry as AgentRegistry
    participant Sub as Sub-Agent
    participant Store as SessionStore

    User->>Router: POST /agents/run (query, context)
    
    Router->>Registry: find_agent(task_type)
    Registry-->>Router: agent_spec
    
    Router->>Router: classify request → select agent
    
    alt classification confident
        Router->>Sub: delegate(query, context)
        
        Sub->>Sub: execute (reason → tool → ... → synthesize)
        Sub-->>Router: result
        
        Router->>Store: save session (hierarchical)
        Router-->>User: final_answer
    else needs clarification
        Router-->>User: clarification_questions
    else needs multiple agents
        Router->>Sub: run agent_1 (extract)
        Router->>Sub: run agent_2 (analyze) parallel
        
        Sub-->>Router: results
        Router->>Router: aggregate & synthesize
        Router-->>User: combined_answer
    end
```

### 4.2 Agent Chain Pattern

```mermaid
flowchart LR
    A["Agent: extractor<br/>Trích xuất entities"] --> 
    B["Agent: validator<br/>Kiểm tra consistency"] -->
    C["Agent: risk-scorer<br/>Đánh giá rủi ro"] -->
    D["Agent: reporter<br/>Tổng hợp báo cáo"]
    
    D --> E[("Lưu session + kết quả")]
    
    style A fill:#e1f5fe
    style B fill:#fff3e0
    style C fill:#fce4ec
    style D fill:#e8f5e9
```

### 4.3 Supervisor + Workers Pattern

```mermaid
flowchart TB
    S[("Supervisor Agent<br/>phân tích task, phối hợp")] 
    
    S --> W1["Worker: search-docs<br/>tìm documents"]
    S --> W2["Worker: extract-fields<br/>trích xuất thông tin"]
    S --> W3["Worker: calc-metrics<br/>tính toán chỉ số"]
    S --> W4["Worker: check-compliance<br/>kiểm tra quy định"]

    W1 --> S
    W2 --> S
    W3 --> S
    W4 --> S
    
    S --> SYNTH["Supervisor: tổng hợp kết quả"]
    SYNTH --> OUT["Final Output"]

    style S fill:#e8eaf6
    style SYNTH fill:#e8eaf6
    style OUT fill:#c8e6c9
```

---

## 5. Tool System Architecture

```mermaid
flowchart TB
    subgraph Registration["Tool Registration"]
        DECORATE["@registry.register()<br/>decorator"]
        DYNAMIC["Dynamic Loader<br/>scan packages"]
        EXT["External Plugin<br/>pip install tool-plugin"]
    end

    subgraph ToolRegistry["ToolRegistry"]
        STORE[("tool store<br/>name → ToolEntry")]
        SCHEMA["Pydantic Schema Validation"]
        CATEGORY["Tool Categories<br/>document | code | web | calc"]
    end

    subgraph Execution["Tool Execution"]
        INJECT["Dependency Injection<br/>DB session, retriever, client"]
        VALIDATE["Input Validation<br/>Pydantic model"]
        EXECUTE["Execute<br/>sync / async / retry"]
        LOG["Log + Trace<br/>duration, tokens, result"]
    end

    subgraph Lifecycle["Tool Lifecycle Hooks"]
        PRE["before_execute(ctx)"]
        POST["after_execute(ctx, result)"]
        ERR["on_error(ctx, error)"]
    end

    Registration --> ToolRegistry
    ToolRegistry --> Execution
    Execution --> Lifecycle

    classDef plugin fill:#f3e5f5
    class EXT plugin
```

---

## 6. Generic Agent API Endpoints

```mermaid
flowchart LR
    subgraph Endpoints["Agent Harness API"]
        direction TB
        
        L1["GET /v1/agents<br/>List available agents"]
        L2["GET /v1/agents/{name}/spec<br/>Get agent definition"]
        L3["POST /v1/agents/{name}/run<br/>Execute agent"]
        L4["GET /v1/agents/sessions/{id}<br/>Get session result"]
        L5["POST /v1/agents/sessions/{id}/cancel<br/>Cancel running agent"]
        L6["POST /v1/agents/sessions/{id}/approve<br/>Approve HIL gate"]
        L7["WS /v1/agents/sessions/{id}/stream<br/>Real-time streaming"]
        L8["GET /v1/agents/templates<br/>List agent templates"]
    end

    style L3 stroke:#22c55e,stroke-width:2px
    style L7 stroke:#3b82f6,stroke-width:2px
```

---

## 7. Data Model (Persistence)

```mermaid
erDiagram
    AGENT_SPEC ||--o{ AGENT_SESSION : defines
    AGENT_SPEC ||--o{ AGENT_VERSION : versions
    AGENT_SPEC ||--o{ TOOL_BINDING : configures_tools
    
    AGENT_SESSION ||--o{ AGENT_STEP : contains
    AGENT_SESSION ||--o{ HIL_REQUEST : may_have
    AGENT_SESSION }o--|| USER : owns
    
    HIL_REQUEST ||--o{ HIL_DECISION : resolved_by
    
    TOOL_BINDING }o--|| TOOL_DEFINITION : binds

    AGENT_SPEC {
        uuid id PK
        string name UK
        string version
        string description
        text system_prompt
        json model_config
        json guardrail_config
        json input_schema
        json output_schema
        datetime created_at
        datetime updated_at
    }

    AGENT_VERSION {
        uuid id PK
        uuid spec_id FK
        string version
        json spec_snapshot
        string changelog
        datetime created_at
    }

    AGENT_SESSION {
        uuid id PK
        uuid spec_id FK
        uuid user_id FK
        string agent_name
        string status
        json input_data
        json output_data
        string error_message
        int total_iterations
        int total_tokens
        float total_cost_usd
        string model_used
        uuid parent_session_id
        string session_tree_path
        datetime started_at
        datetime completed_at
    }

    AGENT_STEP {
        uuid id PK
        uuid session_id FK
        int step_index
        string step_type
        string action
        json input_data
        json output_data
        string reasoning
        string tool_name
        json tool_arguments
        int tokens_used
        int duration_ms
        string status
        datetime created_at
    }

    HIL_REQUEST {
        uuid id PK
        uuid session_id FK
        string gate_type
        string trigger_reason
        json context_snapshot
        string status
        int timeout_seconds
        datetime expires_at
        datetime created_at
    }

    HIL_DECISION {
        uuid id PK
        uuid hil_request_id FK
        uuid user_id FK
        string decision
        string comment
        json edited_output
        string reviewed_by
        datetime created_at
    }

    TOOL_DEFINITION {
        uuid id PK
        string name UK
        string description
        string category
        json input_schema
        json output_example
        string module_path
        string version
        bool enabled
        datetime created_at
    }

    TOOL_BINDING {
        uuid id PK
        uuid spec_id FK
        uuid tool_id FK
        json dependency_overrides
        bool enabled
    }

    USER {
        uuid id PK
        string email
        string role
    }
```

---

## 8. Flow xử lý request điển hình

```mermaid
sequenceDiagram
    actor Client
    
    box Agent Harness Core
        participant Router as AgentRouter
        participant Spec as AgentRegistry
        participant Svc as AgentService
        participant Graph as AgentGraph
        participant Tools as ToolRegistry
        participant LLM as LLMProvider
    end
    
    box Persistence
        participant DB as PostgreSQL
        participant Cache as Redis
    end

    Client->>Router: POST /v1/agents/doc-qa/run
    Note over Router: query: "Hợp đồng nào sắp hết hạn?"

    Router->>Spec: get("doc-qa")
    Spec-->>Router: AgentSpec {system_prompt, tools, guardrails}

    Router->>Svc: run(doc-qa, input, user_id)
    Svc->>DB: create AgentSession (status=running)
    DB-->>Svc: session_id

    Svc->>Graph: ainvoke(initial_state)
    
    par Execute Graph
        Graph->>Graph: retrieve_node → lấy context
        
        loop Reason-Tool Cycle
            Graph->>LLM: call LLM với system prompt + context
            LLM-->>Graph: tool_call (search_documents)

            Graph->>Tools: execute_async("search_documents", {query})
            Tools->>Tools: validate input schema
            Tools->>Tools: inject dependencies (retriever)
            Tools-->>Graph: [{doc_id, text, score}]

            Graph->>Graph: tool_call_node → append result
            Graph->>LLM: call LLM với tool result
            LLM-->>Graph: synthesize
        end

        Graph->>Graph: synthesize_node → final_answer
    end

    Graph-->>Svc: final_state {answer, steps, cost}

    Svc->>DB: persist steps
    Svc->>DB: update session (status=completed)
    Svc-->>Router: AgentResult

    alt streaming requested
        Router->>Cache: publish to session channel
        Cache-->>Client: WS stream events
    end

    Router-->>Client: {answer, session_id, steps_summary}
```

---

## 9. Layer Hierarchy (Package Structure) — As-Built

```
backend/
├── app/
│   ├── harness/                      # Agent Harness Core (PHASE 1 ✅)
│   │   ├── __init__.py
│   │   ├── agent_spec.py             # AgentSpec, ModelConfig, GuardrailConfig
│   │   ├── agent_registry.py         # AgentRegistry singleton + discovery
│   │   ├── agent_graph.py            # Graph factory (LangGraph + fallback)
│   │   ├── multi_agent.py            # Router, Chain, Parallel patterns (PHASE 2 ✅)
│   │   ├── nodes/
│   │   │   ├── __init__.py
│   │   │   ├── reason.py             # make_reason_node
│   │   │   ├── tool_call.py          # make_tool_call_node
│   │   │   └── synthesize.py         # make_synthesize_node
│   │   └── safety.py                 # Guards, loop detector, cost tracker
│   │
│   ├── agents/                       # Agent Library
│   │   ├── agents/                   # Agent templates (4 built-in)
│   │   │   ├── __init__.py           # load_builtin_agents()
│   │   │   ├── doc_qa.py             # doc-qa template
│   │   │   ├── chat.py               # chat template
│   │   │   ├── summarise.py          # summarise template
│   │   │   └── router.py             # router template (PHASE 2 ✅)
│   │   ├── tools/                    # Tool system
│   │   │   ├── __init__.py
│   │   │   ├── registry.py           # ToolRegistry
│   │   │   ├── document_tool.py
│   │   │   ├── search_tool.py
│   │   │   └── delegate_tool.py      # delegate_to_agent (PHASE 2 ✅)
│   │   ├── state.py                  # AgentState
│   │   ├── safety.py                 # MaxIterationGuard, CostTracker, etc.
│   │   └── nodes/                    # (legacy, replaced by harness/nodes/)
│   │
│   ├── api/v1/
│   │   ├── agent.py                  # Agent API endpoints (PHASE 1+2 ✅)
│   │   ├── documents.py
│   │   └── ...
│   │
│   ├── services/
│   │   ├── agent_service.py          # AgentService (PHASE 1+2 ✅)
│   │   └── ...
│   │
│   ├── db/
│   │   ├── session.py                # get_async_session (PHASE 2 ✅)
│   │   ├── models/agent.py           # AgentSession + AgentStep
│   │   └── ...
│   │
│   ├── llm/                          # LLM abstraction
│   ├── rag/                          # Retrieval
│   └── ...
```

---

## 10. Technology Map

| Layer | Hiện tại | Nâng cấp | Status |
|-------|----------|----------|--------|
| **Agent Definition** | Hardcoded trong graph nodes | `AgentSpec` declarative, Pydantic-validated | ✅ |
| **Agent Registry** | Không có | `AgentRegistry` singleton + discovery API | ✅ |
| **Graph Engine** | LangGraph + Fallback (1 graph) | Generic `AgentGraph`, agent-specific graphs | ✅ |
| **Tool System** | Singleton `ToolRegistry`, 2 tools | Plugin system, categories, DI, lifecycle hooks | ⏳ Phase 3 |
| **Multi-Agent** | Không | Router, Chain, Supervisor-Workers patterns | ✅ Router+Chain+Parallel |
| **State Schema** | `AgentState` có `documents` field | `BaseAgentState` + per-agent context extension | ✅ |
| **Human-in-Loop** | Không | `HILGate` với approve/reject/edit API | ❌ Chưa có |
| **API** | Document-specific endpoints | Generic `/agent/*` endpoints | ✅ |
| **Session** | DB lưu steps | Hierarchical sessions, session tree | ⏳ |
| **Streaming** | HTTP response | WebSocket real-time stream | ❌ Chưa có |
| **Templates** | Không | Built-in: doc-qa, chat, summarise, router | ✅ |
| **Plugins** | Không | External tool/agent loading | ❌ Chưa có |

---

## 11. Key Design Decisions

| Decision | Lựa chọn | Lý do |
|----------|----------|-------|
| Agent định nghĩa bằng code (decorator) thay vì YAML/JSON | **Python DSL** | Type safety, IDE autocomplete, dễ test, tận dụng Pydantic |
| Graph engine: LangGraph ưu tiên, fallback state machine | **Hybrid** | Không ép dependency; production dùng LangGraph, dev/test dùng fallback |
| Tool dependency injection | **Factory function** (`create_bound_*`) | Pattern hiện tại đã đúng, chỉ cần generalize |
| Agent session tree | **Parent-child với path** | Cho phép trace agent nào gọi agent nào |
| HIL timeout | **Configurable + fallback action** | Không block system vô thời hạn |
| Plugin system | **Entry-point based** (Python namespace) | Tương tự pytest plugins, không cần thêm framework |

---

> **Document này là architecture blueprint.** Các mục đã implement được đánh dấu ✅ trong Technology Map và Implementation Notes bên dưới.

---

## 12. Implementation Notes

### Phase 1 — Agent Harness Core (Implemented ✅)

| Component | File | Status |
|-----------|------|--------|
| `AgentSpec` + factory methods | `app/harness/agent_spec.py` | ✅ |
| `AgentRegistry` singleton | `app/harness/agent_registry.py` | ✅ |
| `build_agent_graph()` (LangGraph + fallback) | `app/harness/agent_graph.py` | ✅ |
| Reason node (`make_reason_node`) | `app/harness/nodes/reason.py` | ✅ |
| Tool call node (`make_tool_call_node`) | `app/harness/nodes/tool_call.py` | ✅ |
| Synthesize node (`make_synthesize_node`) | `app/harness/nodes/synthesize.py` | ✅ |
| Agent templates (doc-qa, chat, summarise) | `app/agents/agents/` | ✅ |
| `AgentState` with context field | `app/agents/state.py` | ✅ |
| `AgentService.run_agent()` + legacy `run()` | `app/services/agent_service.py` | ✅ |
| API endpoints + lifespan loading | `app/api/v1/agent.py` + `app/main.py` | ✅ |

### Phase 2 — Multi-Agent Orchestration (Implemented ✅)

| Component | File | Status |
|-----------|------|--------|
| `delegate_to_agent` tool | `app/agents/tools/delegate_tool.py` | ✅ |
| `get_async_session` context manager | `app/db/session.py` | ✅ |
| `MultiAgentRouter` (keyword + LLM classification) | `app/harness/multi_agent.py` | ✅ |
| `AgentChain` (sequential pipeline) | `app/harness/multi_agent.py` | ✅ |
| `ParallelAgentGroup` (concurrent fan-out) | `app/harness/multi_agent.py` | ✅ |
| Router agent template | `app/agents/agents/router.py` | ✅ |
| API: `POST /agent/chain/run` | `app/api/v1/agent.py` | ✅ |
| API: `POST /agent/parallel/run` | `app/api/v1/agent.py` | ✅ |
| API: `POST /agent/route/run` | `app/api/v1/agent.py` | ✅ |
| `AgentService.run_chain()` | `app/services/agent_service.py` | ✅ |

### Deviations from Original Plan

| Planned | Actual | Reason |
|---------|--------|--------|
| `app/harness/agent_router.py` | `app/harness/multi_agent.py` (consolidated) | Cleaner single file for all orchestration patterns |
| `app/harness/agent_chain.py` | Inside `multi_agent.py` | Less file sprawl |
| `/v1/agents/*` endpoints | `/agent/*` | Simpler routing, consistent with existing pattern |
| 5 built-in agents | 4 (doc-qa, chat, summarise, router) | doc-extract not yet needed; router added |
| HIL gates, WebSocket streaming, Plugin system | Not implemented (Phase 3+) | Out of scope for initial implementation |
