"""Contract tests for LEG-041 — ParallelAgent (fan-out/fan-in over native beaver).

The parallel composite fans out each branch to the child class's inbox with
``level + 1`` and ``current_index = 0``, keeping the SAME ``task_id`` — the task
id is the task's identity and never changes anywhere in the flow, including
across a fan-out. Branch results return to the parallel's gathering queue
(collapsed onto its inbox) with that same ``task_id``, so the join is keyed
directly on it (O(1) fetch; no child→parent scan). On all-complete it builds its
payload from the branch results (H3 flat union), decrements ``level`` (−1) and
resumes its own level (Schema 2 §12.4). Nothing waits and nothing is locked:
branches run as soon as their deposit lands on their queue (release
parallelism, rule 8).
"""

from __future__ import annotations

import pytest
from beaver import AsyncBeaverDB

from legio.agents.base import AgentBase
from legio.agents.parallel_agent import ParallelAgent
from legio.flow import ExecutionRequestMessage, ExecutionResultMessage
from legio.naming import queue_key


class Branch(AgentBase):
    """An atomic branch: reads a key from the payload and emits an output."""

    def __init__(self, *, key: str, **kwargs: object) -> None:
        self._key = key
        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def _handle(self, request: ExecutionRequestMessage) -> dict:
        return {self._key: request.payload.get("seed", 0)}


async def pop_one(db: AsyncBeaverDB, agent_id: str) -> dict | None:
    try:
        item = await db.queue(queue_key(agent_id)).get(block=False)
    except IndexError:
        return None
    return item.data


def build_parallel(
    *,
    db: AsyncBeaverDB,
    branches,
    agent_id: str = "par",
) -> ParallelAgent:
    return ParallelAgent(agent_id=agent_id, db=db, branches=branches)


