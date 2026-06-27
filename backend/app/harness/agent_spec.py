"""Declarative agent specification models.

AgentSpec defines *what an agent is* — its identity, system prompt, tools,
model configuration, guardrails, and schemas.  All concrete agent templates
instantiate an AgentSpec.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class MemoryConfig(BaseModel):
    """Conversation memory configuration.

    Attributes:
        window_size: Number of recent messages to keep in context.
        enable_summarization: If True, summarize older messages beyond window_size.
        max_history_tokens: Max tokens for the full conversation history.
    """

    window_size: int = Field(
        default=10,
        ge=1,
        description="Number of recent messages to keep in context",
    )
    enable_summarization: bool = Field(
        default=False,
        description="Summarize older messages beyond window_size",
    )
    max_history_tokens: int = Field(
        default=4096,
        ge=256,
        description="Max tokens for conversation history",
    )


class AgentHooks(BaseModel):
    """Before/after execution hooks configuration.

    Attributes:
        before_execution: Optional prompt or action to run before agent execution.
        after_execution: Optional prompt or action to run after agent execution.
        on_error: Optional prompt or action to run on agent error.
    """

    before_execution: str | None = Field(
        default=None,
        description="Prompt or action to run before agent execution",
    )
    after_execution: str | None = Field(
        default=None,
        description="Prompt or action to run after agent execution",
    )
    on_error: str | None = Field(
        default=None,
        description="Prompt or action to run on agent error",
    )


class ModelConfig(BaseModel):
    """LLM model configuration for an agent.

    Attributes:
        provider: LLM provider name (openai, anthropic, xiaomi, local).
        model_name: Specific model identifier (gpt-4o, claude-3-5-sonnet, …).
        temperature: Sampling temperature (0.0 = deterministic).
        max_tokens: Maximum output tokens per LLM call.
        timeout: Request timeout in seconds.
        stream: Whether to enable streaming responses.
    """

    provider: str = Field(
        default="openai",
        description="LLM provider name: openai, anthropic, xiaomi, local",
    )
    model_name: str = Field(
        default="gpt-4o",
        description="Model identifier (gpt-4o, claude-3-5-sonnet, …)",
    )
    temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Sampling temperature",
    )
    max_tokens: int = Field(
        default=4096,
        ge=1,
        description="Maximum output tokens",
    )
    timeout: int = Field(
        default=60,
        ge=1,
        description="Request timeout in seconds",
    )
    stream: bool = Field(
        default=True,
        description="Enable streaming responses",
    )


class HILGateConfig(BaseModel):
    """Human-in-the-loop gate configuration.

    Defines a condition where agent execution pauses for human input.

    Attributes:
        gate_type: What kind of gate (approval, review, confirmation).
        trigger_condition: When to pause (before_tool_call, before_synthesize, on_high_risk).
        timeout_seconds: Max wait for human before fallback.
        on_timeout_action: What to do if human doesn't respond (continue, fail, fallback).
    """

    gate_type: Literal["approval", "review", "confirmation"] = Field(
        ..., description="Type of human-in-the-loop gate"
    )
    trigger_condition: str = Field(
        ..., description="When to trigger the gate, e.g. 'before_tool_call', 'on_high_risk'"
    )
    timeout_seconds: int = Field(
        default=300,
        ge=30,
        description="Max wait for human input",
    )
    on_timeout_action: Literal["continue", "fail", "fallback"] = Field(
        default="continue",
        description="Action when human does not respond",
    )


class GuardrailConfig(BaseModel):
    """Safety and budget limits for an agent run.

    Attributes:
        max_iterations: Hard cap on reasoning-tool-call cycles.
        max_cost_usd: Abort when cumulative LLM cost exceeds this.
        max_wall_clock_seconds: Abort when wall-clock time exceeds this.
        max_tool_repeats: Number of identical tool calls before loop detection fires.
        hil_gates: Human-in-the-loop gates to enforce during execution.
    """

    max_iterations: int = Field(
        default=10,
        ge=1,
        le=200,
        description="Maximum reasoning-tool cycles",
    )
    max_cost_usd: float = Field(
        default=5.0,
        ge=0,
        description="Cost abort threshold in USD",
    )
    max_wall_clock_seconds: int = Field(
        default=300,
        ge=1,
        description="Wall-clock abort threshold",
    )
    max_tool_repeats: int = Field(
        default=3,
        ge=0,
        description="Loop detection threshold (0 = disabled)",
    )
    hil_gates: list[HILGateConfig] = Field(
        default_factory=list,
        description="Human-in-the-loop gates",
    )


class AgentSpec(BaseModel):
    """Declarative definition of an agent.

    This is the core abstraction of the harness.  Every agent — whether
    built-in (doc-qa, chat, summarise) or user-defined — is an AgentSpec.

    Attributes:
        name: Unique agent identifier (e.g. 'doc-qa', 'code-review').
        description: Human-readable description of the agent's capability.
        version: Semantic version of this agent definition.
        system_prompt: The system prompt that defines the agent's persona.
        tools: List of tool names this agent can invoke (registered in ToolRegistry).
        model: LLM model configuration.
        guardrails: Safety and budget limits.
        input_schema: Optional Pydantic model for validating run input.
        output_schema: Optional Pydantic model for validating output.
        allowed_edges: List of agent names this agent can delegate to (for multi-agent).
        metadata: Arbitrary key-value metadata (cost centre, owner, …).
    """

    name: str = Field(
        ..., description="Unique agent identifier, e.g. 'doc-qa'", pattern=r"^[a-z][a-z0-9_-]{1,63}$"
    )
    description: str = Field(
        default="", description="Human-readable capability description"
    )
    version: str = Field(
        default="1.0.0", description="Semantic version"
    )
    system_prompt: str = Field(
        ..., description="System prompt defining agent persona and behaviour"
    )
    tools: list[str] = Field(
        default_factory=list,
        description="Tool names this agent can invoke",
    )
    model: ModelConfig = Field(
        default_factory=ModelConfig,
        description="LLM model configuration",
    )
    guardrails: GuardrailConfig = Field(
        default_factory=GuardrailConfig,
        description="Safety and budget limits",
    )
    input_schema: type[BaseModel] | None = Field(
        default=None,
        exclude=True,
        description="Optional Pydantic model for run input validation",
    )
    output_schema: type[BaseModel] | None = Field(
        default=None,
        exclude=True,
        description="Optional Pydantic model for output validation",
    )
    allowed_edges: list[str] = Field(
        default_factory=list,
        description="Agent names this agent can delegate/handoff to",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary metadata (owner, cost centre, tags, …)",
    )
    planner_prompt: str | None = Field(
        default=None,
        description="Custom prompt for the Plan node. If None, planning is skipped.",
    )
    memory_config: MemoryConfig = Field(
        default_factory=MemoryConfig,
        description="Conversation memory settings",
    )
    hooks: AgentHooks = Field(
        default_factory=AgentHooks,
        description="Before/after execution hooks",
    )

    def model_post_init(self, __context: Any) -> None:
        """Validate that tool names exist (soft check — warns only)."""
        if self.tools:
            try:
                from app.agents.tools.registry import get_registry

                registry = get_registry()
                for tool_name in self.tools:
                    if not registry.has(tool_name):
                        import logging

                        logging.getLogger(__name__).warning(
                            "AgentSpec '%s' references unknown tool '%s'",
                            self.name,
                            tool_name,
                        )
            except ImportError:
                pass  # registry not available during import

    def validate_input(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate run input against input_schema if defined.

        Args:
            data: Raw input dictionary.

        Returns:
            Validated data (may be transformed by Pydantic).
        """
        if self.input_schema is None:
            return data
        return self.input_schema(**data).model_dump()

    # ── built-in agent spec factories ──────────────────────────────────────

    @classmethod
    def doc_qa(cls) -> AgentSpec:
        """Built-in document Q&A agent template."""
        from app.config import get_settings

        _settings = get_settings()
        return cls(
            name="doc-qa",
            model=ModelConfig(model_name=_settings.LLM_MODEL),
            description=(
                "Answer questions over the document corpus using hybrid "
                "retrieval (dense + sparse).  Supports contract analysis, "
                "clause lookup, deadline queries, and risk identification."
            ),
            version="1.0.0",
            system_prompt=(
                "You are a document operations agent. "
                "Given the user query, decide whether you need information "
                "from uploaded documents or can answer directly.\n\n"
                "Available tools:\n{tools}\n\n"
                "You must respond with a JSON object in one of two formats:\n\n"
                "1. To call a tool:\n"
                '  {{"action": "tool_call", "tool_name": "<name>", "arguments": {{...}}}}\n\n'
                "2. To generate the final answer:\n"
                '  {{"action": "synthesize", "reasoning": "<why no more tools are needed>"}}\n\n'
                "Rules:\n"
                "- Only use tools that are listed above.\n"
                "- If the user asks a general question (not about documents), "
                "choose 'synthesize' and answer using your own knowledge.\n"
                "- If the question requires document content — contracts, "
                "invoices, policies, reports, deadlines, clauses — call "
                "the 'rag_query' tool to search and analyse the document corpus.\n"
                "- Do not call the same tool with the same arguments more than once.\n"
                "- Keep tool arguments minimal and focused.\n"
            ),
            tools=["rag_query", "get_document_info"],
            planner_prompt=(
                "Analyse the user's query and create a step-by-step plan. "
                "Each step should use one of the available tools.\n\n"
                "Available tools:\n{tools}\n\n"
                "Respond with a JSON object:\n"
                '{{"plan": [{{"step": 1, "tool": "<tool_name>", "args": {{...}}, "reason": "..."}}, ...]}}\n\n'
                "Rules:\n"
                "- If the query is about document content, plan to call 'rag_query'.\n"
                "- If you need document metadata, plan to call 'get_document_info'.\n"
                "- If the query is general conversation, return an empty plan.\n"
            ),
            guardrails=GuardrailConfig(
                max_iterations=10,
                max_cost_usd=5.0,
                max_wall_clock_seconds=300,
                max_tool_repeats=3,
            ),
            metadata={"category": "document", "owner": "platform"},
        )

    @classmethod
    def chat(cls) -> AgentSpec:
        """Simple conversational agent with no tools."""
        from app.config import get_settings

        _settings = get_settings()
        return cls(
            name="chat",
            model=ModelConfig(model_name=_settings.LLM_MODEL),
            description=(
                "General-purpose conversational agent.  No external tools — "
                "uses only the LLM's built-in knowledge."
            ),
            version="1.0.0",
            system_prompt=(
                "You are a helpful AI assistant. Answer the user's questions "
                "concisely and accurately using your built-in knowledge.\n\n"
                "If you don't know something, say so — do not make up information."
            ),
            tools=[],
            guardrails=GuardrailConfig(
                max_iterations=1,
                max_cost_usd=1.0,
                max_wall_clock_seconds=120,
                max_tool_repeats=0,
            ),
            metadata={"category": "general", "owner": "platform"},
        )

    @classmethod
    def summarise(cls) -> AgentSpec:
        """Document summarisation agent."""
        from app.config import get_settings

        _settings = get_settings()
        return cls(
            name="summarise",
            model=ModelConfig(model_name=_settings.LLM_MODEL),
            description=(
                "Generate concise, structured summaries of documents. "
                "Extracts key points, decisions, deadlines, and action items."
            ),
            version="1.0.0",
            system_prompt=(
                "You are a document summarisation agent. "
                "First, retrieve document content using the 'rag_query' tool, "
                "then produce a structured summary covering: key points, "
                "decisions made, deadlines identified, action items, and "
                "risks or concerns.\n\n"
                "Available tools:\n{tools}\n\n"
                "Respond in the same JSON format: "
                '{{"action": "tool_call"|"synthesize", ...}}'
            ),
            tools=["rag_query", "get_document_info"],
            guardrails=GuardrailConfig(
                max_iterations=5,
                max_cost_usd=3.0,
                max_wall_clock_seconds=240,
                max_tool_repeats=2,
            ),
            metadata={"category": "document", "owner": "platform"},
        )
