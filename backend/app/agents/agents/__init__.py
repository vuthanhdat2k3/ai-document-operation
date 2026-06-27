"""Built-in agent templates.

Each module exposes an ``AGENT`` attribute (an ``AgentSpec`` instance) that
is registered with the global ``AgentRegistry`` during startup.
"""

from __future__ import annotations

import logging

from app.harness.agent_registry import get_agent_registry

logger = logging.getLogger(__name__)

_TEMPLATE_MODULES: list[tuple[str, str]] = [
    ("app.agents.agents.doc_qa", "doc-qa"),
    ("app.agents.agents.chat", "chat"),
    ("app.agents.agents.summarise", "summarise"),
    ("app.agents.agents.router", "router"),
]


def load_builtin_agents() -> None:
    """Register all built-in agent templates with the global AgentRegistry.

    Call this once during application startup.
    """
    registry = get_agent_registry()

    for module_path, spec_name in _TEMPLATE_MODULES:
        if registry.has(spec_name):
            continue
        try:
            import importlib

            mod = importlib.import_module(module_path)
            spec = getattr(mod, "AGENT", None)
            if spec is not None:
                registry.register(spec)
                logger.info("Loaded built-in agent: %s", spec_name)
            else:
                logger.warning("Agent template %s has no AGENT attribute", module_path)
        except Exception:
            logger.exception("Failed to load built-in agent %s from %s", spec_name, module_path)

    loaded = [s.name for s in registry.list_agents()]
    logger.info("Built-in agents loaded: %s", ", ".join(sorted(loaded)))
