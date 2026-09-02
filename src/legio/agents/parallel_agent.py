"""`legio.agents.parallel_agent` — the ParallelAgent runner (LEG-041, R-4).

A parallel composite fans out its branches concurrently and joins their results
(AGENT_LIFECYCLE §12.3/§12.4, ARCHITECTURE §7). It collapses the model's two
queues (inbox + gathering) into one physical queue by message-type dispatch
(the contract explicitly allows this): branch returns land on the parallel's
own queue and ``_handle`` dispatches on ``message_type``.

- **Fan-out** (``execution_request``): each branch is deposited to the child
  class's inbox with ``level_route = (branch_class,)``, ``current_index = 0``,
  ``level + 1`` and ``end_of_level_queue`` = this parallel's own queue (its
  gathering queue, collapsed). A **distinct child task id (uuid) is minted per
  branch** — the child id IS the slot identity (LEG-052). The parallel does
  **not** advance; it records its continuation and join state in the
  ``state:parallel:<class>`` registry (keyed per parent task).
- **Fan-in** (``execution_result``): the child task id identifies the slot.
  When all branches of a parent task have returned, the parallel builds its
  payload from the branch results (H3 flat union — the branches' outputs are
  folded into one payload; ``output_as`` collision/namespacing merging is
  LEG-042), decrements ``level`` (−1) and resumes its own level through the
  uniform Schema 2 advance — with the ``end_of_level_queue`` its creator
  supplied.

Nothing waits and nothing is locked (rule 8): branches run as soon as their
deposit lands on their queue; the join is bookkeeping, not polling-blocking.
Failures (an empty parallel) are never silent (rule 9).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from typing import Any

from legio.agents.base import AgentBase
from legio.flow import ExecutionRequestMessage, MessageType, build_payload

logger = logging.getLogger(__name__)

# Each parallel class keeps its fan-in join state here, keyed by parent task id.
# The child id is the slot identity (LEG-052): child id → (parent task, slot).
_STATE_SCOPE = "state:parallel"


class ParallelAgent(AgentBase):
    """A composite that fans out branches and joins them on all-complete."""

    def __init__(
        self,
        *,
        agent_id: str,
        db: Any,
        branches: Sequence[str],
        lease_ttl: float = 60.0,
    ) -> None:
        super().__init__(agent_id=agent_id, db=db, lease_ttl=lease_ttl)
        self._branches: list[str] = list(branches)
        self._state = db.dict(f"{_STATE_SCOPE}:{agent_id}")

    async def _handle(self, request: ExecutionRequestMessage) -> dict[str, Any] | None:
        """Dispatch by message type: a request fans out, a result fans in."""
        if request.message_type is MessageType.EXECUTION_RESULT:
            return await self._fan_in(request)
        return await self._fan_out(request)

    @staticmethod
    def _mint_child_task_id() -> str:
        return f"par:{uuid.uuid4()}"

    async def _fan_out(self, request: ExecutionRequestMessage) -> None:
        """Deposit one request per branch; record the join state (idempotent)."""
        if not self._branches:
            raise ValueError(f"parallel agent {self._agent_id!r} has no branches")

        existing = await self._state.fetch(request.task_id)
        if existing is not None:
            logger.debug("parallel already fanned out agent=%s task=%s", self._agent_id, request.task_id)
            return

        slots: dict[str, dict[str, Any]] = {}
        for branch_class in self._branches:
            child_id = self._mint_child_task_id()
            child = ExecutionRequestMessage(
                level_route=(branch_class,),
                current_index=0,
                end_of_level_queue=self._agent_id,  # gathering queue (collapsed)
                level=request.level + 1,
                launcher_class=request.launcher_class,
                task_id=child_id,
                payload=dict(request.payload),
            )
            logger.info(
                "parallel fan-out agent=%s parent=%s child=%s to=%s level=%s",
                self._agent_id,
                request.task_id,
                child_id,
                branch_class,
                child.level,
            )
            await self._deliver(branch_class, child.model_dump(mode="json"))
            slots[child_id] = {"result": None}

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
        return

    async def _fan_in(self, request: ExecutionRequestMessage) -> None:
        """Record one returned branch; when all are in, resume the level."""
        parent_record: dict[str, Any] | None = None
        parent_task: str | None = None
        async for key, value in self._state.items():
            if request.task_id in value.get("slots", {}):
                parent_task = key
                parent_record = value
                break
        if parent_record is None:
            raise ValueError(
                f"parallel {self._agent_id!r}: unknown branch result task={request.task_id}"
            )

        slot = parent_record["slots"][request.task_id]
        if slot["result"] is None:
            slot["result"] = dict(request.payload)

        remaining = [c for c, s in parent_record["slots"].items() if s["result"] is None]
        if remaining:
            logger.debug(
                "parallel partial agent=%s parent=%s pending=%s",
                self._agent_id,
                parent_task,
                ",".join(remaining),
            )
            await self._state.set(parent_task, parent_record)
            return

        logger.info("parallel joined agent=%s parent=%s", self._agent_id, parent_task)
        result_payload = self._build_branch_payload(parent_record)
        await self._state.delete(parent_task)
        await self._resume_level(parent_record, result_payload)
        return

    def _build_branch_payload(self, parent_record: dict[str, Any]) -> dict[str, Any]:
        """Build the parallel's payload from the incoming payload + each branch
        result, H3 flat union (output_as namespacing is LEG-042)."""
        continuation = parent_record["continuation"]
        payload = dict(continuation["payload"])
        for slot in parent_record["slots"].values():
            payload = build_payload(payload, slot["result"])
        return payload

    async def _resume_level(
        self, parent_record: dict[str, Any], result_payload: dict[str, Any]
    ) -> None:
        """Resume the parallel's own level via the uniform Schema 2 advance."""
        cont = parent_record["continuation"]
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
