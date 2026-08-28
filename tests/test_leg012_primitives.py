"""Red contract tests for LEG-012 — Primitives interface v1.

These tests pin the public contract for the three substrate primitives
(``Queue``, ``Board``, ``Lock``), the sibling protocols they expose
(``LeaseHandle``), the scheduling-by-field rule (``next_run_at``) and the
namespacing rules ``legio:queue:<agent>`` / ``legio:board:<scope>:<key>``.

The production modules imported here (``legio.primitives``) do NOT exist yet.
This file is intentionally red: it must fail because the production code is not
implemented. Conformance is asserted via ``isinstance`` against the imported
protocols, so the production protocol classes must be decorated with
``@typing.runtime_checkable``.
"""

from __future__ import annotations

import asyncio
from time import monotonic

import pytest

from legio.primitives import (
    BOARD_NAMESPACE,
    QUEUE_NAMESPACE,
    Board,
    LeaseHandle,
    Lock,
    Queue,
    board_key,
    queue_key,
)
from legio.primitives.inmemory import (
    BoardInMemory,
    LockInMemory,
    QueueInMemory,
)


def test_in_memory_primitives_conform_to_protocols() -> None:
    assert isinstance(LockInMemory(ttl=5.0), Lock)
    assert isinstance(QueueInMemory(agent_id="summ"), Queue)
    assert isinstance(BoardInMemory(scope="blackboard"), Board)


def test_queue_name_and_keys_use_legio_namespace() -> None:
    assert QUEUE_NAMESPACE == "legio:queue:"
    assert BOARD_NAMESPACE == "legio:board:"
    assert queue_key("summ") == "legio:queue:summ"
    assert queue_key("flow_a").startswith("legio:queue:")
    assert board_key("blackboard", "node-1:T-1") == "legio:board:blackboard:node-1:T-1"
    assert board_key("results", "T-42").startswith("legio:board:")


def test_board_scopes_match_architecture() -> None:
    for scope in (
        "blackboard",
        "frames",
        "semaphore",
        "results",
        "catalog",
        "outbox",
        "tasks",
    ):
        assert board_key(scope, "k").startswith("legio:board:")


def test_lock_ttl_is_observable() -> None:
    lock = LockInMemory(ttl=5.0)
    assert lock.ttl == pytest.approx(5.0)
    assert lock.expired is False


async def test_lock_expiry_is_detected() -> None:
    lock = LockInMemory(ttl=0.05)
    assert lock.expired is False
    await asyncio.sleep(0.06)
    assert lock.expired is True


def test_lock_renew_extends_ttl() -> None:
    lock = LockInMemory(ttl=0.05)
    lock.renew(ttl=10.0)
    assert lock.ttl == pytest.approx(10.0)
    assert lock.expired is False


async def test_lease_expiry_makes_item_reclaimable() -> None:
    queue = QueueInMemory(agent_id="summ")
    await queue.push({"task_id": "T-1", "payload": "hello"}, priority=1.0)

    handle = await queue.lease(lease_ttl=0.05)
    assert handle is not None
    assert isinstance(handle, LeaseHandle)
    assert handle.item["task_id"] == "T-1"
    assert handle.lock.expired is False

    concurrently_unavailable = await queue.lease(lease_ttl=5.0)
    assert concurrently_unavailable is None

    await asyncio.sleep(0.06)
    reclaim = await queue.lease(lease_ttl=5.0)
    assert reclaim is not None
    assert isinstance(reclaim, LeaseHandle)
    assert reclaim.item["task_id"] == "T-1"

    await queue.ack(reclaim)
    assert await queue.lease(lease_ttl=5.0) is None


async def test_priority_ordering_is_descending() -> None:
    queue = QueueInMemory(agent_id="summ")
    await queue.push({"task_id": "T-low"}, priority=0.0)
    await queue.push({"task_id": "T-high"}, priority=2.0)
    await queue.push({"task_id": "T-mid"}, priority=1.0)

    assert (await queue.pop())["task_id"] == "T-high"
    assert (await queue.pop())["task_id"] == "T-mid"
    assert (await queue.pop())["task_id"] == "T-low"
    assert await queue.pop() is None


async def test_lease_prefers_highest_priority() -> None:
    queue = QueueInMemory(agent_id="summ")
    await queue.push({"task_id": "T-low"}, priority=0.0)
    await queue.push({"task_id": "T-high"}, priority=2.0)

    first = await queue.lease(lease_ttl=5.0)
    assert first is not None
    assert first.item["task_id"] == "T-high"
    await queue.ack(first)


async def test_next_run_at_defers_leasing_without_scheduler() -> None:
    queue = QueueInMemory(agent_id="summ")
    future = monotonic() + 60.0
    await queue.push({"task_id": "T-now", "next_run_at": 0.0}, priority=1.0)
    await queue.push({"task_id": "T-later", "next_run_at": future}, priority=2.0)

    first = await queue.lease(lease_ttl=5.0)
    assert first is not None
    assert first.item["task_id"] == "T-now"

    deferred = await queue.lease(lease_ttl=5.0)
    assert deferred is None

    await queue.ack(first)


async def test_board_get_set_and_update() -> None:
    board = BoardInMemory(scope="blackboard")
    await board.set("input", {"text": "hello"})
    assert await board.get("input") == {"text": "hello"}
    assert await board.get("missing", default=None) is None
    await board.update("input", {"lang": "en"})
    assert await board.get("input") == {"text": "hello", "lang": "en"}


async def test_board_keys_are_namespaced() -> None:
    board = BoardInMemory(scope="blackboard")
    await board.set("node-1:T-1", {"text": "hello"})
    (stored_key,) = board.stored_keys()
    assert stored_key.startswith("legio:board:blackboard:")
