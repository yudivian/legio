"""Contract tests for LEG-023 — AgentBase.run() uniform loop (over native beaver).

The AgentBase is the generalized per-step runner every atomic agent and
composite implements (LEG-023). Its ``run()`` pops a work item from its native
beaver queue, takes a native beaver lock as the lease, dispatches it to the
step's job (a subclass ``_handle``), applies the ``retry_guard`` / ``monitor``
hooks, and routes the outcome: advance to the next stage as an
``ExecutionRequestMessage`` or, on the final step, deposit an
``ExecutionResultMessage`` to the parent/client. All substrate is native beaver
(LEG-048); frames/queues are addressed by name on the shared db.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from beaver import AsyncBeaverDB

from legio.agents.base import AgentBase
from legio.flow import ExecutionRequestMessage, ExecutionResultMessage
from legio.naming import queue_key


def make_request(
    *, task_id: str, current_index: int = 0, route=("main",), return_agent: str = "client"
) -> ExecutionRequestMessage:
    return ExecutionRequestMessage(
        route_pattern_names=route,
        current_index=current_index,
        ultimate_return_agent_id=return_agent,
        origin_node_id="main",
        task_id=task_id,
        payload={"v": 1},
    )


async def pop_one(db: AsyncBeaverDB, agent_id: str) -> dict | None:
    try:
        item = await db.queue(queue_key(agent_id)).get(block=False)
    except IndexError:
        return None
    return item.data


class FinalAgent(AgentBase):
    """Single/final step: always finishes, depositing an ExecutionResultMessage."""

    async def _handle(self, request: ExecutionRequestMessage) -> None:
        frame = await self._frame(request)
        output = {"v": request.payload.get("v", 0), "consumed": frame.get("in", {})}
        await self._finish(request, output)


class ChainAgent(AgentBase):
    """One link of a chain: advance to the next DAG agent unless last in route."""

    async def _handle(self, request: ExecutionRequestMessage) -> None:
        incoming = request.payload.get("input", {})
        v = incoming.get("v", request.payload.get("v", 0))
        output = {"v": v + 1}
        is_last = request.current_index >= len(request.route_pattern_names) - 1
        if is_last:
            await self._finish(request, output)
        else:
            await self._advance(request, output=output)


class FailingAgent(AgentBase):
    """A broken step: raises in _handle. retry_guard decides whether to retry."""

    def __init__(self, *, max_retries: int = 0, **kwargs: object) -> None:
        self._max_retries = max_retries
        self.failures: list[str] = []
        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def _handle(self, request: ExecutionRequestMessage) -> None:
        self.failures.append(request.task_id)
        raise ValueError("boom")


@dataclass
class HookRecorder:
    events: list[tuple[str, str]] = field(default_factory=list)

    async def monitor(self, agent_id: str, task_id: str, event: str) -> None:
        self.events.append((event, task_id))

    async def retry_guard(self, agent_id: str, task_id: str, error: str, attempt: int) -> bool:
        self.events.append(("retry_guard", task_id))
        return attempt < self._max_retries_for


def build(agent_cls, *, agent_id: str, db: AsyncBeaverDB, **extra: object):
    return agent_cls(
        agent_id=agent_id,
        db=db,
        frames_scope="frames",
        lease_ttl=60.0,
        **extra,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_single_step_task_completes_with_result_in_place(beaver_db: AsyncBeaverDB) -> None:
    await beaver_db.queue(queue_key("main")).put(
        make_request(task_id="T-single").model_dump(mode="json"), priority=0.0
    )
    agent = build(FinalAgent, agent_id="main", db=beaver_db)

    steps = await agent.run()

    assert steps == 1
    result_item = await pop_one(beaver_db, "client")
    assert result_item is not None
    result = ExecutionResultMessage.model_validate(result_item)
    assert result.task_id == "T-single"
    assert result.output["v"] == 1


@pytest.mark.asyncio
async def test_two_step_task_runs_both_steps_and_returns(beaver_db: AsyncBeaverDB) -> None:
    first = build(ChainAgent, agent_id="main", db=beaver_db)
    second = build(ChainAgent, agent_id="step", db=beaver_db)
    route = ("main", "step")
    await beaver_db.queue(queue_key("main")).put(
        make_request(task_id="T-two", current_index=0, route=route).model_dump(mode="json"),
        priority=0.0,
    )

    assert await first.run() == 1
    step_item = await pop_one(beaver_db, "step")
    assert step_item is not None
    step_message = ExecutionRequestMessage.model_validate(step_item)
    assert step_message.task_id == "T-two"
    assert step_message.current_index == 1
    assert step_message.payload["input"]["v"] == 2
    await beaver_db.queue(queue_key("step")).put(step_message.model_dump(mode="json"), priority=0.0)

    assert await second.run() == 1
    ret_item = await pop_one(beaver_db, "client")
    assert ret_item is not None
    result = ExecutionResultMessage.model_validate(ret_item)
    assert result.task_id == "T-two"
    assert result.output["v"] == 3


@pytest.mark.asyncio
async def test_broken_step_marks_task_failed_without_crash(beaver_db: AsyncBeaverDB) -> None:
    agent = build(FailingAgent, agent_id="main", db=beaver_db)
    await beaver_db.queue(queue_key("main")).put(
        make_request(task_id="T-bad").model_dump(mode="json"), priority=0.0
    )

    steps = await agent.run()

    assert steps == 1
    assert agent.failures == ["T-bad"]
    result_item = await pop_one(beaver_db, "client")
    assert result_item is not None
    result = ExecutionResultMessage.model_validate(result_item)
    assert result.task_id == "T-bad"
    assert "error" in result.output


@pytest.mark.asyncio
async def test_retry_guard_fires_and_retries_then_deposits_error(
    beaver_db: AsyncBeaverDB,
) -> None:
    recorder = HookRecorder()
    recorder._max_retries_for = 2
    agent = build(FailingAgent, agent_id="main", db=beaver_db)
    agent.set_hooks(retry_guard=recorder.retry_guard)

    await beaver_db.queue(queue_key("main")).put(
        make_request(task_id="T-retry").model_dump(mode="json"), priority=0.0
    )

    await agent.run()

    assert agent.failures == ["T-retry", "T-retry"]
    assert recorder.events.count(("retry_guard", "T-retry")) == 2
    result_item = await pop_one(beaver_db, "client")
    assert result_item is not None
    result = ExecutionResultMessage.model_validate(result_item)
    assert result.task_id == "T-retry"
    assert "error" in result.output


@pytest.mark.asyncio
async def test_monitor_hook_fires_on_step_events(beaver_db: AsyncBeaverDB) -> None:
    recorder = HookRecorder()
    agent = build(FinalAgent, agent_id="main", db=beaver_db)
    agent.set_hooks(monitor=recorder.monitor)
    await beaver_db.queue(queue_key("main")).put(
        make_request(task_id="T-mon").model_dump(mode="json"), priority=0.0
    )

    await agent.run()

    event_types = [event for event, _ in recorder.events]
    assert "start" in event_types
    assert "step_done" in event_types


@pytest.mark.asyncio
async def test_idle_queue_returns_zero_without_busy_loop(beaver_db: AsyncBeaverDB) -> None:
    agent = build(FinalAgent, agent_id="main", db=beaver_db)

    assert await agent.run() == 0
