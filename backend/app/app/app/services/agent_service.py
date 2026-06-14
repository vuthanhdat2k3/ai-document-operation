"""Agent service — orchestrates agent graph execution with DB persistence."""

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
    """

    answer: str
    steps: list[dict[str, Any]]
    cost: dict[str, Any]
    iterations: int
    session_id: str
    status: str = "completed"
    duration_ms: int = 0


class AgentServiceError(Exception):
    """Base exception for agent service errors."""


class AgentService:
    """Execute agent tasks with safety controls and session persistence.

    This service:
    1. Creates an ``AgentSession`` record in the database.
    2. Constructs the initial ``AgentState``.
    3. Runs the agent graph (LangGraph or fallback).
    4. Persists each step as an ``AgentStep`` record.
    5. Updates the session with final results.
    6. Returns an ``AgentResult``.

    Args:
        max_iterations: Hard iteration limit.
        max_cost_usd: Cost abort threshold.
        max_wall_clock_seconds: Time abort threshold.
    """

    def __init__(
        self,
        max_iterations: int = 10,
        max_cost_usd: float = 5.0,
        max_wall_clock_seconds: int = 300,
    ) -> None:
        self.max_iterations = max_iterations
        self.iteration_guard = MaxIterationGuard(max_iterations)
        self.cost_tracker = CostTracker(max_cost_usd=max_cost_usd)
        self.wall_clock_guard = WallClockGuard(max_seconds=max_wall_clock_seconds)

    async def run(
        self,
        task_type: str,
        input_data: dict[str, Any],
        db: AsyncSession,
        user_id: uuid.UUID | None = None,
        document_id: uuid.UUID | None = None,
    ) -> AgentResult:
        """Execute an agent task end-to-end.

        Args:
            task_type: Type of agent task (e.g. 'qa', 'summarize', 'extract').
            input_data: Task input containing at minimum a 'query' or 'messages' key.
            db: Active async database session for persistence.
            user_id: Optional user ID for session ownership.
            document_id: Optional document ID for context.

        Returns:
            ``AgentResult`` with the answer, steps, cost, and session ID.
        """
        start = time.monotonic()
        session_id = uuid.uuid4()
        self.wall_clock_guard.start()

        messages = input_data.get("messages", [])
        if not messages and input_data.get("query"):
            messages = [{"role": "user", "content": input_data["query"]}]

        initial_state = AgentState(
            messages=messages,
            documents=[],
            current_step="init",
            iteration=0,
            max_iterations=self.max_iterations,
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
            )

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error("Agent execution failed: %s", e, exc_info=True)

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
