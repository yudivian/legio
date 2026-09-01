"""Contract tests for LEG-023 — AgentBase.run() uniform loop (over native beaver).

The AgentBase is the generalized per-step runner every atomic agent and
composite implements (LEG-023). Its ``run()`` pops a work item from its native
beaver queue, takes a native beaver lock as the lease, dispatches it to the
step's job (a subclass ``_handle``), applies the ``retry_guard`` / ``monitor``
hooks, and routes the outcome by position (Schema 2): advance to the next class
of the level as an ``ExecutionRequestMessage`` or, at the end of the level,
deposit an ``ExecutionResultMessage`` to the level's ``end_of_level_queue``. All
substrate is native beaver (LEG-048); queues are addressed by name on the shared
db.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from beaver import AsyncBeaverDB

from legio.agents.base import AgentBase
from legio.flow import ExecutionRequestMessage, ExecutionResultMessage
from legio.naming import queue_key


def make_request(
    *,
    task_id: str,
    current_index: int = 0,
    route: tuple[str, ...] = ("main",),
    end_of_level_queue: str = "client",
    level: int = 1,
    payload: dict | None = None,
) -> ExecutionRequestMessage:
    return ExecutionRequestMessage(
        level_route=route,
        current_index=current_index,
        end_of_level_queue=end_of_level_queue,
        level=level,
        task_id=task_id,
        payload={"v": 1} if payload is None else payload,
    )


async def pop_one(db: AsyncBeaverDB, agent_id: str) -> dict | None:
    try:
        item = await db.queue(queue_key(agent_id)).get(block=False)
    except IndexError:
        return None
    return item.data


class FinalAgent(AgentBase):
    """Single/final step: returns state, so the base finishes the level."""

    async def _handle(self, request: ExecutionRequestMessage) -> dict:
        return {"v": request.payload.get("v", 0), "consumed": request.payload.get("in", {})}


class ChainAgent(AgentBase):
    """One link of a chain: return state; the base advances until level end."""

    async def _handle(self, request: ExecutionRequestMessage) -> dict:
        return {"v": int(request.payload.get("v", 0)) + 1}


class FailingAgent(AgentBase):
    """A broken step: raises in _handle. retry_guard decides whether to retry."""

    def __init__(self, *, max_retries: int = 0, **kwargs: object) -> None:
        self._max_retries = max_retries
        self.failures: list[str] = []
        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def _handle(self, request: ExecutionRequestMessage) -> dict:
        self.failures.append(request.task_id)
        raise ValueError("boom")


class MergeAgent(AgentBase):
    """A chain link that accumulates its output into the carried state (H3)."""

    async def _handle(self, request: ExecutionRequestMessage) -> dict:
        carried = dict(request.payload)
        step = 1 + sum(1 for key in carried if key.startswith("s"))
        carried[f"s{step}"] = step
        return carried


@dataclass
class HookRecorder:
    events: list[tuple[str, str]] = field(default_factory=list)
    _max_retries_for: int = 0

    async def monitor(self, agent_id: str, task_id: str, event: str) -> None:
        self.events.append((event, task_id))

    async def retry_guard(self, agent_id: str, task_id: str, error: str, attempt: int) -> bool:
        self.events.append(("retry_guard", task_id))
        return attempt < self._max_retries_for


def build(agent_cls, *, agent_id: str, db: AsyncBeaverDB, **extra: object):
    return agent_cls(
        agent_id=agent_id,
        db=db,
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
    assert result.payload["v"] == 1


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
    assert step_message.payload["v"] == 2
    await beaver_db.queue(queue_key("step")).put(step_message.model_dump(mode="json"), priority=0.0)

    assert await second.run() == 1
    ret_item = await pop_one(beaver_db, "client")
    assert ret_item is not None
    result = ExecutionResultMessage.model_validate(ret_item)
    assert result.task_id == "T-two"
    assert result.payload["v"] == 3


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
    assert "error" in result.payload


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
    assert "error" in result.payload


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


@pytest.mark.asyncio
async def test_root_task_deposits_result_to_end_of_level_queue(
    beaver_db: AsyncBeaverDB,
) -> None:
    """Schema 2 (addendum AL): a root finish lands on ``end_of_level_queue``.

    The task's final-result queue (``result:...``) receives the result — never a
    ``client:`` queue (there is no ``client:`` family).
    """
    await beaver_db.queue(queue_key("main")).put(
        make_request(
            task_id="T-root", end_of_level_queue="result:T-root"
        ).model_dump(mode="json"),
        priority=0.0,
    )
    agent = build(FinalAgent, agent_id="main", db=beaver_db)

    assert await agent.run() == 1

    result_item = await pop_one(beaver_db, "result:T-root")
    assert result_item is not None
    result = ExecutionResultMessage.model_validate(result_item)
    assert result.payload["v"] == 1

    with pytest.raises(IndexError):
        await beaver_db.queue(queue_key("client:T-root")).get(block=False)


@pytest.mark.asyncio
async def test_three_stage_chain_accumulates_carried_state(
    beaver_db: AsyncBeaverDB,
) -> None:
    """B1/C1: a chain of three carries the accumulated state message-to-message."""
    agents = [build(MergeAgent, agent_id=a, db=beaver_db) for a in ("main", "mid", "last")]
    route = ("main", "mid", "last")
    await beaver_db.queue(queue_key("main")).put(
        make_request(
            task_id="T-chain",
            current_index=0,
            route=route,
            end_of_level_queue="result:T-chain",
            payload={},
        ).model_dump(mode="json"),
        priority=0.0,
    )

    assert await agents[0].run() == 1
    mid_item = await pop_one(beaver_db, "mid")
    assert mid_item is not None
    mid_msg = ExecutionRequestMessage.model_validate(mid_item)
    assert mid_msg.payload == {"s1": 1}
    await beaver_db.queue(queue_key("mid")).put(mid_msg.model_dump(mode="json"), priority=0.0)

    assert await agents[1].run() == 1
    last_item = await pop_one(beaver_db, "last")
    assert last_item is not None
    last_msg = ExecutionRequestMessage.model_validate(last_item)
    assert last_msg.payload == {"s1": 1, "s2": 2}
    await beaver_db.queue(queue_key("last")).put(last_msg.model_dump(mode="json"), priority=0.0)

    assert await agents[2].run() == 1
    row = await pop_one(beaver_db, "result:T-chain")
    assert row is not None
    result = ExecutionResultMessage.model_validate(row)
    assert result.payload == {"s1": 1, "s2": 2, "s3": 3}
