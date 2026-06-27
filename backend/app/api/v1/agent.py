"""Agent API endpoints for task execution and session history."""

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user_id
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


    

class AgentInfoResponse(BaseModel):
    """Agent summary returned by GET /v1/agents."""

    name: str
    description: str
    version: str
    tools: list[str]
    model: str
    category: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentRunByNameRequest(BaseModel):
    """Request body for POST /v1/agents/{name}/run."""

    query: str | None = Field(None, description="User query")
    messages: list[dict[str, Any]] | None = Field(
        None, description="Conversation messages in OpenAI format"
    )
    document_id: str | None = Field(
        None, description="Optional document UUID to scope the task to"
    )
    context: dict[str, Any] | None = Field(
        None, description="Optional generic context dict"
    )
    max_iterations: int | None = Field(
        None, description="Override max iterations", ge=1, le=200
    )
    metadata: dict[str, Any] | None = Field(
        None, description="Optional metadata to attach to the session"
    )

    def get_messages(self) -> list[dict[str, Any]]:
        """Return messages list, constructing from query if needed."""
        if self.messages:
            return self.messages
        if self.query:
            return [{"role": "user", "content": self.query}]
        raise ValueError("Either 'query' or 'messages' must be provided")


@router.get("", response_model=list[AgentInfoResponse])
async def list_agents() -> list[AgentInfoResponse]:
    """List all registered agents with their capabilities."""
    from app.harness.agent_registry import get_agent_registry

    registry = get_agent_registry()
    return [
        AgentInfoResponse(
            name=s.name,
            description=s.description,
            version=s.version,
            tools=list(s.tools),
            model=s.model.model_name,
            category=s.metadata.get("category", ""),
            metadata=s.metadata,
        )
        for s in registry.list_agents()
    ]


@router.get("/{agent_name}", response_model=AgentInfoResponse)
async def get_agent_info(agent_name: str) -> AgentInfoResponse:
    """Get detailed information about a specific agent."""
    from app.harness.agent_registry import get_agent_registry

    registry = get_agent_registry()
    try:
        spec = registry.get(agent_name)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return AgentInfoResponse(
        name=spec.name,
        description=spec.description,
        version=spec.version,
        tools=list(spec.tools),
        model=spec.model.model_name,
        category=spec.metadata.get("category", ""),
        metadata=spec.metadata,
    )


