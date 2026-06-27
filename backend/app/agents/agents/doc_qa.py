"""doc-qa — Document Q&A agent template.

This is the canonical "document operations agent".  It uses the existing
document-oriented graph nodes (retrieve → reason → tool_call → synthesize)
but defined through the harness ``AgentSpec`` so it can be discovered and
invoked via the generic agent API.
"""

from __future__ import annotations

from app.harness.agent_spec import AgentSpec

AGENT = AgentSpec.doc_qa()
