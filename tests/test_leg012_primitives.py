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
from collections.abc import Mapping
from time import monotonic
from typing import Any

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


class LockInMemory:
    """In-memory reference implementation of the Lock contract."""

    def __init__(self, ttl: float) -> None:
        self._ttl = ttl
        self._acquired_at = monotonic()
        self._released = False

    @property
    def ttl(self) -> float:
        return self._ttl

    @property
    def expired(self) -> bool:
        return self._released or monotonic() - self._acquired_at >= self._ttl

    def renew(self, ttl: float) -> None:
        self._ttl = ttl
        self._acquired_at = monotonic()

    def release(self) -> None:
        self._released = True


class QueueEntryInMemory:
    def __init__(self, item: Mapping[str, Any], priority: float) -> None:
        self.item = item
        self.priority = priority
        self.lock: LockInMemory | None = None


class LeaseHandleInMemory:
    """In-memory reference implementation of the LeaseHandle contract."""

    def __init__(self, entry: QueueEntryInMemory) -> None:
        self.entry = entry

    @property
    def item(self) -> Mapping[str, Any]:
        return self.entry.item

    @property
    def lock(self) -> LockInMemory:
        assert self.entry.lock is not None
        return self.entry.lock


class QueueInMemory:
    """In-memory reference implementation of the Queue contract.

    Orders by priority (descending); items carrying a future ``next_run_at``
    are not leased before they are due; an expired lease makes the item
    reclaimable again.
    """

    def __init__(self, agent_id: str) -> None:
        self.name = queue_key(agent_id)
        self._entries: list[QueueEntryInMemory] = []

    async def push(self, item: Mapping[str, Any], *, priority: float = 0.0) -> None:
        self._entries.append(QueueEntryInMemory(item, priority))

    async def lease(self, lease_ttl: float) -> LeaseHandleInMemory | None:
        self._reap_expired()
        now = monotonic()
        due_entries = [
            entry
            for entry in self._entries
            if entry.lock is None and entry.item.get("next_run_at", 0.0) <= now
        ]
        if not due_entries:
            return None
        chosen = max(due_entries, key=lambda entry: entry.priority)
        chosen.lock = LockInMemory(ttl=lease_ttl)
        return LeaseHandleInMemory(chosen)

    async def ack(self, handle: LeaseHandleInMemory) -> None:
        self._entries.remove(handle.entry)

    async def pop(self) -> Mapping[str, Any] | None:
        self._reap_expired()
        available = [entry for entry in self._entries if entry.lock is None]
        if not available:
            return None
        chosen = max(
            available,
            key=lambda entry: (entry.priority, -entry.item.get("next_run_at", 0.0)),
        )
        self._entries.remove(chosen)
        return chosen.item

    def _reap_expired(self) -> None:
        for entry in self._entries:
            if entry.lock is not None and entry.lock.expired:
                entry.lock = None


class BoardInMemory:
    """In-memory reference implementation of the Board contract."""

    def __init__(self, scope: str) -> None:
        self._scope = scope
        self._data: dict[str, Any] = {}

    async def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(board_key(self._scope, key), default)

    async def set(self, key: str, value: Any) -> None:
        self._data[board_key(self._scope, key)] = value

    async def update(self, key: str, value: Any) -> None:
        namespaced_key = board_key(self._scope, key)
        current = self._data.get(namespaced_key, {})
        if isinstance(current, dict) and isinstance(value, dict):
            merged = dict(current)
            merged.update(value)
            self._data[namespaced_key] = merged
        else:
            self._data[namespaced_key] = value

    def stored_keys(self) -> list[str]:
        return list(self._data)


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
