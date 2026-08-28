"""Red contract tests for LEG-013 — Tool registry interface v1.

These tests pin the public contract for the node's tool registry: tools are
opaque, substitutable resources exposing only ``input_schema`` /
``output_schema`` (pydantic), registered against a ``tool_type`` at startup
and resolved per node.

The production code imported here (``legio.tools``) does NOT exist yet. This
file is intentionally red: it must fail because the production code is not
implemented. Conformance is asserted via ``isinstance``, so ``Tool`` must be a
``@typing.runtime_checkable`` protocol.
"""

from __future__ import annotations

import pytest
from legio.tools import Tool, ToolRegistry
from pydantic import BaseModel, ValidationError


class TransformInput(BaseModel):
    text: str
    factor: int = 2


class TransformOutput(BaseModel):
    transformed: str


class TransformTool:
    """Domain-free fake tool exposing only its pydantic schemas."""

    @property
    def input_schema(self) -> type[BaseModel]:
        return TransformInput

    @property
    def output_schema(self) -> type[BaseModel]:
        return TransformOutput


def test_tool_is_opaque_and_domain_free() -> None:
    tool = TransformTool()
    assert tool.input_schema is TransformInput
    assert tool.output_schema is TransformOutput
    for attribute in ("queue", "agent_id", "push", "lease", "ack"):
        assert not hasattr(tool, attribute)


def test_fake_tool_conforms_to_tool_protocol() -> None:
    assert isinstance(TransformTool(), Tool)


def test_resolve_returns_registered_tool_instance() -> None:
    registry = ToolRegistry()
    tool = TransformTool()
    registry.register("transform", tool, TransformInput, TransformOutput)

    resolved = registry.resolve("transform")
    assert resolved is tool


def test_schemas_return_registered_input_and_output_schemas() -> None:
    registry = ToolRegistry()
    registry.register("transform", TransformTool(), TransformInput, TransformOutput)

    input_schema, output_schema = registry.schemas("transform")
    assert input_schema is TransformInput
    assert output_schema is TransformOutput


def test_payloads_validate_against_registered_schemas() -> None:
    registry = ToolRegistry()
    registry.register("transform", TransformTool(), TransformInput, TransformOutput)

    input_schema, output_schema = registry.schemas("transform")

    input_payload = input_schema(text="hello", factor=3)
    assert input_payload.text == "hello"
    assert input_payload.factor == 3

    output_payload = output_schema(transformed="HELLO")
    assert output_payload.transformed == "HELLO"


def test_schema_validation_rejects_invalid_payloads() -> None:
    registry = ToolRegistry()
    registry.register("transform", TransformTool(), TransformInput, TransformOutput)

    input_schema, output_schema = registry.schemas("transform")
    with pytest.raises(ValidationError):
        input_schema(text=123, factor="three")
    with pytest.raises(ValidationError):
        output_schema(transformed=123)


def test_resolve_unknown_tool_type_raises() -> None:
    registry = ToolRegistry()
    with pytest.raises(KeyError):
        registry.resolve("no_such_tool")


def test_schemas_unknown_tool_type_raises() -> None:
    registry = ToolRegistry()
    with pytest.raises(KeyError):
        registry.schemas("no_such_tool")
