"""Agent graph — LangGraph orchestration with fallback state machine."""

from __future__ import annotations

import logging
from typing import Any, Literal

logger = logging.getLogger(__name__)

_HAS_LANGGRAPH = False
try:
    from langgraph.graph import END, START, StateGraph

    _HAS_LANGGRAPH = True
except ImportError:
    logger.warning(
        "langgraph is not installed. Using fallback state machine. "
        "Install with: pip install langgraph"
    )


def _should_call_tool(state: dict) -> Literal["tool_call", "synthesize"]:
    """Conditional edge: route to tool_call if a pending tool exists, else synthesize."""
    pending = state.get("pending_tool")
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 10)

    if iteration >= max_iterations:
        logger.info("Max iterations (%d) reached, forcing synthesize", max_iterations)
        return "synthesize"

    if pending and pending.get("name"):
        return "tool_call"

    return "synthesize"


def create_agent_graph():
    """Create and return a compiled agent graph.

    If LangGraph is available, returns a compiled ``StateGraph``.
    Otherwise, returns a ``FallbackAgentGraph`` that implements the
    same execution model with a simple loop.

    Graph topology::

        START → retrieve → reason → [tool_call | synthesize] → END
                                  ↑         |
                                  └─────────┘  (loop back to reason)

    Returns:
        A compiled graph with an ``invoke(state)`` / ``ainvoke(state)`` method.
    """
    from app.agents.nodes.reason import reason_node
    from app.agents.nodes.retrieve import retrieve_node
    from app.agents.nodes.synthesize import synthesize_node
    from app.agents.nodes.tool_call import tool_call_node
    from app.agents.state import AgentState

    if _HAS_LANGGRAPH:
        return _create_langgraph(AgentState, retrieve_node, reason_node, tool_call_node, synthesize_node)

    logger.info("Creating fallback agent graph (LangGraph not available)")
    return FallbackAgentGraph(retrieve_node, reason_node, tool_call_node, synthesize_node)


def _create_langgraph(state_type, retrieve_node, reason_node, tool_call_node, synthesize_node):
    """Build a LangGraph StateGraph."""
    graph = StateGraph(state_type)

    graph.add_node("retrieve", retrieve_node)
    graph.add_node("reason", reason_node)
    graph.add_node("tool_call", tool_call_node)
    graph.add_node("synthesize", synthesize_node)

    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "reason")
    graph.add_conditional_edges(
        "reason",
        _should_call_tool,
        {
            "tool_call": "tool_call",
            "synthesize": "synthesize",
        },
    )
    graph.add_edge("tool_call", "reason")
    graph.add_edge("synthesize", END)

    return graph.compile()


class FallbackAgentGraph:
    """Simple loop-based state machine when LangGraph is unavailable.

    Replicates the same node sequence: retrieve → reason → (tool_call|synthesize).
    After tool_call, loops back to reason. Supports both sync ``invoke``
    and async ``ainvoke``.

    Args:
        retrieve_node: Async callable for document retrieval.
        reason_node: Async callable for reasoning/decision.
        tool_call_node: Async callable for tool execution.
        synthesize_node: Async callable for answer generation.
    """

    def __init__(
        self,
        retrieve_node: Any,
        reason_node: Any,
        tool_call_node: Any,
        synthesize_node: Any,
    ) -> None:
        self._nodes = {
            "retrieve": retrieve_node,
            "reason": reason_node,
            "tool_call": tool_call_node,
            "synthesize": synthesize_node,
        }

    def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        """Synchronous execution wrapper (runs async nodes via asyncio)."""
        import asyncio

        return asyncio.get_event_loop().run_until_complete(self.ainvoke(state))

    async def ainvoke(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent graph asynchronously.

        Args:
            state: Initial ``AgentState`` dict.

        Returns:
            Final state after all nodes have executed.
        """
        current_state = dict(state)
        max_iterations = current_state.get("max_iterations", 10)

        logger.info("FallbackGraph: starting execution (max_iterations=%d)", max_iterations)

        current_state = await self._run_node("retrieve", current_state)

        while True:
            current_state = await self._run_node("reason", current_state)

            pending = current_state.get("pending_tool")
            iteration = current_state.get("iteration", 0)

            if not pending or not pending.get("name") or iteration >= max_iterations:
                break

            current_state = await self._run_node("tool_call", current_state)

        current_state = await self._run_node("synthesize", current_state)

        logger.info("FallbackGraph: execution complete")
        return current_state

    async def _run_node(self, name: str, state: dict[str, Any]) -> dict[str, Any]:
        """Execute a single node and merge its output into state."""
        node_fn = self._nodes[name]
        logger.debug("FallbackGraph: running node=%s iteration=%d", name, state.get("iteration", 0))

        update = await node_fn(state)
        merged = {**state, **update}
        return merged
