"""Agent service — orchestrates agent graph execution with DB persistence.

Supports both legacy ``run(task_type, ...)`` for backward compatibility
and the new harness-based ``run_agent(agent_name, ...)`` that uses
AgentSpec + AgentRegistry.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.safety import CostTracker, MaxIterationGuard, WallClockGuard
from app.agents.state import AgentState

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Result returned by the agent service after execution.

    Attributes:
        answer: The synthesized final answer.
        steps: Ordered list of step records.
        cost: Cost summary dict.
        iterations: Number of iterations executed.
        session_id: UUID of the persisted agent session.
        status: Final status (completed, failed, timeout, cancelled).
        duration_ms: Total wall-clock duration in milliseconds.
        agent_name: Name of the agent that was executed.
    """

    answer: str
    steps: list[dict[str, Any]]
    cost: dict[str, Any]
    iterations: int
    session_id: str
    status: str = "completed"
    duration_ms: int = 0
    agent_name: str = ""


class AgentServiceError(Exception):
    """Base exception for agent service errors."""


class AgentService:
    """Execute agent tasks with safety controls and session persistence.

    This service:
    1. Resolves the AgentSpec from AgentRegistry (new flow) or uses defaults (legacy).
    2. Constructs the initial ``AgentState``.
    3. Builds and runs the agent graph (LangGraph or fallback).
    4. Persists each step as an ``AgentStep`` record.
    5. Updates the session with final results.
    6. Returns an ``AgentResult``.

    Args:
        max_iterations: Hard iteration limit (overrides AgentSpec guardrails).
        max_cost_usd: Cost abort threshold.
        max_wall_clock_seconds: Time abort threshold.
    """

    def __init__(
        self,
        max_iterations: int | None = None,
        max_cost_usd: float | None = None,
        max_wall_clock_seconds: int | None = None,
    ) -> None:
        self._max_iterations = max_iterations
        self._max_cost_usd = max_cost_usd
        self._max_wall_clock_seconds = max_wall_clock_seconds

        self.iteration_guard = MaxIterationGuard(max_iterations or 10)
        self.cost_tracker = CostTracker(max_cost_usd=max_cost_usd or 5.0)
        self.wall_clock_guard = WallClockGuard(max_seconds=max_wall_clock_seconds or 300)

    async def run_chain(
        self,
        agent_names: list[str],
        query: str,
        user_id: uuid.UUID | None = None,
        document_id: uuid.UUID | None = None,
    ) -> AgentResult:
        """Execute a sequence of agents in a chain (pipeline).

        Each agent receives the previous agent's answer as context.
        The final agent's answer is returned.

        Args:
            agent_names: Ordered list of agent names to execute.
            query: Initial input query for the first agent.
            user_id: Optional user ID for session ownership.
            document_id: Optional document ID for context.

        Returns:
            ``AgentResult`` with the aggregated answer and steps.
        """
        from app.harness.multi_agent import AgentChain

        chain = AgentChain(
            agent_names=agent_names,
            description=f"AgentService chain: {' → '.join(agent_names)}",
        )
        result = await chain.run(query=query)

        return AgentResult(
            answer=result.final_answer,
            steps=[
                {"agent_name": s.agent_name, "query": s.query, "answer": s.answer}
                for s in result.steps
            ],
            cost={},
            iterations=result.total_iterations,
            session_id=result.steps[-1].session_id if result.steps else "",
            status="completed",
            agent_name="chain",
        )

    async def run_agent(
        self,
        agent_name: str,
        input_data: dict[str, Any],
        db: AsyncSession,
        user_id: uuid.UUID | None = None,
        document_id: uuid.UUID | None = None,
    ) -> AgentResult:
        """Execute an agent by name using its AgentSpec definition.

        Looks up the agent in the AgentRegistry, resolves its tools
        and guardrails, then builds and executes the appropriate graph.

        Args:
            agent_name: Name of the registered agent (e.g. 'doc-qa', 'chat').
            input_data: Task input containing at minimum a 'query' or 'messages' key.
            db: Active async database session for persistence.
            user_id: Optional user ID for session ownership.
            document_id: Optional document ID for context.

        Returns:
            ``AgentResult`` with the answer, steps, cost, and session ID.
        """
        from app.harness.agent_registry import get_agent_registry

        registry = get_agent_registry()
        spec = registry.get(agent_name)

        guardrails = spec.guardrails
        max_iter = self._max_iterations or guardrails.max_iterations
        max_cost = self._max_cost_usd or guardrails.max_cost_usd
        max_wall_clock = self._max_wall_clock_seconds or guardrails.max_wall_clock_seconds

        return await self._execute(
            agent_name=agent_name,
            spec=spec,
            input_data=input_data,
            db=db,
            user_id=user_id,
            document_id=document_id,
            max_iterations=max_iter,
            max_cost_usd=max_cost,
            max_wall_clock_seconds=max_wall_clock,
        )

    async def run(
        self,
        task_type: str,
        input_data: dict[str, Any],
        db: AsyncSession,
        user_id: uuid.UUID | None = None,
        document_id: uuid.UUID | None = None,
    ) -> AgentResult:
        """Execute an agent task end-to-end (legacy interface).

        .. deprecated::
            Use ``run_agent(agent_name, ...)`` instead.

        Args:
            task_type: Type of agent task (e.g. 'qa', 'summarize', 'extract').
            input_data: Task input containing at minimum a 'query' or 'messages' key.
            db: Active async database session for persistence.
            user_id: Optional user ID for session ownership.
            document_id: Optional document ID for context.

        Returns:
            ``AgentResult`` with the answer, steps, cost, and session ID.
        """
        agent_name = _legacy_task_type_to_agent(task_type)

        from app.harness.agent_registry import get_agent_registry

        registry = get_agent_registry()
        if registry.has(agent_name):
            return await self.run_agent(
                agent_name=agent_name,
                input_data=input_data,
                db=db,
                user_id=user_id,
                document_id=document_id,
            )

        return await self._execute_legacy(
            task_type=task_type,
            input_data=input_data,
            db=db,
            user_id=user_id,
            document_id=document_id,
        )

    async def _execute(
        self,
        agent_name: str,
        spec: Any,
        input_data: dict[str, Any],
        db: AsyncSession,
        user_id: uuid.UUID | None,
        document_id: uuid.UUID | None,
        max_iterations: int,
        max_cost_usd: float,
        max_wall_clock_seconds: int,
    ) -> AgentResult:
        """Execute an agent using its AgentSpec.

        Constructs the initial state, builds the graph via the harness,
        runs it, and persists results.
        """
        start = time.monotonic()
        session_id = uuid.uuid4()

        self.iteration_guard = MaxIterationGuard(max_iterations)
        self.cost_tracker = CostTracker(max_cost_usd=max_cost_usd)
        self.wall_clock_guard = WallClockGuard(max_seconds=max_wall_clock_seconds)
        self.wall_clock_guard.start()

        messages = input_data.get("messages", [])
        if not messages and input_data.get("query"):
            messages = [{"role": "user", "content": input_data["query"]}]

        context = dict(input_data.get("context", {}))
        if document_id:
            context["document_id"] = str(document_id)

        initial_state = AgentState(
            messages=messages,
            context=context,
            documents=context.get("documents", []),
            current_step="init",
            iteration=0,
            max_iterations=max_iterations,
            tool_results=[],
            final_answer=None,
            metadata={
                "session_id": str(session_id),
                "agent_name": agent_name,
                "task_type": agent_name,
                "model": spec.model.model_name,
            },
            task_type=agent_name,
            pending_tool=None,
            error=None,
            steps=[],
        )

        await self._create_session(
            db=db,
            session_id=session_id,
            user_id=user_id,
            document_id=document_id,
            agent_type=agent_name,
            input_data=input_data,
        )

        try:
            from app.harness.agent_graph import build_agent_graph

            graph = build_agent_graph(spec)

            if hasattr(graph, "ainvoke"):
                final_state = await graph.ainvoke(initial_state)
            elif hasattr(graph, "invoke"):
                final_state = graph.invoke(initial_state)
            else:
                raise AgentServiceError("Agent graph has no invoke/ainvoke method")

            elapsed_ms = int((time.monotonic() - start) * 1000)

            await self._persist_steps(db=db, session_id=session_id, steps=final_state.get("steps", []))

            cost_summary = final_state.get("metadata", {}).get("cost", {})
            answer = final_state.get("final_answer", "")
            iterations = final_state.get("iteration", 0)

            await self._update_session(
                db=db,
                session_id=session_id,
                status="completed",
                output_data={
                    "answer": answer,
                    "iterations": iterations,
                    "cost": cost_summary,
                },
                total_tokens=cost_summary.get("total_tokens"),
                completed_at=datetime.now(UTC),
            )

            await db.commit()

            return AgentResult(
                answer=answer,
                steps=[s for s in final_state.get("steps", [])],
                cost=cost_summary,
                iterations=iterations,
                session_id=str(session_id),
                status="completed",
                duration_ms=elapsed_ms,
                agent_name=agent_name,
            )

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error("Agent '%s' execution failed: %s", agent_name, e, exc_info=True)

            try:
                await self._update_session(
                    db=db,
                    session_id=session_id,
                    status="failed",
                    error_message=str(e),
                    completed_at=datetime.now(UTC),
                )
                await db.commit()
            except Exception:
                logger.error("Failed to update session on error", exc_info=True)
                await db.rollback()

            return AgentResult(
                answer=f"Agent execution failed: {e}",
                steps=[],
                cost=self.cost_tracker.summary(),
                iterations=0,
                session_id=str(session_id),
                status="failed",
                duration_ms=elapsed_ms,
                agent_name=agent_name,
            )

    async def _execute_legacy(
        self,
        task_type: str,
        input_data: dict[str, Any],
        db: AsyncSession,
        user_id: uuid.UUID | None,
        document_id: uuid.UUID | None,
    ) -> AgentResult:
        """Original execution path (backward compatibility).

        Uses the hardcoded ``app.agents.graph.create_agent_graph()``
        which builds the fixed retrieve→reason→tool_call→synthesize graph.
        """
        start = time.monotonic()
        session_id = uuid.uuid4()

        self.iteration_guard = MaxIterationGuard(self._max_iterations or 10)
        self.cost_tracker = CostTracker(max_cost_usd=self._max_cost_usd or 5.0)
        self.wall_clock_guard = WallClockGuard(max_seconds=self._max_wall_clock_seconds or 300)
        self.wall_clock_guard.start()

        messages = input_data.get("messages", [])
        if not messages and input_data.get("query"):
            messages = [{"role": "user", "content": input_data["query"]}]

        initial_state = AgentState(
            messages=messages,
            context={},
            documents=[],
            current_step="init",
            iteration=0,
            max_iterations=self._max_iterations or 10,
            tool_results=[],
            final_answer=None,
            metadata={"session_id": str(session_id), "task_type": task_type},
            task_type=task_type,
            pending_tool=None,
            error=None,
            steps=[],
        )

        await self._create_session(
            db=db,
            session_id=session_id,
            user_id=user_id,
            document_id=document_id,
            agent_type=task_type,
            input_data=input_data,
        )

        try:
            from app.agents.graph import create_agent_graph

            graph = create_agent_graph()

            if hasattr(graph, "ainvoke"):
                final_state = await graph.ainvoke(initial_state)
            elif hasattr(graph, "invoke"):
                final_state = graph.invoke(initial_state)
            else:
                raise AgentServiceError("Agent graph has no invoke/ainvoke method")

            elapsed_ms = int((time.monotonic() - start) * 1000)

            await self._persist_steps(db=db, session_id=session_id, steps=final_state.get("steps", []))

            cost_summary = final_state.get("metadata", {}).get("cost", {})
            answer = final_state.get("final_answer", "")
            iterations = final_state.get("iteration", 0)

            await self._update_session(
                db=db,
                session_id=session_id,
                status="completed",
                output_data={
                    "answer": answer,
                    "iterations": iterations,
                    "cost": cost_summary,
                },
                total_tokens=cost_summary.get("total_tokens"),
                completed_at=datetime.now(UTC),
            )

            await db.commit()

            return AgentResult(
                answer=answer,
                steps=[s for s in final_state.get("steps", [])],
                cost=cost_summary,
                iterations=iterations,
                session_id=str(session_id),
                status="completed",
                duration_ms=elapsed_ms,
                agent_name=task_type,
            )

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error("Legacy agent execution failed: %s", e, exc_info=True)

            try:
                await self._update_session(
                    db=db,
                    session_id=session_id,
                    status="failed",
                    error_message=str(e),
                    completed_at=datetime.now(UTC),
                )
                await db.commit()
            except Exception:
                logger.error("Failed to update session on error", exc_info=True)
                await db.rollback()

            return AgentResult(
                answer=f"Agent execution failed: {e}",
                steps=[],
                cost=self.cost_tracker.summary(),
                iterations=0,
                session_id=str(session_id),
                status="failed",
                duration_ms=elapsed_ms,
                agent_name=task_type,
            )

    async def get_session(
        self,
        session_id: uuid.UUID,
        db: AsyncSession,
    ) -> dict[str, Any] | None:
        """Retrieve a persisted agent session with its steps.

        Args:
            session_id: UUID of the agent session.
            db: Active async database session.

        Returns:
            Dict with session data and steps, or None if not found.
        """
        from sqlalchemy import select

        from app.db.models.agent import AgentSession, AgentStep

        stmt = select(AgentSession).where(AgentSession.id == session_id)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()

        if session is None:
            return None

        steps_stmt = (
            select(AgentStep)
            .where(AgentStep.session_id == session_id)
            .order_by(AgentStep.step_index)
        )
        steps_result = await db.execute(steps_stmt)
        steps = steps_result.scalars().all()

        return {
            "session_id": str(session.id),
            "agent_type": session.agent_type,
            "status": session.status,
            "input_data": session.input_data,
            "output_data": session.output_data,
            "error_message": session.error_message,
            "model": session.model,
            "total_tokens": session.total_tokens,
            "total_cost_usd": float(session.total_cost_usd) if session.total_cost_usd else None,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "steps": [
                {
                    "step_index": s.step_index,
                    "step_type": s.step_type,
                    "action": s.action,
                    "input_data": s.input_data,
                    "output_data": s.output_data,
                    "reasoning": s.reasoning,
                    "tokens_used": s.tokens_used,
                    "duration_ms": s.duration_ms,
                    "status": s.status,
                }
                for s in steps
            ],
        }

    async def _create_session(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        user_id: uuid.UUID | None,
        document_id: uuid.UUID | None,
        agent_type: str,
        input_data: dict[str, Any],
    ) -> Any:
        """Create and persist an AgentSession record."""
        from app.db.models.agent import AgentSession

        session = AgentSession(
            id=session_id,
            user_id=user_id or uuid.UUID("00000000-0000-0000-0000-000000000001"),
            document_id=document_id,
            agent_type=agent_type,
            status="running",
            input_data=input_data,
            started_at=datetime.now(UTC),
        )
        db.add(session)
        await db.flush()
        return session

    async def _update_session(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        status: str,
        output_data: dict[str, Any] | None = None,
        error_message: str | None = None,
        total_tokens: int | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        """Update an AgentSession record."""
        from sqlalchemy import select

        from app.db.models.agent import AgentSession

        stmt = select(AgentSession).where(AgentSession.id == session_id)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()

        if session is None:
            logger.warning("Session %s not found for update", session_id)
            return

        session.status = status
        if output_data is not None:
            session.output_data = output_data
        if error_message is not None:
            session.error_message = error_message
        if total_tokens is not None:
            session.total_tokens = total_tokens
        if completed_at is not None:
            session.completed_at = completed_at

        await db.flush()

    async def _persist_steps(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        steps: list[dict[str, Any]],
    ) -> None:
        """Persist agent steps to the database."""
        from app.db.models.agent import AgentStep

        for i, step in enumerate(steps):
            step_record = AgentStep(
                session_id=session_id,
                step_index=i,
                step_type=step.get("step_type", "unknown"),
                action=step.get("output_summary", ""),
                input_data={"summary": step.get("input_summary", "")},
                output_data={"summary": step.get("output_summary", "")},
                reasoning=step.get("output_summary"),
                tokens_used=step.get("tokens_used"),
                duration_ms=step.get("duration_ms"),
                status="completed",
            )
            db.add(step_record)

        await db.flush()


def _legacy_task_type_to_agent(task_type: str) -> str:
    """Map legacy ``task_type`` values to agent names."""
    mapping = {
        "qa": "doc-qa",
        "summarize": "summarise",
        "extract": "doc-extract",
        "risk": "doc-qa",
        "chat": "chat",
    }
    return mapping.get(task_type, task_type)
