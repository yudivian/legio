"""Tests for LEG-014 — Mini-manager (over native beaver).

These tests pin the public contract for the mini-manager: async ``submit`` /
``status`` over the native beaver ``tasks`` dictionary and the per-agent queues
(LEG-048, no invented substrate), the root result landing on the task's
final-result queue (Schema 2 ``end_of_level_queue``, read via ``status``), task
ownership tagging (per LEG-017) and root-token semantics (per LEG-011). No
``results`` board and no per-task ``client:`` queue (addendum AL).
"""

from __future__ import annotations

import pytest
from beaver import AsyncBeaverDB

from legio.flow import ExecutionResultMessage, FlowToken
from legio.manager import TaskState, status, submit
from legio.naming import queue_key, result_queue_key


@pytest.mark.asyncio
async def test_submit_returns_task_id_and_tags_owner(beaver_db: AsyncBeaverDB) -> None:
    task_id = await submit("client-a", "flow_alpha", {"raw": 1})
    assert isinstance(task_id, str)
    assert task_id

    entry = await status(task_id, "client-a")
    assert entry.task_id == task_id
    assert entry.owner == "client-a"
    assert entry.output is None


@pytest.mark.asyncio
async def test_root_result_lands_in_final_result_queue_readable_via_status(
    beaver_db: AsyncBeaverDB,
) -> None:
    task_id = await submit("client-a", "flow_alpha", {"raw": 1})

    result = ExecutionResultMessage(
        task_id=task_id,
        level_route=("flow_alpha",),
        current_index=0,
        end_of_level_queue=result_queue_key(task_id),
        payload={"raw": 1, "kind": "ok"},
    )
    await beaver_db.queue(queue_key(result_queue_key(task_id))).put(
        result.model_dump(mode="json"), priority=0.0
    )

    entry = await status(task_id, "client-a")
    assert entry.output == {"raw": 1, "kind": "ok"}
    assert entry.result_key == result_queue_key(task_id)
    assert entry.state is TaskState.COMPLETED


@pytest.mark.asyncio
async def test_status_is_scoped_to_the_owning_client(beaver_db: AsyncBeaverDB) -> None:
    task_id = await submit("client-a", "flow_alpha", {"raw": 1})

    with pytest.raises(PermissionError):
        await status(task_id, "client-b")

    with pytest.raises(PermissionError):
        await status(task_id, None)


@pytest.mark.asyncio
async def test_submitted_task_holds_root_token_with_result_queue_target(
    beaver_db: AsyncBeaverDB,
) -> None:
    task_id = await submit("client-a", "flow_alpha", {"raw": 1})

    entry = await status(task_id, "client-a")
    token = entry.token
    assert isinstance(token, FlowToken)
    assert token.root is True
    assert token.task_id == task_id
    assert token.level == 1
    assert token.end_of_level_queue == result_queue_key(task_id)


@pytest.mark.asyncio
async def test_submitted_task_stays_pending_until_root_result(
    beaver_db: AsyncBeaverDB,
) -> None:
    task_id = await submit("client-a", "flow_alpha", {"raw": 1})

    entry = await status(task_id, "client-a")
    assert entry.state is TaskState.PENDING
    assert entry.result_key is None
