"""Tool call node — execute the selected tool with validated arguments."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.agents.state import AgentState, StepRecord, ToolResult

logger = logging.getLogger(__name__)


async def tool_call_node(state: AgentState) -> dict[str, Any]:
    """Execute the pending tool call and record the result.

    Reads ``pending_tool`` from state, validates and executes the tool
    via the registry, appends the result to ``tool_results``, and
    increments the iteration counter.

    Args:
        state: Current agent state containing ``pending_tool``.

    Returns:
        Partial state update with ``tool_results``, ``iteration``,
        ``current_step``, ``pending_tool`` (cleared), and appended ``steps``.
    """
    start = time.monotonic()
    pending = state.get("pending_tool")
    iteration = state.get("iteration", 0)

    if not pending:
        logger.warning("tool_call_node: no pending tool, skipping")
        return {
            "current_step": "tool_call",
            "pending_tool": None,
            "iteration": iteration + 1,
        }

    tool_name = pending.get("name", "")
    arguments = pending.get("arguments", {})

    logger.info("tool_call_node: executing %s(%s) iteration=%d", tool_name, arguments, iteration)

    output: Any = None
    error: str | None = None

    try:
        from app.agents.safety import LoopDetector
        from app.agents.tools.registry import get_registry

        registry = get_registry()

        loop_detector = LoopDetector(max_repeats=3)
        if loop_detector.record_call(tool_name, arguments):
            error = f"Loop detected: {tool_name} called with identical arguments too many times"
            logger.warning(error)
        else:
            result = await registry.execute_async(tool_name, arguments)
            output = result
    except Exception as e:
        error = str(e)
        logger.error("tool_call_node: tool %s failed: %s", tool_name, error)

    elapsed_ms = int((time.monotonic() - start) * 1000)

    tool_result = ToolResult(
        tool_name=tool_name,
        arguments=arguments,
        output=output,
        error=error,
        duration_ms=elapsed_ms,
        iteration=iteration,
    )

    tool_results = list(state.get("tool_results", []))
    tool_results.append(tool_result)

    steps = list(state.get("steps", []))
    steps.append(
        StepRecord(
            step_type="tool_call",
            iteration=iteration,
            input_summary=f"{tool_name}({arguments})",
            output_summary=(
                f"error={error}" if error
                else f"output={str(output)[:200]}"
            ),
            duration_ms=elapsed_ms,
        )
    )

    return {
        "tool_results": tool_results,
        "iteration": iteration + 1,
        "current_step": "tool_call",
        "pending_tool": None,
        "steps": steps,
    }
