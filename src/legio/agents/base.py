"""`legio.agents.base` — the uniform per-step runner (LEG-023) over native beaver.

Every agent — atomic (tool/linguistic), composite and root — is a uniform
``run()`` unit. ``AgentBase`` provides that loop once: it pops a work item from
the agent's native beaver queue (``db.queue``), takes a native beaver lock as
the task lease (``db.lock``, LEG-048), dispatches it to the step's job (a
subclass ``_handle``), applies the ``retry_guard`` / ``monitor`` hooks, and
routes the outcome by position (Schema 2): advance to the next class of this
level as an ``ExecutionRequestMessage``, or — at the end of the level — deposit
an ``ExecutionResultMessage`` to the level's ``end_of_level_queue`` (the
submit's final-result queue at level 1, AGENT_LIFECYCLE §4.11). The route and
the destination travel inside the message itself: routing is always derived
from ``level_route``/``current_index``/``end_of_level_queue``, never from
caller-owned knowledge, and the step's accumulated state rides in the single
``payload`` container (Schema 2). There is **no** ``results`` board.

The actual steps (linguistic, tool, composite) plug in via ``_handle``, which
returns the carried state to route; ``ToolAgent`` (LEG-022) is one such
subclass. Failures are never silent (AGENTS.md rule 9): a raised step error is
surfaced as an ``error``-carrying result, and ``retry_guard`` decides whether
to re-run the step instead.

No invented substrate layer exists (LEG-048): the agent speaks beaver natively,
exactly as castor's Manager holds a ``db`` and calls ``db.dict``/``db.queue``/
``db.lock`` directly.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from beaver import AsyncBeaverDB

from legio.flow import ExecutionRequestMessage, ExecutionResultMessage
from legio.naming import queue_key

logger = logging.getLogger(__name__)

RetryGuard = Callable[[str, str, str, int], Awaitable[bool]]
Monitor = Callable[[str, str, str], Awaitable[None]]

_EVENT_START = "start"
_EVENT_STEP_DONE = "step_done"
_EVENT_STEP_ERROR = "step_error"
_EVENT_IDLE = "idle"


class AgentBase:
    """The uniform run loop every agent implements (LEG-023) on native beaver."""

    def __init__(
        self,
        *,
        agent_id: str,
        db: AsyncBeaverDB,
        lease_ttl: float = 60.0,
    ) -> None:
        self._agent_id = agent_id
        self._db = db
        self._lease_ttl = lease_ttl
        self._queue = db.queue(queue_key(agent_id))
        self._retry_guard: RetryGuard | None = None
        self._monitor: Monitor | None = None
        self._attempts: dict[str, int] = {}

    def set_hooks(
        self, *, retry_guard: RetryGuard | None = None, monitor: Monitor | None = None
    ) -> None:
        """Register the optional ``retry_guard`` and ``monitor`` hooks."""
        self._retry_guard = retry_guard
        self._monitor = monitor

    @property
    def agent_id(self) -> str:
        """The agent's stable identity (its queue/namespace name)."""
        return self._agent_id

    async def run(self, *, max_steps: int = 100) -> int:
        """Poll the queue until idle or ``max_steps`` reached; return steps done.

        Bounded so a misbehaving step can never starve the agent into an
        infinite busy loop.
        """
        steps = 0
        while steps < max_steps:
            handled = await self.process_next()
            if not handled:
                break
            steps += 1
        return steps

    async def process_next(self, *, lease_ttl: float | None = None) -> bool:
        """Process at most one due work item; return whether one was handled.

        The native beaver queue ``get(block=False)`` pops destructively (LEG-048);
        a native beaver lock keyed on the item is the task lease — it marks the
        item in-flight and is renewed by ``_heartbeat``, released by ``ack``, and
        would be reclaimed by the reaper on expiry (at-least-once, R-6).
        """
        ttl = lease_ttl or self._lease_ttl
        item = await self._take_due()
        if item is None:
            logger.debug("agent idle agent=%s", self._agent_id)
            return False

        item_id = self._item_id(item)
        lease = self._db.lock(f"{queue_key(self._agent_id)}:{item_id}", lock_ttl=ttl)
        held = await lease.acquire(timeout=0.0, lock_ttl=ttl, block=True)
        if not held:
            logger.debug("agent lease contention agent=%s item=%s", self._agent_id, item_id)
            await self._queue.put(dict(item), priority=0.0)
            return False

        try:
            request = ExecutionRequestMessage.model_validate(dict(item))
            logger.info(
                "agent run agent=%s task=%s level=%s index=%s",
                self._agent_id,
                request.task_id,
                request.level,
                request.current_index,
            )
            self._attempts[request.task_id] = self._attempts.get(request.task_id, 0) + 1
            await self._heartbeat(lease)
            await self._emit(_EVENT_START, request)
            await self._run_guarded(request)
        except Exception:
            logger.exception(
                "agent crashed agent=%s task=%s",
                self._agent_id,
                item.get("task_id", "?"),
            )
            raise
        finally:
            await lease.release()
        logger.debug("agent done agent=%s", self._agent_id)
        return True

    async def _take_due(self) -> Mapping[str, Any] | None:
        """Pop the next due item from the native queue, rotating not-due items."""
        seen: set[str] = set()
        while True:
            try:
                qitem = await self._queue.get(block=False)
            except IndexError:
                return None
            item = qitem.data
            if self._is_due(item):
                return item
            item_id = self._item_id(item)
            if item_id in seen:
                await self._queue.put(dict(item), priority=0.0)
                return None
            seen.add(item_id)
            await self._queue.put(dict(item), priority=0.0)

    def _is_due(self, item: Mapping[str, Any]) -> bool:
        return float(item.get("next_run_at", 0.0)) <= time.time()

    def _item_id(self, item: Mapping[str, Any]) -> str:
        return str(item.get("task_id") or item.get("id") or id(item))

    async def _run_guarded(self, request: ExecutionRequestMessage) -> None:
        """Run the step job and route its outcome, or route a raised failure."""
        try:
            carried = await self._handle(request)
        except Exception as exc:  # noqa: BLE001 - surfaced, never swallowed
            error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "agent step error agent=%s task=%s error=%s",
                self._agent_id,
                request.task_id,
                error,
            )
            await self._emit(_EVENT_STEP_ERROR, request)
            attempt = self._attempts.get(request.task_id, 1)
            should_retry = await self._should_retry(request, error, attempt)
            if should_retry:
                logger.info(
                    "agent retry agent=%s task=%s attempt=%s",
                    self._agent_id,
                    request.task_id,
                    attempt,
                )
                await self._retry(request)
                return
            await self._route_outcome(request, {"error": error})
            return
        if carried is not None:
            await self._route_outcome(request, carried)
            await self._emit(_EVENT_STEP_DONE, request)

    async def _should_retry(
        self, request: ExecutionRequestMessage, error: str, attempt: int
    ) -> bool:
        if self._retry_guard is None:
            return False
        return bool(await self._retry_guard(self._agent_id, request.task_id, error, attempt))

    async def _retry(self, request: ExecutionRequestMessage) -> None:
        """Re-enqueue the request so the step runs again after ack."""
        await self._queue.put(request.model_dump(mode="json"), priority=0.0)

    async def _emit(self, event: str, request: ExecutionRequestMessage | None) -> None:
        if self._monitor is None:
            return
        task_id = request.task_id if request is not None else "?"
        await self._monitor(self._agent_id, task_id, event)

    async def _heartbeat(self, lease: Any) -> None:
        """Renew the item's lease so a live replica keeps it out of reaper.

        Polling-only (AGENTS.md rule 8): there is no sleep; the renewal happens
        on each item we pick up, keeping the lease alive for the duration of the
        step. Continuous in-work heartbeating is R-6 (resilience).
        """
        await lease.renew(self._lease_ttl)
        logger.debug("agent heartbeat agent=%s", self._agent_id)

    async def _route_outcome(
        self, request: ExecutionRequestMessage, payload: dict[str, Any]
    ) -> None:
        """Route the carried state to the next class or the level closer.

        Routing is Schema 2 position-based: while ``current_index + 1`` is inside
        ``level_route`` the outcome advances to ``level_route[current_index + 1]``
        as an ``ExecutionRequestMessage``; at the end of the level it is
        deposited to ``end_of_level_queue`` as an ``ExecutionResultMessage`` (the
        submit's final-result queue at ``level == 1``). The destination is never
        caller-owned — everything rides in the message (ARCHITECTURE §0/§3).
        """
        next_index = request.current_index + 1
        if next_index < len(request.level_route):
            next_class = request.level_route[next_index]
            logger.info(
                "agent advance agent=%s task=%s level=%s to=%s index=%s",
                self._agent_id,
                request.task_id,
                request.level,
                next_class,
                next_index,
            )
            next_request = ExecutionRequestMessage(
                level_route=request.level_route,
                current_index=next_index,
                end_of_level_queue=request.end_of_level_queue,
                level=request.level,
                launcher_class=request.launcher_class,
                task_id=request.task_id,
                payload=payload,
            )
            await self._deliver(next_class, next_request.model_dump(mode="json"))
            return

        if request.level == 1:
            logger.info(
                "agent finish agent=%s task=%s to_end_queue=%s",
                self._agent_id,
                request.task_id,
                request.end_of_level_queue,
            )
        else:
            logger.info(
                "agent branch close agent=%s task=%s level=%s to=%s",
                self._agent_id,
                request.task_id,
                request.level,
                request.end_of_level_queue,
            )
        result = ExecutionResultMessage(
            level_route=request.level_route,
            current_index=request.current_index,
            end_of_level_queue=request.end_of_level_queue,
            level=request.level,
            launcher_class=request.launcher_class,
            task_id=request.task_id,
            payload=payload,
        )
        await self._deliver(request.end_of_level_queue, result.model_dump(mode="json"))

    async def _deliver(self, target: str, item: dict[str, Any]) -> None:
        """Put the message onto a queue by name (class or level closer)."""
        await self._db.queue(queue_key(target)).put(dict(item), priority=0.0)

    async def _handle(
        self, request: ExecutionRequestMessage
    ) -> dict[str, Any] | None:  # pragma: no cover - abstract
        """Execute the step's job; return the carried state (or None to drop).

        Implemented by concrete agents. A returned dict is routed by position by
        ``_route_outcome``; a raised exception is surfaced as an error result by
        ``_run_guarded``.
        """
        raise NotImplementedError


__all__ = ["AgentBase"]
