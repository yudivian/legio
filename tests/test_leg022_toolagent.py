"""Red contract tests for LEG-022 — ToolAgent execution path.

The ToolAgent leases a work item from its queue, reads the staged ``input``
frame key on the blackboard, validates it against the tool's ``input_schema``,
calls the registered tool, validates the ``output_schema``, stages the ``out``
frame and deposits an ``ExecutionResultMessage`` back to the parent (or the
client for the last step). Schema failures on either edge are never silent: the
failure is visible in the outcome.

The production code imported here (``legio.agents.tool_agent``) does NOT exist
yet. This file is intentionally red.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from legio.agents.tool_agent import ToolAgent
from legio.flow import ExecutionRequestMessage, ExecutionResultMessage
from legio.primitives.inmemory import BoardInMemory, QueueInMemory
from legio.tools import ToolRegistry


class TransformInput(BaseModel):
    text: str
    factor: int = 2


class TransformOutput(BaseModel):
    transformed: str


class FakeTransformTool:
    """Domain-free fake tool: callable, exposing only its schemas."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._out: str = "HELLO"

    @property
    def input_schema(self) -> type[BaseModel]:
        return TransformInput

    @property
    def output_schema(self) -> type[BaseModel]:
        return TransformOutput

    def set_output(self, value: object) -> None:
        self._out = value  # type: ignore [assignment]

    def __call__(self, **kwargs: object) -> dict:
        self.calls.append(kwargs)
        return {"transformed": self._out}


@pytest.mark.asyncio
async def test_fake_tool_executes_end_to_end_with_result_deposited() -> None:
    registry = ToolRegistry()
    tool = FakeTransformTool()
    registry.register("transform", tool, TransformInput, TransformOutput)

    queue = QueueInMemory(agent_id="summ")
    parent = QueueInMemory(agent_id="main_a")
    board = BoardInMemory(scope="frames")

    request = ExecutionRequestMessage(
        route_pattern_names=["main_a", "summ"],
        current_index=1,
        ultimate_return_agent_id="main_a",
        origin_node_id="main_a",
        task_id="T-1",
        payload={"input": {"text": "hello", "factor": 2}},
    )
    await queue.push(request.model_dump(mode="json"))
    await board.set("summ:T-1", {"input": {"text": "hello", "factor": 2}})

    agent = ToolAgent(
        agent_id="summ",
        registry=registry,
        tool_type="transform",
        queue=queue,
        board=board,
        queues={"main_a": parent},
        frames_scope="frames",
    )

    handled = await agent.process_next()
    assert handled is True

    assert tool.calls and tool.calls[0]["text"] == "hello"
    assert tool.calls[0]["factor"] == 2

    frame = await board.get("summ:T-1")
    assert frame is not None
    assert frame["out"]["transformed"] == "HELLO"

    result_item = await parent.pop()
    assert result_item is not None
    result = ExecutionResultMessage.model_validate(result_item)
    assert result.task_id == "T-1"
    assert result.output["transformed"] == "HELLO"


@pytest.mark.asyncio
async def test_input_schema_rejection_is_never_silent() -> None:
    registry = ToolRegistry()
    tool = FakeTransformTool()
    registry.register("transform", tool, TransformInput, TransformOutput)

    queue = QueueInMemory(agent_id="summ")
    parent = QueueInMemory(agent_id="main_a")
    board = BoardInMemory(scope="frames")

    request = ExecutionRequestMessage(
        route_pattern_names=["main_a", "summ"],
        current_index=1,
        ultimate_return_agent_id="main_a",
        origin_node_id="main_a",
        task_id="T-bad-in",
    )
    await queue.push(request.model_dump(mode="json"))
    await board.set("summ:T-bad-in", {"input": {"text": 123}})

    agent = ToolAgent(
        agent_id="summ",
        registry=registry,
        tool_type="transform",
        queue=queue,
        board=board,
        queues={"main_a": parent},
        frames_scope="frames",
    )

    await agent.process_next()

    assert tool.calls == []
    result_item = await parent.pop()
    assert result_item is not None
    result = ExecutionResultMessage.model_validate(result_item)
    assert result.task_id == "T-bad-in"
    assert "error" in result.output


@pytest.mark.asyncio
async def test_output_schema_rejection_is_never_silent() -> None:
    registry = ToolRegistry()
    tool = FakeTransformTool()
    tool.set_output(123)
    registry.register("transform", tool, TransformInput, TransformOutput)

    queue = QueueInMemory(agent_id="summ")
    parent = QueueInMemory(agent_id="main_a")
    board = BoardInMemory(scope="frames")

    request = ExecutionRequestMessage(
        route_pattern_names=["main_a", "summ"],
        current_index=1,
        ultimate_return_agent_id="main_a",
        origin_node_id="main_a",
        task_id="T-bad-out",
    )
    await queue.push(request.model_dump(mode="json"))
    await board.set("summ:T-bad-out", {"input": {"text": "hi"}})

    agent = ToolAgent(
        agent_id="summ",
        registry=registry,
        tool_type="transform",
        queue=queue,
        board=board,
        queues={"main_a": parent},
        frames_scope="frames",
    )

    await agent.process_next()

    assert len(tool.calls) == 1
    result_item = await parent.pop()
    assert result_item is not None
    result = ExecutionResultMessage.model_validate(result_item)
    assert result.task_id == "T-bad-out"
    assert "error" in result.output


@pytest.mark.asyncio
async def test_no_due_item_returns_false() -> None:
    registry = ToolRegistry()
    registry.register("transform", FakeTransformTool(), TransformInput, TransformOutput)

    queue = QueueInMemory(agent_id="summ")
    board = BoardInMemory(scope="frames")

    agent = ToolAgent(
        agent_id="summ",
        registry=registry,
        tool_type="transform",
        queue=queue,
        board=board,
        queues={"main_a": QueueInMemory(agent_id="main_a")},
        frames_scope="frames",
    )

    assert await agent.process_next() is False