@router.post("/{agent_name}/run", response_model=AgentRunResponse, status_code=200)
async def run_named_agent(
    agent_name: str,
    body: AgentRunByNameRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),
) -> AgentRunResponse:
    """Execute a named agent from the registry.

    The agent is looked up by name in the AgentRegistry, then its
    AgentSpec is used to build and execute the appropriate graph.
    """
    from app.services.agent_service import AgentService

    try:
        messages = body.get_messages()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    input_data: dict[str, Any] = {
        "messages": messages,
    }
    if body.query:
        input_data["query"] = body.query
    if body.context:
        input_data["context"] = body.context
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

    result = await service.run_agent(
        agent_name=agent_name,
        input_data=input_data,
        db=db,
        user_id=user_id,
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


class AgentSessionListItem(BaseModel):
    """Summary item for GET /agent/sessions list."""

    id: str
    agent_type: str
    status: str
    total_tokens: int | None = None
    total_cost_usd: float | None = None
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str | None = None


class AgentSessionListResponse(BaseModel):
    """Response for GET /agent/sessions."""

    items: list[AgentSessionListItem]
    total: int


@router.get("/sessions", response_model=AgentSessionListResponse)
async def list_agent_sessions(
    limit: int = 50,
    offset: int = 0,
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> AgentSessionListResponse:
    """List recent agent sessions for the current user."""
    from sqlalchemy import func, select as sa_select

    from app.db.models.agent import AgentSession as AgentSessionModel

    stmt = (
        sa_select(AgentSessionModel)
        .where(AgentSessionModel.user_id == user_id)
        .order_by(AgentSessionModel.started_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    sessions = result.scalars().all()

    count_stmt = (
        sa_select(func.count())
        .select_from(AgentSessionModel)
        .where(AgentSessionModel.user_id == user_id)
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    items = [
        AgentSessionListItem(
            id=str(s.id),
            agent_type=s.agent_type,
            status=s.status,
            total_tokens=s.total_tokens,
            total_cost_usd=float(s.total_cost_usd) if s.total_cost_usd else None,
            started_at=s.started_at.isoformat() if s.started_at else None,
            completed_at=s.completed_at.isoformat() if s.completed_at else None,
            created_at=s.created_at.isoformat() if s.created_at else None,
        )
        for s in sessions
    ]

    return AgentSessionListResponse(items=items, total=total)


@router.post("/run", response_model=AgentRunResponse, status_code=200)
async def run_agent_task(
    body: AgentRunRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
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
        user_id=user_id,
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
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> AgentSessionResponse:
    """Retrieve an agent session with its execution steps (must own the session)."""
    service = AgentService()
    session_data = await service.get_session(session_id=session_id, db=db)
    if session_data is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    if session_data.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return AgentSessionResponse(**session_data)


# ── Multi-agent endpoints ───────────────────────────────────────────────


class ChainRunRequest(BaseModel):
    agent_names: list[str] = Field(
        ..., description="Ordered list of agent names to execute in sequence", min_length=1
    )
    query: str = Field(..., description="Initial query for the first agent")
    description: str | None = Field(None, description="Optional chain description")


class ChainStepResponse(BaseModel):
    agent_name: str
    query: str
    answer: str
    session_id: str = ""
    iterations: int = 0
    status: str = "completed"
    error: str | None = None


class ChainRunResponse(BaseModel):
    steps: list[ChainStepResponse]
    final_answer: str
    total_iterations: int = 0


@router.post("/chain/run", response_model=ChainRunResponse)
async def run_agent_chain(body: ChainRunRequest) -> ChainRunResponse:
    from app.harness.multi_agent import AgentChain

    chain = AgentChain(
        agent_names=body.agent_names,
        description=body.description or "",
    )
    result = await chain.run(query=body.query)

    return ChainRunResponse(
        steps=[
            ChainStepResponse(
                agent_name=s.agent_name,
                query=s.query,
                answer=s.answer,
                session_id=s.session_id,
                iterations=s.iterations,
                status=s.status,
                error=s.error,
            )
            for s in result.steps
        ],
        final_answer=result.final_answer,
        total_iterations=result.total_iterations,
    )


class ParallelRunRequest(BaseModel):
    agent_names: list[str] = Field(
        ..., description="List of agent names to execute in parallel", min_length=1
    )
    query: str = Field(..., description="Query to send to all agents")


@router.post("/parallel/run", response_model=ChainRunResponse)
async def run_agent_parallel(body: ParallelRunRequest) -> ChainRunResponse:
    from app.harness.multi_agent import ParallelAgentGroup

    group = ParallelAgentGroup(agent_names=body.agent_names)
    result = await group.run(query=body.query)

    return ChainRunResponse(
        steps=[
            ChainStepResponse(
                agent_name=s.agent_name,
                query=s.query,
                answer=s.answer,
                session_id=s.session_id,
                iterations=s.iterations,
                status=s.status,
                error=s.error,
            )
            for s in result.steps
        ],
        final_answer=result.final_answer,
        total_iterations=result.total_iterations,
    )


class RouteRunRequest(BaseModel):
    query: str = Field(..., description="Query to route to the best agent")


@router.post("/sessions/{session_id}/cancel", status_code=200)
async def cancel_agent_session(
    session_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    """Request cancellation of a running agent session (must own the session).

    Uses the session's ``CancelToken`` to cooperatively stop execution.
    The session status will be updated to ``cancelled`` when the graph
    loop checks the cancellation flag.
    """
    from app.harness.cancel_token import cancel_session, get_cancel_token
    from sqlalchemy import select
    from app.db.models.agent import AgentSession as AgentSessionModel

    # Verify ownership
    stmt = select(AgentSessionModel).where(
        AgentSessionModel.id == session_id,
        AgentSessionModel.user_id == user_id,
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if session.status not in ("running", "paused"):
        raise HTTPException(status_code=409, detail=f"Session is {session.status}, cannot cancel")

    cancelled = cancel_session(str(session_id))
    if not cancelled:
        # No CancelToken — update status directly
        from app.services.agent_service import AgentService
        svc = AgentService()
        await svc._update_session(
            db=db,
            session_id=session_id,
            status="cancelled",
            error_message="Cancelled by user",
            completed_at=datetime.now(UTC),
        )
        await db.commit()
        from app.harness.event_manager import get_event_manager
        await get_event_manager().emit_cancelled(str(session_id))

    return {"session_id": str(session_id), "status": "cancelled", "message": "Cancellation requested"}


# ── Human-in-the-loop endpoints ─────────────────────────────────────────


class HILApproveRequest(BaseModel):
    reason: str = Field("", description="Optional reason / feedback")


@router.get("/hil/pending", response_model=list[dict[str, Any]])
async def list_pending_hil() -> list[dict[str, Any]]:
    """List all pending human-in-the-loop requests."""
    from app.harness.hil_service import get_hil_service
    return get_hil_service().list_pending()


@router.post("/hil/{hil_id}/approve", status_code=200)
async def approve_hil(
    hil_id: str,
    body: HILApproveRequest = HILApproveRequest(),
) -> dict:
    """Approve a pending HIL request, resuming agent execution."""
    from app.harness.hil_service import HILNotFoundError, get_hil_service

    try:
        request = await get_hil_service().approve(hil_id, reason=body.reason)
    except HILNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    # Notify WebSocket clients
    session_id = request.get("session_id", "")
    if session_id:
        from app.harness.event_manager import get_event_manager
        await get_event_manager().emit_step(
            session_id,
            {"event": "hil_resolved", "hil_id": hil_id, "decision": "approved"},
        )

    return {"hil_id": hil_id, "status": "approved"}


@router.post("/hil/{hil_id}/reject", status_code=200)
async def reject_hil(
    hil_id: str,
    body: HILApproveRequest = HILApproveRequest(),
) -> dict:
    """Reject a pending HIL request, resuming agent execution with feedback."""
    from app.harness.hil_service import HILNotFoundError, get_hil_service

    try:
        request = await get_hil_service().reject(hil_id, reason=body.reason)
    except HILNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    session_id = request.get("session_id", "")
    if session_id:
        from app.harness.event_manager import get_event_manager
        await get_event_manager().emit_step(
            session_id,
            {"event": "hil_resolved", "hil_id": hil_id, "decision": "rejected"},
        )

    return {"hil_id": hil_id, "status": "rejected"}


# ── WebSocket streaming endpoint ─────────────────────────────────────────


@router.websocket("/sessions/{session_id}/stream")
async def stream_agent_session(
    websocket: WebSocket,
    session_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> None:
    """WebSocket endpoint for real-time agent execution streaming.

    Connects to the event manager for the given session and forwards
    all events (steps, HIL requests, errors, completion) to the client.

    Protocol::

        Server → Client:  JSON event objects
        Client → Server:  ``{"type": "ping"}`` (keepalive)

    Event format::

        {
            "event": "step" | "hil_request" | "error" | "completed" | "cancelled" | "paused",
            "session_id": "...",
            "timestamp": 1234567890.123,
            "data": { ... }
        }
    """
    from app.harness.event_manager import get_event_manager

    await websocket.accept()
    mgr = get_event_manager()
    await mgr.connect(session_id, websocket)

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                msg = json.loads(data) if data.strip() else {}
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break
            except Exception:
                break
    finally:
        mgr.disconnect(session_id, websocket)
        try:
            await websocket.close()
        except Exception:
            pass
