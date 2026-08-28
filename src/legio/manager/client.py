"""`legio.manager.client` — the client pseudo-agent (LEG-014).

Represents the ``client:{task_id}`` join point: it owns the queue where the
root result lands and can be terminated cleanly (marking its task
``CLIENT_TERMINATED``) or drained. It only coordinates the manager substrate —
it never executes domain logic.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from legio.manager import TaskState, client_queue, set_task_state

logger = logging.getLogger(__name__)


class ClientPseudoAgent:
    """The client-side pseudo-agent for a single task."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        self.agent_id = f"client:{task_id}"

    def handle_termination_request(self) -> None:
        """Mark the owning task as cleanly client-terminated."""
        set_task_state(self.task_id, TaskState.CLIENT_TERMINATED)
        logger.info("client pseudo-agent terminated task=%s", self.task_id)

    async def drain(self) -> list[Mapping[str, Any]]:
        """Remove and return every message left on the client queue."""
        queue = client_queue(self.task_id)
        items: list[Mapping[str, Any]] = []
        while True:
            item = await queue.pop()
            if item is None:
                return items
            items.append(item)


__all__ = ["ClientPseudoAgent"]
