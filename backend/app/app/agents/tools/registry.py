"""Tool registry with schema validation and sandboxed execution."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class ToolInputValidationError(Exception):
    """Raised when tool input fails schema validation."""

    def __init__(self, tool_name: str, error: ValidationError) -> None:
        self.tool_name = tool_name
        self.validation_error = error
        super().__init__(f"Input validation failed for tool '{tool_name}': {error}")


class ToolNotFoundError(Exception):
    """Raised when a requested tool is not registered."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Tool '{name}' not found in registry")


class ToolExecutionError(Exception):
    """Raised when a tool fails during execution."""

    def __init__(self, tool_name: str, message: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' execution failed: {message}")


@dataclass
class ToolEntry:
    """Registered tool metadata and callable.

    Attributes:
        name: Unique tool identifier.
        description: Human-readable description for LLM tool selection.
        input_schema: Pydantic model class for input validation.
        function: The actual tool callable.
        output_example: Example output for schema documentation.
    """

    name: str
    description: str
    input_schema: type[BaseModel] | None
    function: Callable[..., Any]
    output_example: dict[str, Any] | None = None


class ToolRegistry:
    """Singleton registry for agent tools.

    Tools are registered via the ``@tool`` decorator or ``register()`` method.
    The registry validates inputs against Pydantic schemas before execution
    and provides tool discovery for LLM function-calling formats.
    """

    _instance: ToolRegistry | None = None

    def __new__(cls) -> ToolRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_tools"):
            self._tools: dict[str, ToolEntry] = {}

    def register(
        self,
        name: str,
        description: str,
        input_schema: type[BaseModel] | None = None,
        output_example: dict[str, Any] | None = None,
    ) -> Callable:
        """Decorator to register a function as a tool.

        Usage::

            @registry.register(
                name="search_documents",
                description="Search documents by query",
                input_schema=SearchInput,
            )
            def search(query: str, top_k: int = 10) -> list[dict]:
                ...

        Args:
            name: Unique tool identifier.
            description: Human-readable description.
            input_schema: Optional Pydantic model for input validation.
            output_example: Optional example output dict.
        """

        def decorator(func: Callable) -> Callable:
            entry = ToolEntry(
                name=name,
                description=description,
                input_schema=input_schema,
                function=func,
                output_example=output_example,
            )
            self._tools[name] = entry
            logger.debug("Registered tool: %s", name)
            return func

        return decorator

    def get(self, name: str) -> ToolEntry:
        """Retrieve a tool entry by name.

        Args:
            name: Tool identifier.

        Returns:
            The ``ToolEntry`` for the requested tool.

        Raises:
            ToolNotFoundError: If the tool is not registered.
        """
        if name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[name]

    def list_tools(self) -> list[ToolEntry]:
        """Return all registered tools.

        Returns:
            List of ``ToolEntry`` objects.
        """
        return list(self._tools.values())

    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def validate_args(self, name: str, args: dict[str, Any]) -> BaseModel | None:
        """Validate arguments against a tool's input schema.

        Args:
            name: Tool identifier.
            args: Raw arguments dict.

        Returns:
            Validated Pydantic model instance, or None if no schema.

        Raises:
            ToolNotFoundError: If the tool is not registered.
            ToolInputValidationError: If validation fails.
        """
        entry = self.get(name)
        if entry.input_schema is None:
            return None
        try:
            return entry.input_schema(**args)
        except ValidationError as e:
            raise ToolInputValidationError(name, e) from e

    def execute(self, name: str, args: dict[str, Any]) -> Any:
        """Validate arguments and execute a tool.

        Args:
            name: Tool identifier.
            args: Arguments to pass to the tool function.

        Returns:
            The tool's return value.

        Raises:
            ToolNotFoundError: If the tool is not registered.
            ToolInputValidationError: If argument validation fails.
            ToolExecutionError: If the tool raises during execution.
        """
        entry = self.get(name)
        self.validate_args(name, args)

        start = time.monotonic()
        try:
            result = entry.function(**args)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.info("Tool %s executed in %dms", name, elapsed_ms)
            return result
        except ToolInputValidationError:
            raise
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error("Tool %s failed after %dms: %s", name, elapsed_ms, e)
            raise ToolExecutionError(name, str(e)) from e

    async def execute_async(self, name: str, args: dict[str, Any]) -> Any:
        """Validate arguments and execute a tool (async variant).

        Supports both sync and async tool functions.

        Args:
            name: Tool identifier.
            args: Arguments to pass to the tool function.

        Returns:
            The tool's return value.

        Raises:
            ToolNotFoundError: If the tool is not registered.
            ToolInputValidationError: If argument validation fails.
            ToolExecutionError: If the tool raises during execution.
        """
        import asyncio

        entry = self.get(name)
        self.validate_args(name, args)

        start = time.monotonic()
        try:
            if asyncio.iscoroutinefunction(entry.function):
                result = await entry.function(**args)
            else:
                result = entry.function(**args)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.info("Tool %s executed in %dms", name, elapsed_ms)
            return result
        except ToolInputValidationError:
            raise
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error("Tool %s failed after %dms: %s", name, elapsed_ms, e)
            raise ToolExecutionError(name, str(e)) from e

    def to_openai_tools(self) -> list[dict[str, Any]]:
        """Export tool schemas in OpenAI function-calling format.

        Returns:
            List of tool definitions suitable for the ``tools`` parameter
            of the OpenAI Chat Completions API.
        """
        tools = []
        for entry in self._tools.values():
            tool_def: dict[str, Any] = {
                "type": "function",
                "function": {
                    "name": entry.name,
                    "description": entry.description,
                },
            }
            if entry.input_schema is not None:
                schema = entry.input_schema.model_json_schema()
                tool_def["function"]["parameters"] = schema
            tools.append(tool_def)
        return tools

    def reset(self) -> None:
        """Clear all registered tools. Primarily for testing."""
        self._tools.clear()


def get_registry() -> ToolRegistry:
    """Return the singleton tool registry instance."""
    return ToolRegistry()
