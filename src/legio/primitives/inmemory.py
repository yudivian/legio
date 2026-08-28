"""`legio.primitives.inmemory` — in-memory reference substrate (LEG-012).

A dependency-free, namespaced implementation of the LEG-012 protocols used as
the reference substrate for contract tests and local examples. It is *not* the
production backend — beaver (LEG-020) is — but it conforms to the same
protocols so logic written against the protocols runs identically on either.
"""

from __future__ import annotations

from collections.abc import Mapping
from time import monotonic
from typing import Any

from legio.primitives import Lock, board_key, queue_key


class LockInMemory(Lock):
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


__all__ = [
    "BoardInMemory",
    "LeaseHandleInMemory",
    "LockInMemory",
    "QueueEntryInMemory",
    "QueueInMemory",
]
