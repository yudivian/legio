"""Red contract tests for LEG-023 — AgentBase.run() uniform loop.

The AgentBase is the generalized per-step runner every atomic agent and
composite implements (LEG-023). Its ``run()`` leases a work item, dispatches it
to the step's job (a subclass ``_handle``), applies the ``retry_guard`` /
``monitor`` hooks, and routes the outcome: advance to the next stage as an
``ExecutionRequestMessage`` or, on the final step, deposit an
``ExecutionResultMessage`` to the parent/client.

These tests fix the spec's acceptance criteria (contract-first, red first):
  - a single-step task completes with its result in place;
  - a two-step task runs both steps and returns;
  - a broken tool/step marks the task failed without crashing (surfaced error);
  - hooks (retry_guard, monitor) fire on the right events.

The production code imported here (``legio.agents.base``) does NOT exist yet.
This file is intentionally red.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from legio.agents.base import AgentBase
from legio.flow import ExecutionRequestMessage, ExecutionResultMessage
from legio.primitives.inmemory import BoardInMemory, QueueInMemory


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


def build(agent_cls, *, agent_id: str, queues: dict[str, QueueInMemory], **extra: object):
    queue = queues[agent_id]
    board = BoardInMemory(scope="frames")
    return agent_cls(
        agent_id=agent_id,
        queue=queue,
        board=board,
        queues=queues,
        frames_scope="frames",
        lease_ttl=60.0,
        **extra,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_single_step_task_completes_with_result_in_place() -> None:
    main_q, client_q = QueueInMemory("main"), QueueInMemory("client")
    queues = {"main": main_q, "client": client_q}
    agent = build(FinalAgent, agent_id="main", queues=queues)
    await main_q.push(make_request(task_id="T-single").model_dump(mode="json"))

    steps = await agent.run()

    assert steps == 1
    result_item = await client_q.pop()
    assert result_item is not None
    result = ExecutionResultMessage.model_validate(result_item)
    assert result.task_id == "T-single"
    assert result.output["v"] == 1


@pytest.mark.asyncio
async def test_two_step_task_runs_both_steps_and_returns() -> None:
    main_q, step_q, client_q = QueueInMemory("main"), QueueInMemory("step"), QueueInMemory("client")
    queues = {"main": main_q, "step": step_q, "client": client_q}
    first = build(
        ChainAgent,
        agent_id="main",
        queues=queues,
    )
    second = build(ChainAgent, agent_id="step", queues=queues)
    route = ("main", "step")
    await main_q.push(
        make_request(task_id="T-two", current_index=0, route=route).model_dump(mode="json")
    )

    assert await first.run() == 1
    step_item = await step_q.pop()
    assert step_item is not None
    step_message = ExecutionRequestMessage.model_validate(step_item)
    assert step_message.task_id == "T-two"
    assert step_message.current_index == 1
    assert step_message.payload["input"]["v"] == 2
    await step_q.push(step_message.model_dump(mode="json"))

    assert await second.run() == 1
    ret_item = await client_q.pop()
    assert ret_item is not None
    result = ExecutionResultMessage.model_validate(ret_item)
    assert result.task_id == "T-two"
    assert result.output["v"] == 3


@pytest.mark.asyncio
async def test_broken_step_marks_task_failed_without_crash() -> None:
    main_q, client_q = QueueInMemory("main"), QueueInMemory("client")
    queues = {"main": main_q, "client": client_q}
    agent = build(FailingAgent, agent_id="main", queues=queues)
    await main_q.push(make_request(task_id="T-bad").model_dump(mode="json"))

    steps = await agent.run()

    assert steps == 1
    assert agent.failures == ["T-bad"]
    result_item = await client_q.pop()
    assert result_item is not None
    result = ExecutionResultMessage.model_validate(result_item)
    assert result.task_id == "T-bad"
    assert "error" in result.output


@pytest.mark.asyncio
async def test_retry_guard_fires_and_retries_then_deposits_error() -> None:
    main_q, client_q = QueueInMemory("main"), QueueInMemory("client")
    queues = {"main": main_q, "client": client_q}
    recorder = HookRecorder()
    recorder._max_retries_for = 2
    agent = build(FailingAgent, agent_id="main", queues=queues)
    agent.set_hooks(retry_guard=recorder.retry_guard)

    await main_q.push(make_request(task_id="T-retry").model_dump(mode="json"))

    await agent.run()

    assert agent.failures == ["T-retry", "T-retry"]
    assert recorder.events.count(("retry_guard", "T-retry")) == 2
    result_item = await client_q.pop()
    assert result_item is not None
    result = ExecutionResultMessage.model_validate(result_item)
    assert result.task_id == "T-retry"
    assert "error" in result.output


@pytest.mark.asyncio
async def test_monitor_hook_fires_on_step_events() -> None:
    main_q, client_q = QueueInMemory("main"), QueueInMemory("client")
    queues = {"main": main_q, "client": client_q}
    recorder = HookRecorder()
    agent = build(FinalAgent, agent_id="main", queues=queues)
    agent.set_hooks(monitor=recorder.monitor)
    await main_q.push(make_request(task_id="T-mon").model_dump(mode="json"))

    await agent.run()

    event_types = [event for event, _ in recorder.events]
    assert "start" in event_types
    assert "step_done" in event_types


@pytest.mark.asyncio
async def test_idle_queue_returns_zero_without_busy_loop() -> None:
    queues = {"main": QueueInMemory("main")}
    agent = build(FinalAgent, agent_id="main", queues=queues)

    assert await agent.run() == 0
