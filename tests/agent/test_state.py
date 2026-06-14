"""Tests for AgentState TypedDict creation and field access."""

from __future__ import annotations

from app.agents.state import AgentState, StepRecord, ToolResult


class TestToolResult:
    """ToolResult TypedDict."""

    def test_create_full(self) -> None:
        tr: ToolResult = {
            "tool_name": "search",
            "arguments": {"query": "test"},
            "output": [{"id": 1}],
            "error": None,
            "duration_ms": 150,
            "iteration": 0,
        }
        assert tr["tool_name"] == "search"
        assert tr["arguments"] == {"query": "test"}
        assert tr["output"] == [{"id": 1}]
        assert tr["error"] is None
        assert tr["duration_ms"] == 150
        assert tr["iteration"] == 0

    def test_with_error(self) -> None:
        tr: ToolResult = {
            "tool_name": "fail_tool",
            "arguments": {},
            "output": None,
            "error": "ValueError: bad input",
            "duration_ms": 50,
            "iteration": 2,
        }
        assert tr["error"] == "ValueError: bad input"


class TestStepRecord:
    """StepRecord TypedDict."""

    def test_create_minimal(self) -> None:
        sr: StepRecord = {
            "step_type": "retrieve",
            "iteration": 0,
            "input_summary": "search query",
            "output_summary": "5 documents found",
            "duration_ms": 200,
        }
        assert sr["step_type"] == "retrieve"
        assert sr["iteration"] == 0

    def test_all_step_types(self) -> None:
        for st in ("retrieve", "reason", "tool_call", "synthesize"):
            sr: StepRecord = {
                "step_type": st,  # type: ignore[assignment]
                "iteration": 0,
                "input_summary": "",
                "output_summary": "",
                "duration_ms": 0,
            }
            assert sr["step_type"] == st

    def test_with_optional_tokens(self) -> None:
        sr: StepRecord = {
            "step_type": "reason",
            "iteration": 1,
            "input_summary": "analyzing",
            "output_summary": "analysis complete",
            "duration_ms": 500,
            "tokens_used": 1500,
        }
        assert sr["tokens_used"] == 1500


class TestAgentState:
    """AgentState TypedDict creation and field access."""

    def _make_state(self, **overrides) -> AgentState:
        defaults: AgentState = {
            "messages": [],
            "documents": [],
            "current_step": "retrieve",
            "iteration": 0,
            "max_iterations": 10,
            "tool_results": [],
            "final_answer": None,
            "metadata": {},
            "task_type": "qa",
            "pending_tool": None,
            "error": None,
            "steps": [],
        }
        defaults.update(overrides)
        return defaults

    def test_create_default(self) -> None:
        state = self._make_state()
        assert state["current_step"] == "retrieve"
        assert state["iteration"] == 0
        assert state["max_iterations"] == 10
        assert state["task_type"] == "qa"
        assert state["final_answer"] is None
        assert state["error"] is None

    def test_messages_field(self) -> None:
        state = self._make_state(messages=[
            {"role": "user", "content": "What is the penalty?"},
            {"role": "assistant", "content": "The penalty is $500."},
        ])
        assert len(state["messages"]) == 2
        assert state["messages"][0]["role"] == "user"

    def test_documents_field(self) -> None:
        docs = [{"chunk_id": "c1", "text": "some text", "score": 0.9}]
        state = self._make_state(documents=docs)
        assert len(state["documents"]) == 1
        assert state["documents"][0]["score"] == 0.9

    def test_tool_results_field(self) -> None:
        tr: ToolResult = {
            "tool_name": "search",
            "arguments": {"q": "test"},
            "output": [],
            "error": None,
            "duration_ms": 100,
            "iteration": 0,
        }
        state = self._make_state(tool_results=[tr])
        assert len(state["tool_results"]) == 1
        assert state["tool_results"][0]["tool_name"] == "search"

    def test_final_answer_field(self) -> None:
        state = self._make_state(final_answer="The penalty is $500.")
        assert state["final_answer"] == "The penalty is $500."

    def test_metadata_field(self) -> None:
        state = self._make_state(metadata={
            "session_id": "abc-123",
            "user_id": "user-1",
            "total_cost_usd": 0.05,
        })
        assert state["metadata"]["session_id"] == "abc-123"
        assert state["metadata"]["total_cost_usd"] == 0.05

    def test_pending_tool_field(self) -> None:
        state = self._make_state(pending_tool={"name": "search", "arguments": {"q": "test"}})
        assert state["pending_tool"]["name"] == "search"

    def test_error_field(self) -> None:
        state = self._make_state(error="Something went wrong")
        assert state["error"] == "Something went wrong"

    def test_steps_field(self) -> None:
        sr: StepRecord = {
            "step_type": "retrieve",
            "iteration": 0,
            "input_summary": "query",
            "output_summary": "results",
            "duration_ms": 100,
        }
        state = self._make_state(steps=[sr])
        assert len(state["steps"]) == 1
        assert state["steps"][0]["step_type"] == "retrieve"

    def test_iteration_increment(self) -> None:
        state = self._make_state()
        state["iteration"] += 1
        assert state["iteration"] == 1

    def test_state_mutation(self) -> None:
        state = self._make_state()
        state["current_step"] = "synthesize"
        state["final_answer"] = "Done."
        assert state["current_step"] == "synthesize"
        assert state["final_answer"] == "Done."

    def test_task_types(self) -> None:
        for task in ("qa", "summarize", "extract", "risk"):
            state = self._make_state(task_type=task)
            assert state["task_type"] == task
