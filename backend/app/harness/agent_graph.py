"""Generic agent graph factory.

Builds an appropriate LangGraph (or fallback state machine) for any
``AgentSpec``.  Supports both tool-using agents (ReAct loop) and
simple single-turn agents.

All graph loops now support:

* **Cancellation** — periodic ``CancelToken.check()``
* **HIL gates** — pauses execution when a gate trigger condition matches
* **Event emission** — broadcasts step updates via ``EventManager``
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.harness.agent_spec import AgentSpec, HILGateConfig

logger = logging.getLogger(__name__)


def build_agent_graph(spec: AgentSpec) -> Any:
    """Build and return an executable agent graph for the given AgentSpec.

    The graph topology depends on the agent's tool configuration:

    * **No tools / simple agents** — single ``synthesize`` node (prompt → answer).
    * **With tools** — full ReAct loop: retrieve → (reason → tool_call)⁺ → synthesize.
    * **Document agents** (category == "document") — adds a ``retrieve`` node for
      hybrid search over the document corpus.

    Args:
        spec: The agent specification describing system prompt, tools, guardrails.

    Returns:
        A compiled graph with ``invoke(state)`` / ``ainvoke(state)`` methods.
    """
    has_tools = len(spec.tools) > 0
    is_document_agent = spec.metadata.get("category") == "document"

    if is_document_agent:
        return _build_document_graph(spec)
    if has_tools:
        return _build_react_graph(spec)
    return _build_simple_graph(spec)


# ── graph builders ──────────────────────────────────────────────────────


def _build_simple_graph(spec: AgentSpec) -> Any:
    """Build a single-node graph: prompt → answer.

    For agents with no tools (e.g. ``chat``).
    """
    try:
        return _build_langgraph_simple(spec)
    except ImportError:
        pass

    return _FallbackSimpleGraph(spec)


def _build_react_graph(spec: AgentSpec) -> Any:
    """Build a ReAct loop graph: reason ↔ tool_call → synthesize.

    For generic agents with tools but no document retrieval.
    """
    try:
        return _build_langgraph_react(spec)
    except ImportError:
        pass

    return _FallbackReActGraph(spec)


def _build_document_graph(spec: AgentSpec) -> Any:
    """Build a document-aware RAG graph: retrieve → (reason ↔ tool_call) → synthesize.

    For document-category agents like ``doc-qa``.
    """
    try:
        return _build_langgraph_document(spec)
    except ImportError:
        pass

    return _FallbackDocumentGraph(spec)


# ── LangGraph builders ──────────────────────────────────────────────────


def _build_langgraph_simple(spec: AgentSpec) -> Any:
    """LangGraph: single synthesize node."""
    from langgraph.graph import END, START, StateGraph

    from app.agents.state import AgentState as State

    graph = StateGraph(State)
    graph.add_node("synthesize", _make_synthesize_node(spec))
    graph.add_edge(START, "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()


def _build_langgraph_react(spec: AgentSpec) -> Any:
    """LangGraph: ReAct loop with reason, tool_call, synthesize."""
    from langgraph.graph import END, START, StateGraph

    from app.agents.state import AgentState as State
    from app.harness.nodes.reason import make_reason_node
    from app.harness.nodes.synthesize import make_synthesize_node
    from app.harness.nodes.tool_call import make_tool_call_node

    def _should_call_tool(state: dict) -> str:
        pending = state.get("pending_tool")
        iteration = state.get("iteration", 0)
        max_iter = spec.guardrails.max_iterations
        if iteration >= max_iter:
            return "synthesize"
        if pending and pending.get("name"):
            return "tool_call"
        return "synthesize"

    graph = StateGraph(State)
    graph.add_node("reason", make_reason_node(spec))
    graph.add_node("tool_call", make_tool_call_node())
    graph.add_node("synthesize", make_synthesize_node(spec))

    graph.add_edge(START, "reason")
    graph.add_conditional_edges(
        "reason",
        _should_call_tool,
        {"tool_call": "tool_call", "synthesize": "synthesize"},
    )
    graph.add_edge("tool_call", "reason")
    graph.add_edge("synthesize", END)

    return graph.compile()


def _build_langgraph_document(spec: AgentSpec) -> Any:
    """LangGraph: retrieve → (reason ↔ tool_call) → synthesize.

    This preserves the current ``doc-qa`` graph topology exactly.
    """
    from langgraph.graph import END, START, StateGraph

    from app.agents.nodes.retrieve import retrieve_node
    from app.agents.nodes.synthesize import synthesize_node as doc_synthesize_node
    from app.agents.state import AgentState as State
    from app.harness.nodes.reason import make_reason_node
    from app.harness.nodes.tool_call import make_tool_call_node

    def _should_call_tool(state: dict) -> str:
        pending = state.get("pending_tool")
        iteration = state.get("iteration", 0)
        max_iter = spec.guardrails.max_iterations
        if iteration >= max_iter:
            return "synthesize"
        if pending and pending.get("name"):
            return "tool_call"
        return "synthesize"

    graph = StateGraph(State)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("reason", make_reason_node(spec))
    graph.add_node("tool_call", make_tool_call_node())
    graph.add_node("synthesize", doc_synthesize_node)

    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "reason")
    graph.add_conditional_edges(
        "reason",
        _should_call_tool,
        {"tool_call": "tool_call", "synthesize": "synthesize"},
    )
    graph.add_edge("tool_call", "reason")
    graph.add_edge("synthesize", END)

    return graph.compile()


# ── Shared node factories ───────────────────────────────────────────────


def _make_synthesize_node(spec: AgentSpec) -> Any:
    """Create a simple synthesize node for non-tool agents.

    Uses the agent's system prompt and calls the LLM directly.
    """

    async def synthesize_node(state: dict) -> dict:
        import time

        from app.agents.state import StepRecord
        from app.llm.factory import get_llm_provider
        from app.llm.base import Message

        start = time.monotonic()
        messages = state.get("messages", [])

        llm = get_llm_provider()
        llm_messages = [
            Message(role="system", content=spec.system_prompt),
            *(Message(role=m.get("role", "user"), content=m.get("content", ""))
              for m in messages if isinstance(m, dict)),
        ]

        try:
            response = await llm.chat(
                messages=llm_messages,
                model=spec.model.model_name,
                max_tokens=spec.model.max_tokens,
                temperature=spec.model.temperature,
            )
            answer = response.content
        except Exception as e:
            logger.error("synthesize_node LLM call failed: %s", e)
            answer = f"I encountered an error: {e}"

        elapsed_ms = int((time.monotonic() - start) * 1000)

        steps = list(state.get("steps", []))
        steps.append(
            StepRecord(
                step_type="synthesize",
                iteration=state.get("iteration", 0),
                input_summary=f"messages={len(messages)}",
                output_summary=answer[:200],
                duration_ms=elapsed_ms,
            )
        )

        return {
            "final_answer": answer,
            "current_step": "synthesize",
            "steps": steps,
        }

    return synthesize_node


# ── Fallback graphs (no LangGraph) ──────────────────────────────────────


async def _check_hil_gates(
    spec: AgentSpec,
    state: dict,
    session_id: str,
) -> dict | None:
    """Check configured HIL gates and pause if a trigger matches.

    Returns the HIL decision dict if a gate was triggered, None otherwise.
    """
    gates: list[HILGateConfig] = spec.guardrails.hil_gates
    if not gates:
        return None

    current_step = state.get("current_step", "")
    pending_tool = state.get("pending_tool")
    iteration = state.get("iteration", 0)

    for gate in gates:
        trigger = gate.trigger_condition

        if trigger == "before_tool_call" and pending_tool and pending_tool.get("name"):
            pass  # will trigger
        elif trigger == "before_synthesize" and current_step == "synthesize":
            pass  # will trigger
        elif trigger.startswith("on_iteration:"):
            target = int(trigger.split(":", 1)[1])
            if iteration < target:
                continue
        else:
            continue

        from app.harness.hil_service import HILService

        hil = HILService()
        context = {
            "step": current_step,
            "iteration": iteration,
            "pending_tool": str(pending_tool.get("name", "")) if pending_tool else None,
        }
        decision = await hil.request_approval(
            session_id=session_id,
            gate=gate,
            context=context,
        )
        return decision

    return None


async def _emit_step_event(session_id: str, state: dict, step_type: str) -> None:
    """Emit a step event via the EventManager (fire-and-forget safe)."""
    from app.harness.event_manager import get_event_manager

    mgr = get_event_manager()
    if mgr.is_connected(session_id):
        await mgr.emit_step(
            session_id,
            {
                "step_type": step_type,
                "iteration": state.get("iteration", 0),
                "current_step": state.get("current_step", ""),
                "final_answer": state.get("final_answer"),
                "pending_tool": state.get("pending_tool"),
            },
        )


def _with_cancel_check(
    coro: Any,
    state: dict,
) -> Any:
    """Wrap a coroutine to check cancel token before execution.

    The cancel token is expected in ``state.get("metadata", {}).get("session_id")``
    or in ``state["session_id"]``.
    """
    session_id = (
        state.get("metadata", {}).get("session_id")
        or state.get("session_id", "")
    )

    async def _wrapped() -> Any:
        if session_id:
            from app.harness.cancel_token import get_cancel_token

            token = get_cancel_token(session_id)
            if token:
                token.check()
        return await coro

    return _wrapped()



class _FallbackSimpleGraph:
    """Simple prompt → answer loop (no LangGraph)."""

    def __init__(self, spec: AgentSpec) -> None:
        self._spec = spec
        self._synthesize = _make_synthesize_node(spec)

    def invoke(self, state: dict) -> dict:
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self.ainvoke(state))

    async def ainvoke(self, state: dict) -> dict:
        session_id = state.get("metadata", {}).get("session_id") or state.get("session_id", "")
        current = dict(state)

        result = await _with_cancel_check(self._synthesize(current), current)
        current = {**current, **result}
        await _emit_step_event(session_id, current, "synthesize")

        # HIL: before_synthesize gate
        await _check_hil_gates(self._spec, current, session_id)

        return current


class _FallbackReActGraph:
    """Simple ReAct loop (no LangGraph)."""

    def __init__(self, spec: AgentSpec) -> None:
        from app.harness.nodes.reason import make_reason_node
        from app.harness.nodes.synthesize import make_synthesize_node
        from app.harness.nodes.tool_call import make_tool_call_node

        self._spec = spec
        self._reason = make_reason_node(spec)
        self._tool_call = make_tool_call_node()
        self._synthesize = make_synthesize_node(spec)

    def invoke(self, state: dict) -> dict:
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self.ainvoke(state))

    async def ainvoke(self, state: dict) -> dict:
        session_id = state.get("metadata", {}).get("session_id") or state.get("session_id", "")
        current = dict(state)
        max_iter = self._spec.guardrails.max_iterations

        while True:
            await _check_hil_gates(self._spec, current, session_id)

            reason_update = await _with_cancel_check(self._reason(current), current)
            current = {**current, **reason_update}
            await _emit_step_event(session_id, current, "reason")

            pending = current.get("pending_tool")
            iteration = current.get("iteration", 0)

            if not pending or not pending.get("name") or iteration >= max_iter:
                break

            tool_update = await _with_cancel_check(self._tool_call(current), current)
            current = {**current, **tool_update}
            await _emit_step_event(session_id, current, "tool_call")

        synth_update = await _with_cancel_check(self._synthesize(current), current)
        current = {**current, **synth_update}
        await _emit_step_event(session_id, current, "synthesize")
        await _check_hil_gates(self._spec, current, session_id)

        return current


class _FallbackDocumentGraph:
    """Document-aware loop with retrieval (no LangGraph)."""

    def __init__(self, spec: AgentSpec) -> None:
        from app.agents.nodes.retrieve import retrieve_node
        from app.harness.nodes.reason import make_reason_node
        from app.harness.nodes.synthesize import make_synthesize_node
        from app.harness.nodes.tool_call import make_tool_call_node

        self._spec = spec
        self._retrieve = retrieve_node
        self._reason = make_reason_node(spec)
        self._tool_call = make_tool_call_node()
        self._synthesize = make_synthesize_node(spec)

    def invoke(self, state: dict) -> dict:
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self.ainvoke(state))

    async def ainvoke(self, state: dict) -> dict:
        session_id = state.get("metadata", {}).get("session_id") or state.get("session_id", "")
        current = dict(state)
        max_iter = self._spec.guardrails.max_iterations

        retrieve_update = await _with_cancel_check(self._retrieve(current), current)
        current = {**current, **retrieve_update}
        await _emit_step_event(session_id, current, "retrieve")

        while True:
            await _check_hil_gates(self._spec, current, session_id)

            reason_update = await _with_cancel_check(self._reason(current), current)
            current = {**current, **reason_update}
            await _emit_step_event(session_id, current, "reason")

            pending = current.get("pending_tool")
            iteration = current.get("iteration", 0)

            if not pending or not pending.get("name") or iteration >= max_iter:
                break

            tool_update = await _with_cancel_check(self._tool_call(current), current)
            current = {**current, **tool_update}
            await _emit_step_event(session_id, current, "tool_call")

        synth_update = await _with_cancel_check(self._synthesize(current), current)
        current = {**current, **synth_update}
        await _emit_step_event(session_id, current, "synthesize")
        await _check_hil_gates(self._spec, current, session_id)

        return current
