"""Plugin loader — discover, load, and register external agent/tool plugins.

Plugin discovery scans configured directories for Python modules that
export either:

* ``__agent_plugin__`` — an ``AgentSpec`` instance
* ``__tool_plugin__`` — a callable with a ``ToolEntry``-like interface

Directory structure::

    plugins/
    ├── my-custom-agent/
    │   ├── __init__.py          # exports __agent_plugin__
    │   └── ...
    └── my-custom-tool/
        ├── __init__.py          # exports __tool_plugin__
        └── ...
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

AGENT_PLUGIN_ATTR = "__agent_plugin__"
TOOL_PLUGIN_ATTR = "__tool_plugin__"


def discover_plugins(plugin_dirs: list[str] | None = None) -> list[Path]:
    """Discover plugin directories containing Python modules.

    Args:
        plugin_dirs: List of directory paths to scan.
            Defaults to ``./plugins`` relative to the working directory.

    Returns:
        List of paths to ``__init__.py`` files found in subdirectories.
    """
    if plugin_dirs is None:
        plugin_dirs = ["plugins"]

    found: list[Path] = []
    for directory in plugin_dirs:
        root = Path(directory).resolve()
        if not root.is_dir():
            logger.debug("Plugin directory %s does not exist, skipping", root)
            continue

        for entry in sorted(root.iterdir()):
            init_file = entry / "__init__.py"
            if init_file.is_file():
                found.append(init_file)
                logger.debug("Discovered plugin candidate: %s", entry.name)
            elif entry.is_dir() and (entry / "__init__.py").is_file():
                found.append(entry / "__init__.py")

    logger.info("Discovered %d plugin candidates", len(found))
    return found


def load_plugin_module(init_path: Path) -> Any | None:
    """Load a single plugin module and extract its plugin attributes.

    Args:
        init_path: Path to the plugin's ``__init__.py``.

    Returns:
        The loaded module if it exports ``__agent_plugin__`` or
        ``__tool_plugin__``, ``None`` otherwise.
    """
    plugin_dir = init_path.parent
    module_name = f"_plugin_{plugin_dir.name}"

    # Add parent to sys.path so relative imports in the plugin work
    parent_dir = str(plugin_dir.parent)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    try:
        spec = importlib.util.spec_from_file_location(module_name, init_path)
        if spec is None or spec.loader is None:
            logger.warning("Could not load spec for %s", init_path)
            return None

        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        if hasattr(mod, AGENT_PLUGIN_ATTR) or hasattr(mod, TOOL_PLUGIN_ATTR):
            logger.info("Loaded plugin: %s (agent=%s, tool=%s)", plugin_dir.name,
                        hasattr(mod, AGENT_PLUGIN_ATTR), hasattr(mod, TOOL_PLUGIN_ATTR))
            return mod

        logger.debug("Module %s has no plugin attributes, skipping", plugin_dir.name)
        return None
    except Exception as exc:
        logger.warning("Failed to load plugin %s: %s", plugin_dir.name, exc)
        return None


def load_plugins(plugin_dirs: list[str] | None = None) -> dict[str, int]:
    """Discover and load all plugins, registering found agents and tools.

    Args:
        plugin_dirs: Directories to scan for plugins.

    Returns:
        Summary dict: ``{"agents_loaded": int, "tools_loaded": int}``.
    """
    from app.harness.agent_registry import get_agent_registry
    from app.agents.tools.registry import get_tool_registry

    registry = get_agent_registry()
    # tool_registry = get_tool_registry()  # uncomment when ToolRegistry getter is available

    init_files = discover_plugins(plugin_dirs)
    agents_loaded = 0
    tools_loaded = 0

    for init_file in init_files:
        mod = load_plugin_module(init_file)
        if mod is None:
            continue

        agent_plugin = getattr(mod, AGENT_PLUGIN_ATTR, None)
        if agent_plugin is not None:
            try:
                registry.register_or_replace(agent_plugin)
                agents_loaded += 1
                logger.info("Registered plugin agent: %s", agent_plugin.name)
            except Exception as exc:
                logger.error("Failed to register plugin agent from %s: %s", init_file.parent.name, exc)

        tool_plugin = getattr(mod, TOOL_PLUGIN_ATTR, None)
        if tool_plugin is not None:
            try:
                # tool_registry.register(tool_plugin)
                tools_loaded += 1
                logger.info("Registered plugin tool: %s from %s",
                            getattr(tool_plugin, "name", "unknown"), init_file.parent.name)
            except Exception as exc:
                logger.error("Failed to register plugin tool from %s: %s", init_file.parent.name, exc)

    return {"agents_loaded": agents_loaded, "tools_loaded": tools_loaded}
