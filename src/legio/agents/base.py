"""`legio.agents.base` — the uniform per-step runner (LEG-023) over native beaver.

Every agent — atomic (tool/linguistic), composite and root — is a uniform
``run()`` unit. ``AgentBase`` provides that loop once: it pops a work item from
the agent's native beaver queue (``db.queue``), takes a native beaver lock as
the task lease (``db.lock``, LEG-048), dispatches it to the step's job (a
subclass ``_handle``), applies the ``retry_guard`` / ``monitor`` hooks, and
routes the outcome — advance to the next stage as an ``ExecutionRequestMessage``,
or finish by depositing an ``ExecutionResultMessage`` to the parent/client
(finality by position, LEG-011). Frames and results live on native beaver
dictionaries (``db.dict``); boards are addressed by their scope name directly.

The actual steps (linguistic, tool, composite) plug in via ``_handle``;
``ToolAgent`` (LEG-022) is one such subclass. Failures are never silent
(AGENTS.md rule 9): a raised step error is surfaced as an ``error`` result, and
``retry_guard`` decides whether to re-run the step instead.

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

from legio.errors import UnrecoverableError
from legio.flow import ExecutionRequestMessage, ExecutionResultMessage
from legio.naming import queue_key

logger = logging.getLogger(__name__)

RetryGuard = Callable[[str, str, str, int], Awaitable[bool]]
Monitor = Callable[[str, str, str], Awaitable[None]]

_EVENT_START = "start"
_EVENT_STEP_DONE = "step_done"
_EVENT_STEP_ERROR = "step_error"
_EVENT_IDLE = "idle"

_FRAMES_SCOPE = "frames"
_RESULTS_SCOPE = "results"


class AgentBase:
    """The uniform run loop every agent implements (LEG-023) on native beaver."""

    def __init__(
        self,
        *,
        agent_id: str,
        db: AsyncBeaverDB,
        frames_scope: str = _FRAMES_SCOPE,
        lease_ttl: float = 60.0,
    ) -> None:
        self._agent_id = agent_id
        self._db = db
        self._frames_scope = frames_scope
        self._lease_ttl = lease_ttl
        self._queue = db.queue(queue_key(agent_id))
        self._frames = db.dict(frames_scope)
        self._results = db.dict(_RESULTS_SCOPE)
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

        Bounded so a misbehaving step can never starve the worker into an
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
                "agent run agent=%s task=%s step=%s",
                self._agent_id,
                request.task_id,
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
        """Run the step job, routing a raised failure to retry or error result."""
        try:
            await self._handle(request)
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
            await self._finish(request, {"error": error})
            return
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

    async def _frame(self, request: ExecutionRequestMessage) -> dict[str, Any]:
        """Read the staged frame for this agent/task from the frames dictionary."""
        frame = await self._frames.fetch(f"{self._agent_id}:{request.task_id}", {})
        return dict(frame or {})

    async def _store_out(
        self, request: ExecutionRequestMessage, key: str, output: dict[str, Any]
    ) -> None:
        """Deep-merge ``output`` under the staged frame's ``key``."""
        frame = await self._frame(request)
        frame[key] = output
        await self._frames.set(f"{self._agent_id}:{request.task_id}", frame)

    async def _heartbeat(self, lease: Any) -> None:
        """Renew the item's lease so a live replica keeps it out of reaper.

        Polling-only (AGENTS.md rule 8): there is no sleep; the renewal happens
        on each item we pick up, keeping the lease alive for the duration of the
        step. Continuous in-work heartbeating is R-6 (resilience).
        """
        await lease.renew(self._lease_ttl)
        logger.debug("agent heartbeat agent=%s", self._agent_id)

    async def _advance(self, request: ExecutionRequestMessage, *, output: dict[str, Any]) -> None:
        """Route the outcome to the next agent in the DAG carried by the token.

        The next queue is derived from the token itself — the CPS continuation
        (``route_pattern_names[current_index + 1]``) — never from caller-owned
        knowledge (ARCHITECTURE §0/§3). There is no central engine; the agent
        decides only from its message and the token.
        """
        next_index = request.current_index + 1
        names = request.route_pattern_names
        if next_index >= len(names):
            raise UnrecoverableError(f"agent {self._agent_id} advanced beyond the end of its DAG")
        next_agent_id = names[next_index]
        logger.info(
            "agent advance agent=%s task=%s to=%s index=%s",
            self._agent_id,
            request.task_id,
            next_agent_id,
            next_index,
        )
        next_request = ExecutionRequestMessage(
            route_pattern_names=request.route_pattern_names,
            current_index=next_index,
            ultimate_return_agent_id=request.ultimate_return_agent_id,
            origin_node_id=request.origin_node_id,
            task_id=request.task_id,
            payload={"input": output},
        )
        await self._deliver(next_agent_id, next_request.model_dump(mode="json"))

    async def _finish(self, request: ExecutionRequestMessage, output: dict[str, Any]) -> None:
        """Deposit the ExecutionResultMessage to the return agent.

        For a root task (``ultimate_return_agent_id == client:{task_id}``) the
        result is additionally written to ``results:{task_id}`` so the client
        reads it back via ``status`` (ARCH §6/§7.6, LEG-050). Deliveries are at
        least-once; exactly-once ack is R-5 (LEG-050).
        """
        logger.info(
            "agent finish agent=%s task=%s to=%s",
            self._agent_id,
            request.task_id,
            request.ultimate_return_agent_id,
        )
        result = ExecutionResultMessage(
            route_pattern_names=request.route_pattern_names,
            current_index=request.current_index,
            ultimate_return_agent_id=request.ultimate_return_agent_id,
            origin_node_id=request.origin_node_id,
            task_id=request.task_id,
            output=output,
        )
        await self._deliver(request.ultimate_return_agent_id, result.model_dump(mode="json"))
        if request.ultimate_return_agent_id.startswith("client:"):
            await self._results.set(request.task_id, {"output": output})
            logger.info("agent root result agent=%s task=%s", self._agent_id, request.task_id)

    async def _deliver(self, target_agent_id: str, item: dict[str, Any]) -> None:
        """Put the message onto the target agent's native beaver queue, by name."""
        await self._db.queue(queue_key(target_agent_id)).put(dict(item), priority=0.0)

    async def _handle(
        self, request: ExecutionRequestMessage
    ) -> None:  # pragma: no cover - abstract
        """Execute the step's job. Implemented by concrete agents."""
        raise NotImplementedError


__all__ = ["AgentBase"]
