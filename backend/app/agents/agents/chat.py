"""chat — General-purpose conversational agent template.

A minimal agent with no tools.  Single-turn LLM call without retrieval
or tool execution.  Useful as a reference for custom agent definitions.
"""

from __future__ import annotations

from app.harness.agent_spec import AgentSpec

AGENT = AgentSpec.chat()
