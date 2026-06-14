# Phase 6A: Agent Harness + Tool Registry — Implementation Plan

## Task
Implement LangGraph agent orchestrator with tool registry, schema validation, and safety controls.

## Dependencies
Phase 5A (RAG pipeline)

## Files to Create

### 1. `backend/app/agents/__init__.py`
- Empty init

### 2. `backend/app/agents/state.py`
- AgentState TypedDict
- messages, documents, current_step, iteration, max_iterations, tool_results, final_answer, metadata

### 3. `backend/app/agents/graph.py`
- create_agent_graph() -> StateGraph
- Nodes: retrieve, reason, tool_call, synthesize
- Edges: conditional routing
- Loop detection

### 4. `backend/app/agents/nodes/retrieve.py`
- retrieve_node(state) -> state
- Hybrid search on relevant documents

### 5. `backend/app/agents/nodes/reason.py`
- reason_node(state) -> state
- LLM decides next action (tool call or synthesize)

### 6. `backend/app/agents/nodes/tool_call.py`
- tool_call_node(state) -> state
- Execute selected tool with validation

### 7. `backend/app/agents/nodes/synthesize.py`
- synthesize_node(state) -> state
- Generate final answer from accumulated context

### 8. `backend/app/agents/tools/__init__.py`
- Tool registry

### 9. `backend/app/agents/tools/registry.py`
- ToolRegistry class
- @tool decorator
- register, get, list_tools, execute methods
- Schema validation before execution

### 10. `backend/app/agents/tools/search_tool.py`
- search_documents tool

### 11. `backend/app/agents/tools/document_tool.py`
- get_document tool

### 12. `backend/app/agents/safety.py`
- LoopDetector class
- CostTracker class
- MaxIterationGuard

### 13. `backend/app/services/agent_service.py`
- AgentService class
- run(task_type, input) -> AgentResult

### 14. `backend/app/api/v1/agent.py`
- POST /api/v1/agent/run
- GET /api/v1/agent/sessions/{session_id}

## Acceptance Criteria
- [ ] Agent invokes registered tools
- [ ] Tool schema validation rejects malformed input
- [ ] Loop detection terminates after max 10 iterations
- [ ] Cost tracking reports per-step usage
- [ ] Session history persisted and retrievable

## Test Requirements
- `tests/agent/test_state_machine.py`
- `tests/agent/test_tool_registry.py`
- `tests/agent/test_loop_detection.py`
- `tests/agent/test_safety.py`
- `tests/api/test_agent.py`
