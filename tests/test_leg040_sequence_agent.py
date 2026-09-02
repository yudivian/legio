"""Contract tests for LEG-040 — SequenceAgent (forward-only composite, R-4).

A sequence composite is a forward-only chain (AGENT_LIFECYCLE §12.3): steps run
strictly in order and nothing returns to the sequence itself. When a sequence is
reached as a step of its parent's route (a nested/capability sequence), its
``SequenceAgent`` re-seeds the first of its declared stages with a flattened
``level_route`` and ``current_index = 0``, preserving ``level``,
``end_of_level_queue``, ``task_id``, ``launcher_class`` and the incoming
``payload``; the base ``AgentBase`` then advances by position through the stages
to the end of the level (Schema 2 §12.4). A top-level ``main`` sequence is
flattened by ``starting_route`` (its stages ARE the level route), so the
composite is only invoked as an embedded capability.

The contract asserts the two properties the LEG-040 acceptance requires:
ordering by the token (step 1's result is consumable in step 2) and payload
building across steps, plus the forwarding invariants for the nested composite.
Failures (an empty sequence) are never silent (AGENTS.md rule 9).
"""

from __future__ import annotations

import pytest
from beaver import AsyncBeaverDB

from legio.agents.base import AgentBase
from legio.agents.sequence_agent import SequenceAgent
from legio.flow import ExecutionRequestMessage, ExecutionResultMessage, build_payload
from legio.naming import queue_key


class BuildStep(AgentBase):
    """One stage of a sequence: builds the payload including its own output."""

    def __init__(self, *, key: str, **kwargs: object) -> None:
        self._key = key
        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def _handle(self, request: ExecutionRequestMessage) -> dict:
        return build_payload(request.payload, {self._key: request.payload.get("seed", 0)})


async def pop_one(db: AsyncBeaverDB, agent_id: str) -> dict | None:
    try:
        item = await db.queue(queue_key(agent_id)).get(block=False)
    except IndexError:
        return None
    return item.data


def build_sequence(
    *,
    db: AsyncBeaverDB,
    sequence_route: tuple[str, ...],
    agent_id: str = "seq",
) -> SequenceAgent:
    return SequenceAgent(agent_id=agent_id, db=db, sequence_route=sequence_route)


def step_request(
    *,
    task_id: str,
    payload: dict,
    route: tuple[str, ...],
    current_index: int,
    end_of_level_queue: str,
    level: int = 1,
) -> ExecutionRequestMessage:
    return ExecutionRequestMessage(
        level_route=route,
        current_index=current_index,
        end_of_level_queue=end_of_level_queue,
        level=level,
        launcher_class=route[0] if route else "",
        task_id=task_id,
        payload=payload,
    )


@pytest.mark.asyncio
async def test_sequence_forwards_to_first_stage_of_flattened_route(
    beaver_db: AsyncBeaverDB,
) -> None:
    """A nested sequence re-seeds its first stage with current_index 0."""
    seq = build_sequence(db=beaver_db, sequence_route=("a", "b"))
    request = step_request(
        task_id="T-seq",
        payload={"seed": 7},
        route=("outer", "seq"),  # the sequence is step 1 of the outer route
        current_index=1,
        end_of_level_queue="result:T-seq",
    )
    await beaver_db.queue(queue_key("seq")).put(request.model_dump(mode="json"), priority=0.0)

    handled = await seq.process_next()
    assert handled is True

    first = await pop_one(beaver_db, "a")
    assert first is not None
    forwarded = ExecutionRequestMessage.model_validate(first)
    assert forwarded.level_route == ("a", "b")
    assert forwarded.current_index == 0
    assert forwarded.task_id == "T-seq"
    assert forwarded.end_of_level_queue == "result:T-seq"
    assert forwarded.level == 1
    assert forwarded.launcher_class == "outer"
    assert forwarded.payload == {"seed": 7}


@pytest.mark.asyncio
async def test_sequence_preserves_level_and_end_queue_for_branch(
    beaver_db: AsyncBeaverDB,
) -> None:
    """A sequence inside a parallel branch keeps its level and branch closer."""
    seq = build_sequence(db=beaver_db, sequence_route=("p", "q"))
    request = step_request(
        task_id="T-branch",
        payload={"v": 1},
        route=("par", "seq"),
        current_index=1,
        end_of_level_queue="gather:par",  # the parallel's gathering queue
        level=2,
    )
    await beaver_db.queue(queue_key("seq")).put(request.model_dump(mode="json"), priority=0.0)

    await seq.process_next()

    first = await pop_one(beaver_db, "p")
    assert first is not None
    forwarded = ExecutionRequestMessage.model_validate(first)
    assert forwarded.level == 2
    assert forwarded.end_of_level_queue == "gather:par"
    assert forwarded.level_route == ("p", "q")


@pytest.mark.asyncio
async def test_sequence_runs_steps_in_order_and_builds_payload(
    beaver_db: AsyncBeaverDB,
) -> None:
    """A two-step sequence runs step 1 then step 2; step 2 consumes step 1's
    output (ordering by the token) and the final result lands on the closer."""
    seq = build_sequence(db=beaver_db, sequence_route=("step1", "step2"))
    step1 = BuildStep(agent_id="step1", db=beaver_db, key="s1")
    step2 = BuildStep(agent_id="step2", db=beaver_db, key="s2")
    request = step_request(
        task_id="T-2",
        payload={"seed": 3},
        route=("seq",),
        current_index=0,
        end_of_level_queue="result:T-2",
    )
    await beaver_db.queue(queue_key("seq")).put(request.model_dump(mode="json"), priority=0.0)

    assert await seq.process_next() is True

    first = await pop_one(beaver_db, "step1")
    assert first is not None
    first_request = ExecutionRequestMessage.model_validate(first)
    assert first_request.level_route == ("step1", "step2")
    assert first_request.current_index == 0
    await beaver_db.queue(queue_key("step1")).put(first_request.model_dump(mode="json"), priority=0.0)
    assert await step1.process_next() is True

    second = await pop_one(beaver_db, "step2")
    assert second is not None
    second_request = ExecutionRequestMessage.model_validate(second)
    assert second_request.current_index == 1
    assert second_request.payload == {"seed": 3, "s1": 3}
    await beaver_db.queue(queue_key("step2")).put(second_request.model_dump(mode="json"), priority=0.0)
    assert await step2.process_next() is True

    result_item = await pop_one(beaver_db, "result:T-2")
    assert result_item is not None
    result = ExecutionResultMessage.model_validate(result_item)
    assert result.task_id == "T-2"
    assert result.payload == {"seed": 3, "s1": 3, "s2": 3}


@pytest.mark.asyncio
async def test_sequence_with_empty_route_fails_visibly(beaver_db: AsyncBeaverDB) -> None:
    """An empty sequence is a load-time/construction error, never silent."""
    seq = build_sequence(db=beaver_db, sequence_route=())
    request = step_request(
        task_id="T-empty",
        payload={},
        route=("seq",),
        current_index=0,
        end_of_level_queue="result:T-empty",
    )
    await beaver_db.queue(queue_key("seq")).put(request.model_dump(mode="json"), priority=0.0)

    await seq.process_next()

    result_item = await pop_one(beaver_db, "result:T-empty")
    assert result_item is not None
    result = ExecutionResultMessage.model_validate(result_item)
    assert result.task_id == "T-empty"
    assert "error" in result.payload
