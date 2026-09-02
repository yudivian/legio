"""`legio.agents.sequence_agent` — the SequenceAgent runner (LEG-040, R-4).

A sequence composite is a **forward-only** chain (AGENT_LIFECYCLE §12.3): steps
run strictly in order, nothing returns to the sequence itself, and the last
stage deposits into the level closer. When a sequence is reached as a step of
its parent's route (an embedded/capability sequence), this agent re-seeds the
first of its declared stages with a flattened ``level_route`` and
``current_index = 0``, preserving ``level``, ``end_of_level_queue``, ``task_id``,
``launcher_class`` and the incoming ``payload``. From there any stage runs the
uniform Schema 2 advance (``AgentBase._route_outcome``): position within the
sequence, then the level closer (the creator's gathering queue at ``level > 1``,
or the submit's final-result queue at ``level == 1``).

A top-level ``main`` sequence is flattened into its stages by ``starting_route``
(``legio.patterns.sequences``), so the stages ARE the level route and no
``SequenceAgent`` is invoked; this agent exists for the nested-composite case
where the sequence class is a capability step.

An empty sequence is a construction error (rule 9): it is surfaced as a visible
error result, never silent.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from legio.agents.base import AgentBase
from legio.flow import ExecutionRequestMessage

logger = logging.getLogger(__name__)


class SequenceAgent(AgentBase):
    """A forward-only sequence composite over the class inbox (LEG-040)."""

    def __init__(
        self,
        *,
        agent_id: str,
        db: Any,
        sequence_route: Sequence[str],
        lease_ttl: float = 60.0,
    ) -> None:
        super().__init__(agent_id=agent_id, db=db, lease_ttl=lease_ttl)
        self._sequence_route = tuple(sequence_route)

    async def _handle(self, request: ExecutionRequestMessage) -> dict[str, Any] | None:
        """Re-seed the first stage of this sequence; forward-only, no payload."""
        if not self._sequence_route:
            raise ValueError(f"sequence agent {self._agent_id!r} has no stages")
        first_stage = self._sequence_route[0]
        logger.info(
            "sequence forward agent=%s task=%s stage=%s",
            self._agent_id,
            request.task_id,
            first_stage,
        )
        next_request = ExecutionRequestMessage(
            level_route=self._sequence_route,
            current_index=0,
            end_of_level_queue=request.end_of_level_queue,
            level=request.level,
            launcher_class=request.launcher_class,
            task_id=request.task_id,
            payload=request.payload,
        )
        await self._deliver(first_stage, next_request.model_dump(mode="json"))
        return None


__all__ = ["SequenceAgent"]
