"""Agent state schema for LangGraph orchestration."""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


class ToolResult(TypedDict):
    """Result from a single tool invocation."""

    tool_name: str
    arguments: dict[str, Any]
    output: Any
    error: str | None
    duration_ms: int
    iteration: int


class StepRecord(TypedDict):
    """Record of a single agent step for observability."""

    step_type: Literal["retrieve", "reason", "tool_call", "synthesize"]
    iteration: int
    input_summary: str
    output_summary: str
    duration_ms: int
    tokens_used: NotRequired[int]


class AgentState(TypedDict):
    """State schema passed between nodes in the agent graph.

    All nodes receive and return this state. Fields are additive — nodes
    should only modify fields they own and leave others untouched.
    """

    messages: list[dict[str, Any]]
    """Conversation messages in OpenAI format (role/content)."""

    documents: list[dict[str, Any]]
    """Retrieved document chunks from the retrieve node."""

    current_step: str
    """Name of the step currently executing or last completed."""

    iteration: int
    """Current iteration count (0-indexed)."""

    max_iterations: int
    """Hard cap on iterations before forced synthesis."""

    tool_results: list[ToolResult]
    """Accumulated results from tool invocations."""

    final_answer: str | None
    """Synthesized answer produced by the synthesize node."""

    metadata: dict[str, Any]
    """Arbitrary metadata: session_id, user_id, cost tracking, etc."""

    task_type: str
    """Type of agent task (e.g. 'qa', 'summarize', 'extract', 'risk')."""

    pending_tool: dict[str, Any] | None
    """Tool call pending execution: {name, arguments} or None."""

    error: str | None
    """Error message if a node failed; triggers fallback routing."""

    steps: list[StepRecord]
    """Ordered list of step records for session history."""
