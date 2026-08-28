"""`legio.primitives` — the three substrate primitives contract (v1).

This module pins the *protocols* that every concrete substrate implementation
(queue, board, lock) must satisfy. The beaver-backed implementations (LEG-020)
and the in-memory reference used by contract tests both conform to these
protocols.

All primitives are namespaced: ``legio:queue:<agent>`` and
``legio:board:<scope>:<key>``. Default granularity: a lock is bound to a queue
item id; the queue uses priority ordering (descending) and ``next_run_at`` as a
scheduling field (no scheduler).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

QUEUE_NAMESPACE = "legio:queue:"
BOARD_NAMESPACE = "legio:board:"


def queue_key(agent_id: str) -> str:
    """Full namespaced queue name for an agent."""
    return f"{QUEUE_NAMESPACE}{agent_id}"


def board_key(scope: str, key: str) -> str:
    """Full namespaced board key under a scope (e.g. ``blackboard``)."""
    return f"{BOARD_NAMESPACE}{scope}:{key}"


@runtime_checkable
class Lock(Protocol):
    """A TTL-bound mutex; it is the *task lease*.

    Expiry makes the guarded item reclaimable. ``renew`` extends the TTL.
    """

    @property
    def ttl(self) -> float: ...

    @property
    def expired(self) -> bool: ...

    def renew(self, ttl: float) -> None: ...

    def release(self) -> None: ...


@runtime_checkable
class LeaseHandle(Protocol):
    """The result of a successful ``Queue.lease``.

    Carries the leased item and the lock (lease) that guards it.
    """

    @property
    def item(self) -> Mapping[str, Any]: ...

    @property
    def lock(self) -> Lock: ...


@runtime_checkable
class Queue(Protocol):
    """A persistent priority queue per agent.

    Ordered by priority (descending). Items carrying a future ``next_run_at``
    are not leased before they are due. ``lease`` hands out an item under a
    TTL lock; ``ack`` completes it; an expired lease makes the item reclaimable.
    """

    @property
    def name(self) -> str: ...

    async def push(self, item: Mapping[str, Any], *, priority: float = 0.0) -> None: ...

    async def lease(self, lease_ttl: float) -> LeaseHandle | None: ...

    async def ack(self, handle: LeaseHandle) -> None: ...

    async def pop(self) -> Mapping[str, Any] | None: ...


@runtime_checkable
class Board(Protocol):
    """A persistent key-value store per scope (blackboard, frames, results...).

    ``update`` deep-merges dictionaries under the key.
    """

    async def get(self, key: str, default: Any = None) -> Any: ...

    async def set(self, key: str, value: Any) -> None: ...

    async def update(self, key: str, value: Any) -> None: ...

    def stored_keys(self) -> list[str]: ...


__all__ = [
    "BOARD_NAMESPACE",
    "QUEUE_NAMESPACE",
    "Board",
    "LeaseHandle",
    "Lock",
    "Queue",
    "board_key",
    "queue_key",
]
