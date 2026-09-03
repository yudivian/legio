"""`legio.agents.parallel_agent` — the ParallelAgent runner (LEG-041, R-4).

A parallel composite fans out its branches concurrently and joins their results
(AGENT_LIFECYCLE §12.3/§12.4, ARCHITECTURE §7). It collapses the model's two
queues (inbox + gathering) into one physical queue by message-type dispatch
(the contract explicitly allows this): branch returns land on the parallel's
own queue and ``_handle`` dispatches on ``message_type``.

The **task id is the task's identity** and never changes anywhere in the flow,
including across a fan-out (AGENTS.md / Schema 2): every branch is deposited
with the SAME ``task_id`` as its parallel parent, so a branch result arrives
with that same ``task_id`` and the parallel keys its join bookkeeping directly
on it — there is no child→parent lookup and no scanning; everything the
parallel needs to resume rides in the message.
``state:parallel:<agent_id>`` holds only the in-flight continuation per task.

- **Fan-out** (``execution_request``): each branch is deposited to the child
  class's inbox with ``level_route = (branch_class,)``, ``current_index = 0``,
  ``level + 1``, ``end_of_level_queue`` = this parallel's own queue (its
  gathering queue, collapsed) and the SAME ``task_id``. The parallel does not
  advance; it records its continuation in the join state keyed by that task id.
- **Fan-in** (``execution_result``): the result's ``level_route[0]`` names the
  branch slot and its ``task_id`` is the join key (direct ``fetch``, no scan).
  When all branches of the task have returned, the parallel builds its payload
  from the branch results (H3 flat union — the branches' outputs are folded
  into one payload; ``output_as`` collision/namespacing merging is LEG-042),
  decrements ``level`` (−1) and resumes its own level through the uniform
  Schema 2 advance — with the ``end_of_level_queue`` its creator supplied.

Nothing waits and nothing is locked (rule 8): branches run as soon as their
deposit lands on their queue; the join is bookkeeping, not polling-blocking.
Failures (an empty parallel) are never silent (rule 9).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from legio.agents.base import AgentBase
from legio.flow import ExecutionRequestMessage, MessageType, build_payload

logger = logging.getLogger(__name__)

# Each parallel class keeps its in-flight join continuation here, keyed by the
# TASK id (constant across the flow). A task id is thus an ordinary dict key —
# multiple concurrent tasks simply occupy several keys.
_STATE_SCOPE = "state:parallel"


class ParallelAgent(AgentBase):
    """A composite that fans out branches and joins them on all-complete."""

    def __init__(
        self,
        *,
        agent_id: str,
        db: Any,
        branches: Sequence[str],
    ) -> None:
        super().__init__(agent_id=agent_id, db=db)
        self._branches: list[str] = list(branches)
        self._state = db.dict(f"{_STATE_SCOPE}:{agent_id}")

    async def _handle(self, request: ExecutionRequestMessage) -> dict[str, Any] | None:
        """Dispatch by message type: a request fans out, a result fans in."""
        if request.message_type is MessageType.EXECUTION_RESULT:
            await self._fan_in(request)
            return None
        await self._fan_out(request)
        return None

    async def _fan_out(self, request: ExecutionRequestMessage) -> None:
        """Deposit one request per branch; record the continuation (idempotent)."""
        if not self._branches:
            raise ValueError(f"parallel agent {self._agent_id!r} has no branches")

        existing = await self._state.fetch(request.task_id)
        if existing is not None:
            logger.debug(
                "parallel already fanned out agent=%s task=%s",
                self._agent_id,
                request.task_id,
            )
            return

        slots: dict[str, dict[str, Any]] = {}
        for branch_class in self._branches:
            child = ExecutionRequestMessage(
                level_route=(branch_class,),
                current_index=0,
                end_of_level_queue=self._agent_id,  # gathering queue (collapsed)
                level=request.level + 1,
                launcher_class=request.launcher_class,
                task_id=request.task_id,
                payload=dict(request.payload),
            )
            logger.info(
                "parallel fan-out agent=%s task=%s to=%s level=%s",
                self._agent_id,
                request.task_id,
                branch_class,
                child.level,
            )
            await self._deliver(branch_class, child.model_dump(mode="json"))
            slots[branch_class] = {"result": None}

        record = {
            "continuation": {
                "level_route": list(request.level_route),
                "current_index": request.current_index,
                "end_of_level_queue": request.end_of_level_queue,
                "level": request.level,
                "launcher_class": request.launcher_class,
                "task_id": request.task_id,
                "payload": dict(request.payload),
            },
            "slots": slots,
        }
        await self._state.set(request.task_id, record)

    async def _fan_in(self, request: ExecutionRequestMessage) -> None:
        """Record one returned branch; when all are in, resume the level.

        The join key is the task id — the result's constant ``task_id`` — so the
        continuation is fetched directly (O(1)); the branch slot is named by the
        result's ``level_route[0]``. Nothing is looked up by scanning.
        """
        record = await self._state.fetch(request.task_id)
        if record is None:
            raise ValueError(
                f"parallel {self._agent_id!r}: no fan-out for task={request.task_id}"
            )

        branch = request.level_route[0] if request.level_route else ""
        slot = record["slots"].get(branch)
        if slot is None:
            raise ValueError(
                f"parallel {self._agent_id!r}: unknown branch={branch!r} for task={request.task_id}"
            )
        slot["result"] = dict(request.payload)

        if any(s["result"] is None for s in record["slots"].values()):
            logger.debug(
                "parallel partial agent=%s task=%s",
                self._agent_id,
                request.task_id,
            )
            await self._state.set(request.task_id, record)
            return

        logger.info("parallel joined agent=%s task=%s", self._agent_id, request.task_id)
        result_payload = self._build_branch_payload(record)
        await self._state.delete(request.task_id)
        await self._resume_level(record, result_payload)

    def _build_branch_payload(self, record: dict[str, Any]) -> dict[str, Any]:
        """Build the parallel's payload from the incoming payload + each branch
        result, H3 flat union (output_as namespacing is LEG-042)."""
        continuation = record["continuation"]
        payload = dict(continuation["payload"])
        for slot in record["slots"].values():
            payload = build_payload(payload, slot["result"])
        return payload

    async def _resume_level(
        self, record: dict[str, Any], result_payload: dict[str, Any]
    ) -> None:
        """Resume the parallel's own level via the uniform Schema 2 advance."""
        cont = record["continuation"]
        resume = ExecutionRequestMessage(
            level_route=tuple(cont["level_route"]),
            current_index=cont["current_index"],
            end_of_level_queue=cont["end_of_level_queue"],
            level=cont["level"],
            launcher_class=cont["launcher_class"],
            task_id=cont["task_id"],
            payload=result_payload,
        )
        await self._route_outcome(resume, result_payload)


__all__ = ["ParallelAgent"]