def par_request(
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
async def test_parallel_fans_out_both_branches_sharing_task_id(
    beaver_db: AsyncBeaverDB,
) -> None:
    """Both branches get a request (current_index 0, level+1) that keep the task
    id — the task id never changes in the flow (release parallelism)."""
    par = build_parallel(db=beaver_db, branches=["b1", "b2"])
    request = par_request(
        task_id="P-root",
        payload={"seed": 9},
        route=("main", "par"),
        current_index=1,
        end_of_level_queue="result:P-root",
    )
    await beaver_db.queue(queue_key("par")).put(request.model_dump(mode="json"), priority=0.0)

    handled = await par.process_next()
    assert handled is True

    first = await pop_one(beaver_db, "b1")
    assert first is not None
    second = await pop_one(beaver_db, "b2")
    assert second is not None

    r1 = ExecutionRequestMessage.model_validate(first)
    r2 = ExecutionRequestMessage.model_validate(second)
    # both branches fanned out: current_index 0, one level deeper
    assert r1.current_index == 0 and r2.current_index == 0
    assert r1.level == 2 and r2.level == 2
    # branches return to the parallel's gathering queue, collapsed onto its inbox
    assert r1.end_of_level_queue == "par"
    assert r2.end_of_level_queue == "par"
    # the task id stays constant across the fan-out — it is the task's identity
    assert r1.task_id == "P-root"
    assert r2.task_id == "P-root"
    assert r1.payload == {"seed": 9}
    assert r2.payload == {"seed": 9}


@pytest.mark.asyncio
async def test_parallel_does_not_advance_until_all_branches_return(
    beaver_db: AsyncBeaverDB,
) -> None:
    """After fan-out the parallel has not advanced; only when ALL branches
    return (joined) does it resume its own level."""
    par = build_parallel(db=beaver_db, branches=["b1", "b2"])
    request = par_request(
        task_id="P-partial",
        payload={"seed": 1},
        route=("main", "par", "after"),
        current_index=1,
        end_of_level_queue="result:P-partial",
    )
    await beaver_db.queue(queue_key("par")).put(request.model_dump(mode="json"), priority=0.0)
    assert await par.process_next() is True

    # Fan-out deposited both branches (same task id).
    b1 = await pop_one(beaver_db, "b1")
    b2 = await pop_one(beaver_db, "b2")
    assert b1 is not None and b2 is not None
    child1 = ExecutionRequestMessage.model_validate(b1)
    child2 = ExecutionRequestMessage.model_validate(b2)
    assert child1.task_id == "P-partial"
    assert child2.task_id == "P-partial"

    # One branch returns; the other has not. The parallel must NOT advance yet.
    await beaver_db.queue(queue_key("par")).put(
        ExecutionResultMessage(
            level_route=("b1",),
            current_index=0,
            end_of_level_queue="par",
            level=2,
            launcher_class="main",
            task_id="P-partial",
            payload={"s1": 1},
        ).model_dump(mode="json"),
        priority=0.0,
    )
    # process_next dispatches the result; no "after" deposit yet
    assert await par.process_next() is True
    assert await pop_one(beaver_db, "after") is None

    # Second branch returns -> now the join completes and the parallel advances.
    await beaver_db.queue(queue_key("par")).put(
        ExecutionResultMessage(
            level_route=("b2",),
            current_index=0,
            end_of_level_queue="par",
            level=2,
            launcher_class="main",
            task_id="P-partial",
            payload={"s2": 2},
        ).model_dump(mode="json"),
        priority=0.0,
    )
    assert await par.process_next() is True
    advanced = await pop_one(beaver_db, "after")
    assert advanced is not None
    adv = ExecutionRequestMessage.model_validate(advanced)
    assert adv.current_index == 2
    assert adv.level == 1
    assert adv.task_id == "P-partial"
    assert adv.payload == {"seed": 1, "s1": 1, "s2": 2}


@pytest.mark.asyncio
async def test_parallel_joins_and_delivers_to_flow_end(
    beaver_db: AsyncBeaverDB,
) -> None:
    """A parallel that is the last step of level 1 delivers the final result to
    the final-result queue on all-complete."""
    par = build_parallel(db=beaver_db, branches=["b1", "b2"])
    request = par_request(
        task_id="P-end",
        payload={"seed": 4},
        route=("main", "par"),
        current_index=1,
        end_of_level_queue="result:P-end",
    )
    await beaver_db.queue(queue_key("par")).put(request.model_dump(mode="json"), priority=0.0)
    assert await par.process_next() is True

    b1 = await pop_one(beaver_db, "b1")
    b2 = await pop_one(beaver_db, "b2")
    assert b1 is not None and b2 is not None

    for branch, value in (("b1", 4), ("b2", 4)):
        await beaver_db.queue(queue_key("par")).put(
            ExecutionResultMessage(
                level_route=(branch,),
                current_index=0,
                end_of_level_queue="par",
                level=2,
                launcher_class="main",
                task_id="P-end",
                payload={branch: value},
            ).model_dump(mode="json"),
            priority=0.0,
        )
    await par.process_next()
    await par.process_next()

    result_item = await pop_one(beaver_db, "result:P-end")
    assert result_item is not None
    result = ExecutionResultMessage.model_validate(result_item)
    assert result.task_id == "P-end"
    assert result.payload == {"seed": 4, "b1": 4, "b2": 4}


@pytest.mark.asyncio
async def test_parallel_with_no_branches_fails_visibly(beaver_db: AsyncBeaverDB) -> None:
    """An empty parallel is a construction error, never silent (rule 9)."""
    par = build_parallel(db=beaver_db, branches=[])
    request = par_request(
        task_id="P-empty",
        payload={},
        route=("par",),
        current_index=0,
        end_of_level_queue="result:P-empty",
    )
    await beaver_db.queue(queue_key("par")).put(request.model_dump(mode="json"), priority=0.0)

    await par.process_next()

    result_item = await pop_one(beaver_db, "result:P-empty")
    assert result_item is not None
    result = ExecutionResultMessage.model_validate(result_item)
    assert result.task_id == "P-empty"
    assert "error" in result.payload
