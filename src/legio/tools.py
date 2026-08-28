"""`legio.tools` — the tool registry (LEG-013) and tool contract.

A tool is an opaque, substitutable execution resource injected by the consumer.
It exposes only its pydantic ``input_schema`` / ``output_schema`` and never knows
about agents or queues. The registry maps ``tool_type`` → tool per node, loaded
at worker startup.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


@runtime_checkable
class Tool(Protocol):
    """A substitutable execution resource exposing only its schemas."""

    @property
    def input_schema(self) -> type[BaseModel]: ...

    @property
    def output_schema(self) -> type[BaseModel]: ...


class ToolRegistry:
    """Maps ``tool_type`` → tool and its schemas, per node."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._input_schemas: dict[str, type[BaseModel]] = {}
        self._output_schemas: dict[str, type[BaseModel]] = {}

    def register(
        self,
        tool_type: str,
        tool: Tool,
        input_schema: type[BaseModel],
        output_schema: type[BaseModel],
    ) -> None:
        """Register a tool against its ``tool_type``."""
        self._tools[tool_type] = tool
        self._input_schemas[tool_type] = input_schema
        self._output_schemas[tool_type] = output_schema

    def resolve(self, tool_type: str) -> Tool:
        """Return the registered tool instance for ``tool_type``."""
        try:
            return self._tools[tool_type]
        except KeyError:
            raise KeyError(f"no tool registered for tool_type {tool_type!r}") from None

    def schemas(self, tool_type: str) -> tuple[type[BaseModel], type[BaseModel]]:
        """Return ``(input_schema, output_schema)`` for ``tool_type``."""
        if tool_type not in self._tools:
            raise KeyError(f"no tool registered for tool_type {tool_type!r}")
        return self._input_schemas[tool_type], self._output_schemas[tool_type]


__all__ = ["Tool", "ToolRegistry"]
