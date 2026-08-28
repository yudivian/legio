"""`legio.agents.base` — the uniform per-step runner (LEG-023).

Every agent — atomic (tool/linguistic), composite and root — is a uniform
``run()`` unit. ``AgentBase`` provides that loop once: it leases a work item
from the agent's queue, dispatches it to the step's job (a subclass
``_handle``), applies the ``retry_guard`` / ``monitor`` hooks, and routes the
outcome — advance to the next stage as an ``ExecutionRequestMessage``, or finish
by depositing an ``ExecutionResultMessage`` to the parent/client (finality by
position, LEG-011).

The actual steps (linguistic, tool, composite) plug in via ``_handle``;
``ToolAgent`` (LEG-022) is one such subclass. Failures are never silent
(AGENTS.md rule 9): a raised step error is surfaced as an ``error`` result, and
``retry_guard`` decides whether to re-run the step instead.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from legio.errors import UnrecoverableError
from legio.flow import ExecutionRequestMessage, ExecutionResultMessage
from legio.primitives import Board, LeaseHandle, Queue

logger = logging.getLogger(__name__)

RetryGuard = Callable[[str, str, str, int], Awaitable[bool]]
Monitor = Callable[[str, str, str], Awaitable[None]]

_EVENT_START = "start"
_EVENT_STEP_DONE = "step_done"
_EVENT_STEP_ERROR = "step_error"
_EVENT_IDLE = "idle"


class AgentBase:
    """The uniform run loop every agent implements (LEG-023)."""

    def __init__(
        self,
        *,
        agent_id: str,
        queue: Queue,
        board: Board,
        queues: Mapping[str, Queue],
        frames_scope: str = "frames",
        lease_ttl: float = 60.0,
        results_board: Board | None = None,
    ) -> None:
        self._agent_id = agent_id
        self._queue = queue
        self._board = board
        self._queues = queues
        self._frames_scope = frames_scope
        self._lease_ttl = lease_ttl
        self._results_board = results_board
        self._retry_guard: RetryGuard | None = None
        self._monitor: Monitor | None = None
        self._attempts: dict[str, int] = {}

    def set_hooks(
        self, *, retry_guard: RetryGuard | None = None, monitor: Monitor | None = None
    ) -> None:
        """Register the optional ``retry_guard`` and ``monitor`` hooks."""
        self._retry_guard = retry_guard
        self._monitor = monitor

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
        """Process at most one due work item; return whether one was handled."""
        ttl = lease_ttl or self._lease_ttl
        handle = await self._queue.lease(ttl)
        if handle is None:
            logger.debug("agent idle agent=%s", self._agent_id)
            return False

        try:
            request = ExecutionRequestMessage.model_validate(dict(handle.item))
            logger.info(
                "agent run agent=%s task=%s step=%s",
                self._agent_id,
                request.task_id,
                request.current_index,
            )
            self._attempts[request.task_id] = self._attempts.get(request.task_id, 0) + 1
            await self._heartbeat(handle)
            await self._emit(_EVENT_START, request)
            await self._run_guarded(request, handle)
        except Exception:
            logger.exception(
                "agent crashed agent=%s task=%s",
                self._agent_id,
                handle.item.get("task_id", "?"),
            )
            raise
        finally:
            await self._queue.ack(handle)
        logger.debug("agent done agent=%s", self._agent_id)
        return True

    async def _run_guarded(self, request: ExecutionRequestMessage, handle: LeaseHandle) -> None:
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
                await self._retry(request, handle)
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

    async def _retry(self, request: ExecutionRequestMessage, _handle: LeaseHandle) -> None:
        """Re-enqueue the request so the step runs again after ack."""
        await self._queue.push(request.model_dump(mode="json"))

    async def _emit(self, event: str, request: ExecutionRequestMessage | None) -> None:
        if self._monitor is None:
            return
        task_id = request.task_id if request is not None else "?"
        await self._monitor(self._agent_id, task_id, event)

    async def _frame(self, request: ExecutionRequestMessage) -> dict[str, Any]:
        """Read the staged frame for this agent/task from the blackboard."""
        frame = await self._board.get(f"{self._agent_id}:{request.task_id}", default={})
        return dict(frame or {})

    async def _store_out(
        self, request: ExecutionRequestMessage, key: str, output: dict[str, Any]
    ) -> None:
        """Deep-merge ``output`` under the staged frame's ``key``."""
        frame = await self._frame(request)
        frame[key] = output
        await self._board.update(f"{self._agent_id}:{request.task_id}", frame)

    async def _heartbeat(self, handle: LeaseHandle) -> None:
        """Renew the item's lease so a live replica keeps it out of reaper.

        Polling-only (AGENTS.md rule 8): there is no sleep; the renewal happens
        on each item we pick up, keeping the lease alive for the duration of the
        step. Continuous in-work heartbeating is R-6 (resilience).
        """
        handle.lock.renew(self._lease_ttl)
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
        if (
            request.ultimate_return_agent_id.startswith("client:")
            and self._results_board is not None
        ):
            await self._results_board.set(request.task_id, {"output": output})
            logger.info("agent root result agent=%s task=%s", self._agent_id, request.task_id)

    async def _deliver(self, target_agent_id: str, item: dict[str, Any]) -> None:
        target = self._queues.get(target_agent_id)
        if target is None:
            raise KeyError(f"no queue registered for agent {target_agent_id!r}")
        await target.push(item)

    async def _handle(
        self, request: ExecutionRequestMessage
    ) -> None:  # pragma: no cover - abstract
        """Execute the step's job. Implemented by concrete agents."""
        raise NotImplementedError


__all__ = ["AgentBase"]
