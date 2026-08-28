"""Integration test for the decoupled polling flow (base for LEG-026 E2E).

Pins the corrected, decoupled model over the real modules:

1. ``manager.submit`` (synthetic parent) deposits the first
   ``ExecutionRequestMessage`` (root step) into the starting agent's queue and
   stages the payload.
2. A worker runs a ``ToolAgent`` that *polls* that queue — it never knows the
   client or the task, only the queue.
3. The agent advances/finishes by the DAG in the token and, being root, writes
   the result to ``results:{task_id}``.
4. ``status`` (polling the board) reflects COMPLETED with the output.

This validates the critical corrections so that LEG-025/026 are built on a
faithful decoupled base, not an orchestrated one.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from legio.agents.tool_agent import ToolAgent
from legio.manager import (
    agent_queue,
    client_queue,
    reset_manager,
    results_board,
    status,
    submit,
)
from legio.primitives.inmemory import BoardInMemory
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


@pytest.fixture(autouse=True)
def reset_substrate() -> None:
    reset_manager()


async def build_transform_worker(task_id: str) -> ToolAgent:
    registry = ToolRegistry()
    registry.register("transform", FakeTransformTool(), TransformInput, TransformOutput)
    return ToolAgent(
        agent_id="transform",
        registry=registry,
        tool_type="transform",
        queue=agent_queue("transform"),
        board=BoardInMemory("frames"),
        queues={
            "transform": agent_queue("transform"),
            f"client:{task_id}": client_queue(task_id),
        },
        results_board=await results_board(),
    )


@pytest.mark.asyncio
async def test_submit_deposits_step_one_in_starting_agent_queue() -> None:
    task_id = await submit("client-a", "transform", {"text": "hello"})

    start_q = agent_queue("transform")
    item = await start_q.pop()
    assert item is not None
    assert item["task_id"] == task_id
    assert item["current_index"] == 0
    assert item["payload"]["input"] == {"text": "hello"}


@pytest.mark.asyncio
async def test_decoupled_root_flow_writes_results_and_status_completed() -> None:
    task_id = await submit("client-a", "transform", {"text": "hello"})

    worker = await build_transform_worker(task_id)
    steps = await worker.run()
    assert steps == 1

    entry = await status(task_id, "client-a")
    assert entry.state.value == "completed"
    assert entry.output == {"transformed": "HELLO"}
    assert entry.result_key == f"results:{task_id}"

    board = await results_board()
    assert await board.get(task_id) == {"output": {"transformed": "HELLO"}}
