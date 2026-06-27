"""Agent Registry — register, discover, and retrieve agent specifications.

Mirrors the pattern used by ``ToolRegistry`` but for agents themselves.
Agents can be registered via the ``@agent`` decorator or added explicitly.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.harness.agent_spec import AgentSpec

logger = logging.getLogger(__name__)


class AgentNotFoundError(LookupError):
    """Raised when a requested agent is not registered."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Agent '{name}' not found in registry. Available: ...")


class AgentRegistry:
    """Singleton registry for agent specifications.

    Agents are registered via the ``@agent`` decorator or ``register()`` method.
    The registry provides discovery for the API layer and runtime lookup for
    the ``AgentService``.

    Usage::

        registry = get_agent_registry()

        # Register an AgentSpec instance
        registry.register(doc_qa_spec)

        # Retrieve
        spec = registry.get("doc-qa")

        # List all
        for spec in registry.list_agents():
            print(spec.name, spec.description)
    """

    _instance: AgentRegistry | None = None

    def __new__(cls) -> AgentRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents: dict[str, "AgentSpec"] = {}
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_agents"):
            self._agents: dict[str, "AgentSpec"] = {}

    # ── registration ──────────────────────────────────────────────────────

    def register(self, spec: "AgentSpec") -> "AgentSpec":
        """Register an AgentSpec.

        Args:
            spec: The agent specification to register.

        Returns:
            The same spec (for chaining / decorator use).

        Raises:
            ValueError: If an agent with the same name is already registered.
        """
        if spec.name in self._agents:
            raise ValueError(
                f"Agent '{spec.name}' is already registered. "
                "Use 'register(..., replace=True)' or unregister first."
            )
        self._agents[spec.name] = spec
        logger.info("Registered agent: %s v%s", spec.name, spec.version)
        return spec

    def register_or_replace(self, spec: "AgentSpec") -> "AgentSpec":
        """Register or replace an existing AgentSpec.

        Args:
            spec: The agent specification to register.

        Returns:
            The same spec.
        """
        existed = spec.name in self._agents
        self._agents[spec.name] = spec
        if existed:
            logger.info("Replaced agent: %s v%s", spec.name, spec.version)
        else:
            logger.info("Registered agent: %s v%s", spec.name, spec.version)
        return spec

    def unregister(self, name: str) -> None:
        """Remove an agent from the registry.

        Args:
            name: Agent name to remove.

        Raises:
            AgentNotFoundError: If the agent is not registered.
        """
        if name not in self._agents:
            raise AgentNotFoundError(name)
        del self._agents[name]
        logger.info("Unregistered agent: %s", name)

    # ── lookup ────────────────────────────────────────────────────────────

    def get(self, name: str) -> "AgentSpec":
        """Retrieve an AgentSpec by name.

        Args:
            name: Agent identifier.

        Returns:
            The matching AgentSpec.

        Raises:
            AgentNotFoundError: If no agent with that name is registered.
        """
        spec = self._agents.get(name)
        if spec is None:
            raise AgentNotFoundError(name)
        return spec

    def has(self, name: str) -> bool:
        """Check if an agent is registered."""
        return name in self._agents

    def list_agents(
        self,
        category: str | None = None,
    ) -> list["AgentSpec"]:
        """Return all registered agents, optionally filtered by category.

        Args:
            category: If set, only return agents whose metadata.category matches.

        Returns:
            List of matching AgentSpec objects.
        """
        specs = list(self._agents.values())
        if category:
            specs = [
                s for s in specs if s.metadata.get("category") == category
            ]
        return specs

    # ── bulk ──────────────────────────────────────────────────────────────

    def register_many(self, specs: list["AgentSpec"]) -> None:
        """Register multiple AgentSpecs at once.

        Args:
            specs: List of agent specifications.
        """
        for spec in specs:
            self.register(spec)

    def reset(self) -> None:
        """Clear all registered agents. Primarily for testing."""
        self._agents.clear()

    # ── convenience ───────────────────────────────────────────────────────

    def to_openai_assistants(self) -> list[dict]:
        """Export agent specs in OpenAI Assistants API format (for reference).

        Returns:
            List of assistant-like definitions.
        """
        return [
            {
                "id": spec.name,
                "description": spec.description,
                "model": spec.model.model_name,
                "tools": spec.tools,
                "metadata": spec.metadata,
            }
            for spec in self._agents.values()
        ]


# ── module-level helpers ────────────────────────────────────────────────


def get_agent_registry() -> AgentRegistry:
    """Return the singleton agent registry instance."""
    return AgentRegistry()


def agent(spec: "AgentSpec") -> "AgentSpec":
    """Decorator-style registration helper.

    Usage::

        QA_AGENT = agent(AgentSpec.doc_qa())
    """
    return get_agent_registry().register(spec)
