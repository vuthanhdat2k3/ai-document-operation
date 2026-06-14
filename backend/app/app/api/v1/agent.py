"""Agent API endpoints for task execution and session history."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.agent_service import AgentResult, AgentService

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentRunRequest(BaseModel):
    """Request body for POST /agent/run."""

    task_type: str = Field(
        ...,
        description="Type of agent task",
        examples=["qa", "summarize", "extract", "risk"],
    )
    query: str | None = Field(
        None,
        description="User query (converted to messages if provided)",
    )
    messages: list[dict[str, Any]] | None = Field(
        None,
        description="Conversation messages in OpenAI format",
    )
    document_id: str | None = Field(
        None,
        description="Optional document UUID to scope the task to",
    )
    max_iterations: int = Field(
        10,
        description="Maximum agent iterations",
        ge=1,
        le=50,
    )
    metadata: dict[str, Any] | None = Field(
        None,
        description="Optional metadata to attach to the session",
    )

    def get_messages(self) -> list[dict[str, Any]]:
        """Return messages list, constructing from query if needed."""
        if self.messages:
            return self.messages
        if self.query:
            return [{"role": "user", "content": self.query}]
        raise ValueError("Either 'query' or 'messages' must be provided")


class AgentRunResponse(BaseModel):
    """Response body for POST /agent/run."""

    session_id: str
    status: str
    answer: str
    iterations: int
    cost: dict[str, Any]
    steps: list[dict[str, Any]]
    duration_ms: int


class AgentSessionResponse(BaseModel):
    """Response body for GET /agent/sessions/{session_id}."""

    session_id: str
    agent_type: str
    status: str
    input_data: dict[str, Any]
    output_data: dict[str, Any] | None
    error_message: str | None
    model: str | None
    total_tokens: int | None
    total_cost_usd: float | None
    started_at: str | None
    completed_at: str | None
    steps: list[dict[str, Any]]


CURRENT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@router.post("/run", response_model=AgentRunResponse, status_code=200)
async def run_agent_task(
    body: AgentRunRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> AgentRunResponse:
    """Execute an agent task.

    The agent will retrieve relevant documents, reason about the query,
    optionally call tools, and synthesize a final answer. The full
    execution trace is persisted as an agent session.
    """
    try:
        messages = body.get_messages()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    input_data: dict[str, Any] = {
        "messages": messages,
        "task_type": body.task_type,
    }
    if body.query:
        input_data["query"] = body.query
    if body.metadata:
        input_data["metadata"] = body.metadata

    document_id = None
    if body.document_id:
        try:
            document_id = uuid.UUID(body.document_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid document_id format: {body.document_id}",
            ) from exc

    service = AgentService(max_iterations=body.max_iterations)

    result: AgentResult = await service.run(
        task_type=body.task_type,
        input_data=input_data,
        db=db,
        user_id=CURRENT_USER_ID,
        document_id=document_id,
    )

    return AgentRunResponse(
        session_id=result.session_id,
        status=result.status,
        answer=result.answer,
        iterations=result.iterations,
        cost=result.cost,
        steps=result.steps,
        duration_ms=result.duration_ms,
    )


@router.get("/sessions/{session_id}", response_model=AgentSessionResponse)
async def get_agent_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> AgentSessionResponse:
    """Retrieve an agent session with its execution steps.

    Returns the full session history including input, output, steps,
    cost, and timing information.
    """
    service = AgentService()
    session_data = await service.get_session(session_id=session_id, db=db)

    if session_data is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return AgentSessionResponse(**session_data)
