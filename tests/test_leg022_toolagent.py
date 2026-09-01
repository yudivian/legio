"""Tests for LEG-022 — ToolAgent execution path (over native beaver).

The ToolAgent pops a work item from its native beaver queue, reads the payload
from the message's single ``payload`` container (Schema 2), validates it
against the tool's ``input_schema``, calls the registered tool, validates the
``output_schema``, and builds the new payload, which the base routes:
advance to the next class of the level, or deposit an ``ExecutionResultMessage``
to the level's ``end_of_level_queue``. The step's state travels in the messages
(AGENT_LIFECYCLE §12.1): nothing is staged out-of-message. Schema failures on
either edge are never silent: the failure is visible in the outcome. All state
lives on native beaver primitives (LEG-048).
"""

from __future__ import annotations

import pytest
from beaver import AsyncBeaverDB
from pydantic import BaseModel

from legio.agents.tool_agent import ToolAgent
from legio.flow import ExecutionRequestMessage, ExecutionResultMessage
from legio.naming import queue_key
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


async def pop_one(db: AsyncBeaverDB, agent_id: str) -> dict | None:
    try:
        item = await db.queue(queue_key(agent_id)).get(block=False)
    except IndexError:
        return None
    return item.data


def crafted_request(
    *, task_id: str, payload: dict
) -> ExecutionRequestMessage:
    return ExecutionRequestMessage(
        level_route=("main_a", "summ"),
        current_index=1,
        end_of_level_queue="main_a",
        task_id=task_id,
        payload=payload,
    )


@pytest.mark.asyncio
async def test_fake_tool_executes_end_to_end_with_result_deposited(
    beaver_db: AsyncBeaverDB,
) -> None:
    registry = ToolRegistry()
    tool = FakeTransformTool()
    registry.register("transform", tool, TransformInput, TransformOutput)

    request = crafted_request(task_id="T-1", payload={"text": "hello", "factor": 2})
    await beaver_db.queue(queue_key("summ")).put(request.model_dump(mode="json"), priority=0.0)

    agent = ToolAgent(
        agent_id="summ",
        db=beaver_db,
        registry=registry,
        tool_type="transform",
    )

    handled = await agent.process_next()
    assert handled is True

    assert tool.calls and tool.calls[0]["text"] == "hello"
    assert tool.calls[0]["factor"] == 2

    result_item = await pop_one(beaver_db, "main_a")
    assert result_item is not None
    result = ExecutionResultMessage.model_validate(result_item)
    assert result.task_id == "T-1"
    assert result.payload["transformed"] == "HELLO"


@pytest.mark.asyncio
async def test_input_schema_rejection_is_never_silent(beaver_db: AsyncBeaverDB) -> None:
    registry = ToolRegistry()
    tool = FakeTransformTool()
    registry.register("transform", tool, TransformInput, TransformOutput)

    request = crafted_request(task_id="T-bad-in", payload={"text": 123})
    await beaver_db.queue(queue_key("summ")).put(request.model_dump(mode="json"), priority=0.0)

    agent = ToolAgent(
        agent_id="summ",
        db=beaver_db,
        registry=registry,
        tool_type="transform",
    )

    await agent.process_next()

    assert tool.calls == []
    result_item = await pop_one(beaver_db, "main_a")
    assert result_item is not None
    result = ExecutionResultMessage.model_validate(result_item)
    assert result.task_id == "T-bad-in"
    assert "error" in result.payload


@pytest.mark.asyncio
async def test_output_schema_rejection_is_never_silent(beaver_db: AsyncBeaverDB) -> None:
    registry = ToolRegistry()
    tool = FakeTransformTool()
    tool.set_output(123)
    registry.register("transform", tool, TransformInput, TransformOutput)

    request = crafted_request(task_id="T-bad-out", payload={"text": "hi"})
    await beaver_db.queue(queue_key("summ")).put(request.model_dump(mode="json"), priority=0.0)

    agent = ToolAgent(
        agent_id="summ",
        db=beaver_db,
        registry=registry,
        tool_type="transform",
    )

    await agent.process_next()

    assert len(tool.calls) == 1
    result_item = await pop_one(beaver_db, "main_a")
    assert result_item is not None
    result = ExecutionResultMessage.model_validate(result_item)
    assert result.task_id == "T-bad-out"
    assert "error" in result.payload


@pytest.mark.asyncio
async def test_no_due_item_returns_false(beaver_db: AsyncBeaverDB) -> None:
    registry = ToolRegistry()
    registry.register("transform", FakeTransformTool(), TransformInput, TransformOutput)

    agent = ToolAgent(
        agent_id="summ",
        db=beaver_db,
        registry=registry,
        tool_type="transform",
    )

    assert await agent.process_next() is False
