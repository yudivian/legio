"""Integration test for the decoupled polling flow over native beaver (LEG-048).

Pins the corrected, decoupled model over the real modules:

1. ``manager.submit`` (synthetic parent) deposits the first
   ``ExecutionRequestMessage`` (root step) into the starting agent's queue
   (``db.queue("legio:queue:transform")``) and stages the payload.
2. A ``ToolAgent`` runs its own loop and *polls* that queue — it never knows the
   client or the task, only the queue.
3. The agent advances/finishes by the DAG in the token and, being root, writes
   the result to ``db.dict("results")``.
4. ``status`` (polling the board) reflects COMPLETED with the output.

This validates the critical corrections so that LEG-025/026 are built on a
faithful decoupled base, not an orchestrated one. No invented substrate layer.
"""

from __future__ import annotations

import pytest
from beaver import AsyncBeaverDB
from pydantic import BaseModel

from legio.agents.tool_agent import ToolAgent
from legio.manager import results_board, status, submit
from legio.naming import queue_key
from legio.tools import ToolRegistry


class TransformInput(BaseModel):
    text: str
    factor: int = 2


class TransformOutput(BaseModel):
    transformed: str


class FakeTransformTool:
    @property
    def input_schema(self) -> type[BaseModel]:
        return TransformInput

    @property
    def output_schema(self) -> type[BaseModel]:
        return TransformOutput

    def __call__(self, **kwargs: object) -> dict:
        return {"transformed": str(kwargs["text"]).upper()}


def build_transform_agent(db: AsyncBeaverDB) -> ToolAgent:
    registry = ToolRegistry()
    registry.register("transform", FakeTransformTool(), TransformInput, TransformOutput)
    return ToolAgent(
        agent_id="transform",
        db=db,
        registry=registry,
        tool_type="transform",
    )


@pytest.mark.asyncio
async def test_submit_deposits_step_one_in_starting_agent_queue(
    beaver_db: AsyncBeaverDB,
) -> None:
    task_id = await submit("client-a", "transform", {"text": "hello"})

    item = await beaver_db.queue(queue_key("transform")).get(block=False)
    assert item.data["task_id"] == task_id
    assert item.data["current_index"] == 0
    assert item.data["payload"]["input"] == {"text": "hello"}


@pytest.mark.asyncio
async def test_decoupled_root_flow_writes_results_and_status_completed(
    beaver_db: AsyncBeaverDB,
) -> None:
    task_id = await submit("client-a", "transform", {"text": "hello"})

    agent_db = beaver_db
    board = await results_board()
    _ = board  # ensures the manager's results dict exists

    agent = build_transform_agent(agent_db)
    steps = await agent.run()
    assert steps == 1

    entry = await status(task_id, "client-a")
    assert entry.state.value == "completed"
    assert entry.output == {"text": "hello", "transformed": "HELLO"}
    assert entry.result_key == f"results:{task_id}"

    assert await board.fetch(task_id) == {"output": {"text": "hello", "transformed": "HELLO"}}
