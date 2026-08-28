"""Integration tests for LEG-020 — primitives over beaver.

Runs the LEG-012 conformance behavior against a real local ``AsyncBeaverDB``
(SQLite, temp file / in-memory): priority ordering, ``next_run_at`` retry
scheduling, lease TTL + renewal.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from beaver import AsyncBeaverDB

from legio.primitives import LeaseHandle
from legio.primitives.beaver import BeaverBoard, BeaverLock, BeaverQueue


@pytest.fixture
async def db() -> AsyncGenerator[AsyncBeaverDB]:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    beaver = AsyncBeaverDB(path)
    await beaver.connect()
    try:
        yield beaver
    finally:
        await beaver.close()
        Path(path).unlink(missing_ok=True)


async def test_queue_priority_ordering_descending_push_order(db: AsyncBeaverDB) -> None:
    queue = BeaverQueue(db, "summ")
    await queue.push({"task_id": "T-low"}, priority=0.0)
    await queue.push({"task_id": "T-high"}, priority=2.0)
    await queue.push({"task_id": "T-mid"}, priority=1.0)

    high = await queue.pop()
    mid = await queue.pop()
    low = await queue.pop()
    assert high is not None and high["task_id"] == "T-high"
    assert mid is not None and mid["task_id"] == "T-mid"
    assert low is not None and low["task_id"] == "T-low"
    assert await queue.pop() is None


async def test_queue_lease_returns_item_and_ack_completes(db: AsyncBeaverDB) -> None:
    queue = BeaverQueue(db, "summ")
    await queue.push({"task_id": "T-1"}, priority=1.0)

    handle = await queue.lease(lease_ttl=5.0)
    assert isinstance(handle, LeaseHandle)
    assert handle.item["task_id"] == "T-1"
    assert handle.lock.expired is False

    await queue.ack(handle)
    assert await queue.lease(lease_ttl=5.0) is None


async def test_lease_ttl_and_renew_observable(db: AsyncBeaverDB) -> None:
    queue = BeaverQueue(db, "summ")
    await queue.push({"task_id": "T-1"}, priority=1.0)
    handle = await queue.lease(lease_ttl=0.2)
    assert isinstance(handle, LeaseHandle)
    assert handle.lock.ttl == pytest.approx(0.2)
    assert handle.lock.expired is False

    await asyncio.sleep(0.05)
    assert isinstance(handle.lock, BeaverLock)
    await handle.lock.renew_async(lock_ttl=5.0)
    assert handle.lock.ttl == pytest.approx(5.0)
    assert handle.lock.expired is False
    await queue.ack(handle)


async def test_next_run_at_defers_lease_without_scheduler(db: AsyncBeaverDB) -> None:
    queue = BeaverQueue(db, "summ")
    future = time.time() + 60.0
    await queue.push({"task_id": "T-now", "next_run_at": 0.0}, priority=1.0)
    await queue.push({"task_id": "T-later", "next_run_at": future}, priority=2.0)

    first = await queue.lease(lease_ttl=5.0)
    assert first is not None
    assert first.item["task_id"] == "T-now"

    deferred = await queue.lease(lease_ttl=5.0)
    assert deferred is None

    await queue.ack(first)


async def test_board_set_get_and_update(db: AsyncBeaverDB) -> None:
    board = BeaverBoard(db, "blackboard")
    await board.set("input", {"text": "hello"})
    assert await board.get("input") == {"text": "hello"}
    assert await board.get("missing", default=None) is None
    await board.update("input", {"lang": "en"})
    assert await board.get("input") == {"text": "hello", "lang": "en"}


async def test_board_keys_are_namespaced(db: AsyncBeaverDB) -> None:
    board = BeaverBoard(db, "blackboard")
    await board.set("node-1:T-1", {"text": "hello"})
    stored = board.stored_keys()
    assert any(k.startswith("legio:board:blackboard:") for k in stored)


async def test_lock_conforms_to_lease_contract(db: AsyncBeaverDB) -> None:
    beaver_lock = db.lock("legio:queue:summ:T-1", lock_ttl=5.0, timeout=0.0)
    lock = BeaverLock(beaver_lock, lock_ttl=5.0)
    assert await lock.acquire_async(timeout=0.0, lock_ttl=5.0) is True
    assert lock.expired is False
    assert await lock.renew_async(lock_ttl=10.0) is True
    assert lock.ttl == pytest.approx(10.0)
    await lock.release_async()
