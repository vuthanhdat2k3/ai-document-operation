"""router — Intelligent request routing agent.

Analyses the user's query, decides which specialist agent (doc-qa, chat,
summarise, …) is best suited, delegates via ``delegate_to_agent``, and
returns the specialist's answer.
"""

from __future__ import annotations

from app.config import get_settings
from app.harness.agent_spec import AgentSpec, GuardrailConfig, ModelConfig

AGENT = AgentSpec(
    name="router",
    description=(
        "Intelligent request router. Analyses your query and routes it to "
        "the best specialist agent. Supports document Q&A, summarisation, "
        "general chat, and more."
    ),
    version="1.0.0",
    system_prompt=(
        "You are an intelligent request router. Your job is to:\n\n"
        "1. Analyse the user's query.\n"
        "2. Decide which specialist agent can best handle it.\n"
        "3. Call the ``delegate_to_agent`` tool with the chosen agent name.\n"
        "4. Return the specialist's answer to the user.\n\n"
        "Available agents (use these as the ``agent_name`` parameter):\n"
        "  - doc-qa: Answer questions using the document corpus (contracts, invoices, etc.)\n"
        "  - summarise: Generate structured summaries of documents\n"
        "  - chat: General conversation without any external tools\n\n"
        "Rules:\n"
        "- Always use the ``delegate_to_agent`` tool — never try to answer directly.\n"
        "- If the query is about documents, contracts, invoices, or data extraction, "
        "use 'doc-qa'.\n"
        "- If the query asks for a summary, use 'summarise'.\n"
        "- For general conversation, questions, or anything not document-related, "
        "use 'chat'.\n"
        "- Return the specialist's answer verbatim.\n"
        "- Luôn trả lời bằng tiếng Việt.\n"
    ),
    tools=["delegate_to_agent"],
    model=ModelConfig(
        provider="openai",
        model_name=get_settings().LLM_MODEL,
        temperature=0.0,
        max_tokens=2048,
    ),
    guardrails=GuardrailConfig(
        max_iterations=3,
        max_cost_usd=2.0,
        max_wall_clock_seconds=120,
        max_tool_repeats=2,
    ),
    metadata={"category": "routing", "owner": "platform"},
)
