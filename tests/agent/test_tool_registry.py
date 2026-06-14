"""Tests for tool registry: registration, listing, execution, validation."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.agents.tools.registry import (
    ToolEntry,
    ToolExecutionError,
    ToolInputValidationError,
    ToolNotFoundError,
    ToolRegistry,
    get_registry,
)


class SearchInput(BaseModel):
    query: str
    top_k: int = 10


class TestToolRegistrySingleton:
    """Singleton behavior."""

    def test_singleton_instance(self) -> None:
        r1 = ToolRegistry()
        r2 = ToolRegistry()
        assert r1 is r2

    def test_get_registry_returns_singleton(self) -> None:
        r = get_registry()
        assert isinstance(r, ToolRegistry)


class TestToolRegistration:
    """Tool registration via @register decorator."""

    def setup_method(self) -> None:
        self.registry = ToolRegistry()
        self.registry.reset()

    def test_register_decorator(self) -> None:
        @self.registry.register(
            name="search",
            description="Search documents",
            input_schema=SearchInput,
        )
        def search(query: str, top_k: int = 10) -> list:
            return [{"result": query}]

        assert self.registry.has("search")

    def test_registered_tool_is_returned_unchanged(self) -> None:
        def my_func(x: int) -> int:
            return x * 2

        decorated = self.registry.register(name="double", description="Double a number")(my_func)
        assert decorated is my_func

    def test_register_with_no_schema(self) -> None:
        @self.registry.register(name="ping", description="Ping")
        def ping() -> str:
            return "pong"

        entry = self.registry.get("ping")
        assert entry.input_schema is None

    def test_register_with_output_example(self) -> None:
        @self.registry.register(
            name="test_tool",
            description="Test",
            output_example={"status": "ok"},
        )
        def test_tool() -> dict:
            return {"status": "ok"}

        entry = self.registry.get("test_tool")
        assert entry.output_example == {"status": "ok"}


class TestToolListing:
    """Tool discovery."""

    def setup_method(self) -> None:
        self.registry = ToolRegistry()
        self.registry.reset()

    def test_list_empty(self) -> None:
        assert self.registry.list_tools() == []

    def test_list_multiple(self) -> None:
        @self.registry.register(name="a", description="Tool A")
        def a() -> None:
            pass

        @self.registry.register(name="b", description="Tool B")
        def b() -> None:
            pass

        tools = self.registry.list_tools()
        assert len(tools) == 2
        names = {t.name for t in tools}
        assert names == {"a", "b"}

    def test_has_returns_true(self) -> None:
        @self.registry.register(name="exists", description="Exists")
        def exists() -> None:
            pass

        assert self.registry.has("exists") is True

    def test_has_returns_false(self) -> None:
        assert self.registry.has("nonexistent") is False

    def test_get_raises_not_found(self) -> None:
        with pytest.raises(ToolNotFoundError, match="nonexistent"):
            self.registry.get("nonexistent")


class TestSchemaValidation:
    """Input validation via Pydantic schemas."""

    def setup_method(self) -> None:
        self.registry = ToolRegistry()
        self.registry.reset()

        @self.registry.register(
            name="search",
            description="Search",
            input_schema=SearchInput,
        )
        def search(query: str, top_k: int = 10) -> list:
            return []

        @self.registry.register(name="no_schema", description="No schema")
        def no_schema() -> str:
            return "ok"

    def test_valid_args(self) -> None:
        result = self.registry.validate_args("search", {"query": "test", "top_k": 5})
        assert isinstance(result, SearchInput)
        assert result.query == "test"
        assert result.top_k == 5

    def test_valid_args_defaults(self) -> None:
        result = self.registry.validate_args("search", {"query": "test"})
        assert isinstance(result, SearchInput)
        assert result.top_k == 10

    def test_invalid_args_raises(self) -> None:
        with pytest.raises(ToolInputValidationError):
            self.registry.validate_args("search", {"wrong_field": "value"})

    def test_missing_required_raises(self) -> None:
        with pytest.raises(ToolInputValidationError):
            self.registry.validate_args("search", {"top_k": 5})

    def test_no_schema_returns_none(self) -> None:
        result = self.registry.validate_args("no_schema", {})
        assert result is None

    def test_not_found_raises(self) -> None:
        with pytest.raises(ToolNotFoundError):
            self.registry.validate_args("missing", {})


class TestToolExecution:
    """Tool execution (sync and async)."""

    def setup_method(self) -> None:
        self.registry = ToolRegistry()
        self.registry.reset()

    def test_execute_sync(self) -> None:
        @self.registry.register(name="add", description="Add numbers")
        def add(a: int, b: int) -> int:
            return a + b

        result = self.registry.execute("add", {"a": 3, "b": 4})
        assert result == 7

    def test_execute_with_schema_validation(self) -> None:
        @self.registry.register(
            name="search",
            description="Search",
            input_schema=SearchInput,
        )
        def search(query: str, top_k: int = 10) -> list:
            return [{"q": query, "k": top_k}]

        result = self.registry.execute("search", {"query": "test", "top_k": 3})
        assert result == [{"q": "test", "k": 3}]

    def test_execute_invalid_args_raises(self) -> None:
        @self.registry.register(
            name="search",
            description="Search",
            input_schema=SearchInput,
        )
        def search(query: str, top_k: int = 10) -> list:
            return []

        with pytest.raises(ToolInputValidationError):
            self.registry.execute("search", {})

    def test_execute_tool_error_wrapped(self) -> None:
        @self.registry.register(name="fail", description="Failing tool")
        def fail() -> None:
            raise ValueError("boom")

        with pytest.raises(ToolExecutionError, match="boom"):
            self.registry.execute("fail", {})

    def test_execute_not_found(self) -> None:
        with pytest.raises(ToolNotFoundError):
            self.registry.execute("missing", {})

    @pytest.mark.asyncio
    async def test_execute_async_sync_func(self) -> None:
        @self.registry.register(name="sync_tool", description="Sync")
        def sync_tool(x: int) -> int:
            return x * 2

        result = await self.registry.execute_async("sync_tool", {"x": 5})
        assert result == 10

    @pytest.mark.asyncio
    async def test_execute_async_async_func(self) -> None:
        @self.registry.register(name="async_tool", description="Async")
        async def async_tool(x: int) -> int:
            return x * 3

        result = await self.registry.execute_async("async_tool", {"x": 5})
        assert result == 15

    @pytest.mark.asyncio
    async def test_execute_async_error_wrapped(self) -> None:
        @self.registry.register(name="async_fail", description="Failing async")
        async def async_fail() -> None:
            raise RuntimeError("async boom")

        with pytest.raises(ToolExecutionError, match="async boom"):
            await self.registry.execute_async("async_fail", {})


class TestDuplicateRegistration:
    """Duplicate tool name handling."""

    def setup_method(self) -> None:
        self.registry = ToolRegistry()
        self.registry.reset()

    def test_last_registration_wins(self) -> None:
        @self.registry.register(name="tool", description="First version")
        def v1() -> str:
            return "v1"

        @self.registry.register(name="tool", description="Second version")
        def v2() -> str:
            return "v2"

        entry = self.registry.get("tool")
        assert entry.description == "Second version"
        assert entry.function() == "v2"

    def test_duplicate_does_not_increase_count(self) -> None:
        @self.registry.register(name="tool", description="V1")
        def v1() -> None:
            pass

        @self.registry.register(name="tool", description="V2")
        def v2() -> None:
            pass

        assert len(self.registry.list_tools()) == 1


class TestOpenAIToolsExport:
    """OpenAI function-calling format export."""

    def setup_method(self) -> None:
        self.registry = ToolRegistry()
        self.registry.reset()

    def test_export_basic(self) -> None:
        @self.registry.register(name="search", description="Search docs")
        def search() -> list:
            return []

        tools = self.registry.to_openai_tools()
        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "search"
        assert tools[0]["function"]["description"] == "Search docs"

    def test_export_with_schema(self) -> None:
        @self.registry.register(
            name="search",
            description="Search",
            input_schema=SearchInput,
        )
        def search(query: str, top_k: int = 10) -> list:
            return []

        tools = self.registry.to_openai_tools()
        params = tools[0]["function"]["parameters"]
        assert "properties" in params
        assert "query" in params["properties"]

    def test_export_empty(self) -> None:
        assert self.registry.to_openai_tools() == []


class TestToolRegistryReset:
    """Registry reset for testing."""

    def test_reset_clears_all(self) -> None:
        registry = ToolRegistry()
        registry.reset()

        @registry.register(name="a", description="A")
        def a() -> None:
            pass

        assert len(registry.list_tools()) == 1
        registry.reset()
        assert len(registry.list_tools()) == 0
