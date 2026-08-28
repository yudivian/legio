"""`legio.primitives.beaver` — beaver-backed implementations (LEG-020).

Implements the LEG-012 protocols (``Queue``, ``Board``, ``Lock``) on top of a
single local ``AsyncBeaverDB`` (SQLite). Beaver's priority queue has no native
``lease``/``ack`` — ``get`` pops destructively — so ``BeaverQueue.lease`` takes
an item and guards it with a TTL ``BeaverLock`` (the task lease). On expiry the
**reaper** (R-6) re-inserts the item; that reclaim path is out of scope here.

All calls are async. The lock also satisfies the synchronous ``Lock`` protocol
so a ``LeaseHandle.lock`` can be handed to code that expects the contract.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping
from typing import Any

from beaver import AsyncBeaverDB
from beaver.locks import AsyncBeaverLock
from beaver.queues import AsyncBeaverQueue

from legio.primitives import (
    Board,
    LeaseHandle,
    Lock,
    Queue,
    board_key,
    queue_key,
)

logger = logging.getLogger(__name__)

_DEFAULT_MODEL: dict[str, Any] | None = None


class BeaverLock(Lock):
    """TTL mutex over ``AsyncBeaverLock``; also the task lease.

    Tracks wall-clock so ``.ttl`` / ``.expired`` are observable synchronously
    (beaver exposes neither). ``renew``/``release`` are async; the synchronous
    protocol methods schedule them onto the running loop when one exists.
    """

    def __init__(
        self,
        beaver_lock: AsyncBeaverLock,
        lock_ttl: float = 60.0,
    ) -> None:
        self._lock = beaver_lock
        self._lock_ttl = lock_ttl
        self._expires_at = 0.0
        self._acquired_at = 0.0

    @property
    def ttl(self) -> float:
        return self._lock_ttl

    @property
    def expired(self) -> bool:
        return self._expires_at > 0.0 and time.monotonic() > self._expires_at

    def renew(self, ttl: float) -> None:
        self._schedule(self.renew_async(ttl))

    def release(self) -> None:
        self._schedule(self.release_async())

    def _schedule(self, coro: Any) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(coro)

    async def acquire_async(
        self,
        timeout: float | None = None,
        lock_ttl: float | None = None,
        block: bool = True,
    ) -> bool:
        ttl = lock_ttl or self._lock_ttl
        acquired = await self._lock.acquire(timeout=timeout, lock_ttl=ttl, block=block)
        if acquired:
            self._expires_at = time.monotonic() + ttl
            self._acquired_at = time.monotonic()
        return acquired

    async def renew_async(self, lock_ttl: float | None = None) -> bool:
        ttl = lock_ttl or self._lock_ttl
        renewed = await self._lock.renew(ttl)
        if renewed:
            self._lock_ttl = ttl
            self._expires_at = time.monotonic() + ttl
        return renewed

    async def release_async(self) -> None:
        await self._lock.release()
        self._expires_at = 0.0


class _LeaseHandle(LeaseHandle):
    def __init__(self, item: Mapping[str, Any], lock: BeaverLock) -> None:
        self._item = item
        self._lock = lock

    @property
    def item(self) -> Mapping[str, Any]:
        return self._item

    @property
    def lock(self) -> Lock:
        return self._lock


class BeaverQueue(Queue):
    """Persistent priority queue over beaver.

    Posts an item and returns it for a ``LeaseHandle``; the handle is guarded
    by a TTL ``BeaverLock``. ``ack`` completes it (removed by beaver's ``get``);
    on lease expiry the reaper re-inserts it. Items with a future
    ``next_run_at`` are not leased before they are due.
    """

    def __init__(self, db: AsyncBeaverDB, agent_id: str) -> None:
        self._db = db
        self._agent_id = agent_id
        self._queue: AsyncBeaverQueue = db.queue(queue_key(agent_id))
        self._name = queue_key(agent_id)

    @property
    def name(self) -> str:
        return self._name

    async def push(self, item: Mapping[str, Any], *, priority: float = 0.0) -> None:
        await self._queue.put(dict(item), priority=-priority)
        logger.debug(
            "queue push agent=%s item=%s priority=%s", self._agent_id, self._item_id(item), priority
        )

    async def lease(self, lease_ttl: float) -> LeaseHandle | None:
        while True:
            item = await self._try_take_due()
            if item is None:
                logger.debug("queue lease idle agent=%s", self._agent_id)
                return None
            item_id = self._item_id(item)
            beaver_lock = self._db.lock(f"{self._name}:{item_id}", lock_ttl=lease_ttl, timeout=0.0)
            lock = BeaverLock(beaver_lock, lock_ttl=lease_ttl)
            held = await lock.acquire_async(timeout=0.0, lock_ttl=lease_ttl)
            if held:
                logger.info(
                    "queue lease acquired agent=%s item=%s ttl=%s",
                    self._agent_id,
                    item_id,
                    lease_ttl,
                )
                return _LeaseHandle(item, lock)
            logger.debug("queue lease contention agent=%s item=%s", self._agent_id, item_id)
            await self._queue.put(dict(item), priority=-self._effective_priority(item))

    async def ack(self, handle: LeaseHandle) -> None:
        if isinstance(handle.lock, BeaverLock):
            await handle.lock.release_async()
        logger.debug("queue ack agent=%s item=%s", self._agent_id, self._item_id(handle.item))

    async def pop(self) -> Mapping[str, Any] | None:
        return await self._try_take_due()

    async def _try_take_due(self) -> Mapping[str, Any] | None:
        seen: set[str] = set()
        while True:
            try:
                item = await self._queue.get(block=False)
            except IndexError:
                return None
            if self._is_due(item.data):
                return item.data
            item_id = self._item_id(item.data)
            if item_id in seen:
                await self._queue.put(
                    dict(item.data), priority=-self._effective_priority(item.data)
                )
                return None
            seen.add(item_id)
            await self._queue.put(dict(item.data), priority=-self._effective_priority(item.data))

    def _is_due(self, item: Mapping[str, Any]) -> bool:
        next_run_at = item.get("next_run_at", 0.0)
        return next_run_at <= time.time()

    def _effective_priority(self, item: Mapping[str, Any]) -> float:
        next_run_at = item.get("next_run_at")
        if next_run_at is None:
            return float(item.get("priority", 0.0))
        return float(item.get("priority", 0.0))

    def _item_id(self, item: Mapping[str, Any]) -> str:
        return str(item.get("task_id") or item.get("id") or id(item))


class BeaverBoard(Board):
    """Persistent key-value board over beaver, namespaced per scope.

    Keys exposed through ``get``/``set``/``update``/``stored_keys`` carry the
    ``legio:board:<scope>:<key>`` prefix; the underlying beaver dictionary uses
    the scope as its table name and raw keys internally.
    """

    def __init__(self, db: AsyncBeaverDB, scope: str, *, ttl_seconds: float | None = None) -> None:
        self._scope = scope
        self._dict = db.dict(scope)
        self._ttl_seconds = ttl_seconds
        self._raw_keys: set[str] = set()

    async def get(self, key: str, default: Any = None) -> Any:
        try:
            return await self._dict.get(key)
        except KeyError:
            return default

    async def set(self, key: str, value: Any) -> None:
        await self._dict.set(key, value, ttl_seconds=self._ttl_seconds)
        self._raw_keys.add(key)
        logger.debug("board set scope=%s key=%s", self._scope, key)

    async def update(self, key: str, value: Any) -> None:
        current = await self.get(key, default={})
        if isinstance(value, dict) and isinstance(current, dict):
            merged = dict(current)
            merged.update(value)
            await self._dict.set(key, merged, ttl_seconds=self._ttl_seconds)
        else:
            await self._dict.set(key, value, ttl_seconds=self._ttl_seconds)
        self._raw_keys.add(key)
        logger.debug("board update scope=%s key=%s", self._scope, key)

    def stored_keys(self) -> list[str]:
        return [board_key(self._scope, key) for key in sorted(self._raw_keys)]


__all__ = ["BeaverBoard", "BeaverLock", "BeaverQueue"]
