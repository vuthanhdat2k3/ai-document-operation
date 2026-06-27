"""Agent Registry — register, discover, retrieve, and version agent specifications.

Mirrors the pattern used by ``ToolRegistry`` but for agents themselves.
Agents can be registered via the ``@agent`` decorator or added explicitly.

Version history is preserved so callers can inspect or roll back to
previous versions of an agent definition.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.harness.agent_spec import AgentSpec

logger = logging.getLogger(__name__)


_MAX_VERSION_HISTORY = 20


class AgentNotFoundError(LookupError):
    """Raised when a requested agent is not registered."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Agent '{name}' not found in registry. Available: ...")


class VersionNotFoundError(LookupError):
    """Raised when a requested version is not found in history."""

    def __init__(self, name: str, version: str) -> None:
        self.name = name
        self.version = version
        super().__init__(f"Version '{version}' for agent '{name}' not found in history.")


class AgentRegistry:
    """Singleton registry for agent specifications with version history.

    Agents are registered via the ``@agent`` decorator or ``register()`` method.
    The registry preserves version history for rollback and inspection.

    Usage::

        registry = get_agent_registry()

        # Register an AgentSpec instance
        registry.register(doc_qa_spec)

        # Retrieve
        spec = registry.get("doc-qa")

        # List all
        for spec in registry.list_agents():
            print(spec.name, spec.description)

        # Version management
        registry.list_versions("doc-qa")
        spec_v1 = registry.get_version("doc-qa", "1.0.0")
        registry.rollback("doc-qa", "1.0.0")
    """

    _instance: AgentRegistry | None = None

    def __new__(cls) -> AgentRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents: dict[str, "AgentSpec"] = {}
            cls._instance._history: dict[str, list[dict]] = {}
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_agents"):
            self._agents: dict[str, "AgentSpec"] = {}
        if not hasattr(self, "_history"):
            self._history: dict[str, list[dict]] = {}

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
                "Use 'register_or_replace(...)' or unregister first."
            )
        self._agents[spec.name] = spec
        self._push_history(spec)
        logger.info("Registered agent: %s v%s", spec.name, spec.version)
        return spec

    def register_or_replace(self, spec: "AgentSpec") -> "AgentSpec":
        """Register or replace an existing AgentSpec.

        Preserves the previous version in the version history.

        Args:
            spec: The agent specification to register.

        Returns:
            The same spec.
        """
        existed = spec.name in self._agents
        self._agents[spec.name] = spec
        self._push_history(spec)
        if existed:
            logger.info("Replaced agent: %s v%s", spec.name, spec.version)
        else:
            logger.info("Registered agent: %s v%s", spec.name, spec.version)
        return spec

    def unregister(self, name: str) -> None:
        """Remove an agent from the registry.

        Version history is preserved even after unregistration.

        Args:
            name: Agent name to remove.

        Raises:
            AgentNotFoundError: If the agent is not registered.
        """
        if name not in self._agents:
            raise AgentNotFoundError(name)
        del self._agents[name]
        logger.info("Unregistered agent: %s", name)

    # ── version history ───────────────────────────────────────────────────

    def _push_history(self, spec: "AgentSpec") -> None:
        """Push a version record into the agent's version history."""
        history = self._history.setdefault(spec.name, [])
        entry = {
            "version": spec.version,
            "name": spec.name,
            "description": spec.description,
            "registered_at": datetime.now(UTC).isoformat(),
        }
        # Avoid duplicate consecutive versions
        if history and history[-1]["version"] == spec.version:
            history[-1] = entry
        else:
            history.append(entry)
        # Trim oldest entries
        if len(history) > _MAX_VERSION_HISTORY:
            history[:] = history[-_MAX_VERSION_HISTORY:]

    def list_versions(self, name: str) -> list[dict]:
        """Return the version history for a named agent.

        Args:
            name: Agent identifier.

        Returns:
            List of dicts with keys: ``version``, ``name``, ``registered_at``.
        """
        return list(self._history.get(name, []))

    def get_version(self, name: str, version: str) -> "AgentSpec | None":
        """Retrieve a specific version of an agent from history.

        Args:
            name: Agent identifier.
            version: Semantic version string to look up.

        Returns:
            The AgentSpec if the version is the currently active one,
            ``None`` otherwise (we only store metadata in history, not
            full spec copies).
        """
        spec = self._agents.get(name)
        if spec is not None and spec.version == version:
            return spec
        # Version not found — could store full snapshots in future
        return None

    def rollback(self, name: str, version: str) -> "AgentSpec":
        """Roll back an agent to a previous version.

        .. note::
            Full spec snapshots are not stored yet — rollback verifies
            the version exists in history and re-registers.  To fully
            support rollback the plugin system must re-import the spec.

        Args:
            name: Agent identifier.
            version: Version to roll back to.

        Returns:
            The current (rolled back) AgentSpec.

        Raises:
            VersionNotFoundError: If the version is not found.
        """
        history = self._history.get(name, [])
        if not any(h["version"] == version for h in history):
            raise VersionNotFoundError(name, version)

        if name not in self._agents:
            raise AgentNotFoundError(name)

        logger.info("Rollback requested for %s to v%s — re-import needed", name, version)
        # Current implementation: mark the rollback in history.
        # Full rollback requires re-loading the spec from the plugin source.
        self._history[name].append({
            "version": f"{self._agents[name].version}→{version}",
            "name": name,
            "description": f"Rollback to {version} requested",
            "registered_at": datetime.now(UTC).isoformat(),
        })
        return self._agents[name]

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
        """Clear all registered agents and version history. Primarily for testing."""
        self._agents.clear()
        self._history.clear()

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
                "version": spec.version,
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
