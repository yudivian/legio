"""`legio.worker` — a single replica running one agent (LEG-025).

A ``Worker`` owns one concrete agent (an ``AgentBase``) and repeatedly polls its
queue via ``AgentBase.run()`` — the decoupled loop from LEG-023. It never knows
the task or the client; it only advances whatever polled work appears on that
agent's queue, and route/finish is decided by the DAG in each token.

``process_once`` drains the agent's queue once (polling-only, AGENTS.md rule 8:
no sleeping; a replica is autonomous and polls its own queue itself, with
scheduling expressed as a field, ``next_run_at``). ``serve`` is the foreground
loop consumed by ``legio worker`` in deployment.
"""

from __future__ import annotations

import logging

from legio.agents.base import AgentBase

logger = logging.getLogger(__name__)


class Worker:
    """A replica that runs a single agent against its queue."""

    def __init__(self, agent: AgentBase) -> None:
        self._agent = agent

    @property
    def agent_id(self) -> str:
        return self._agent.agent_id

    @property
    def agent(self) -> AgentBase:
        return self._agent

    async def process_once(self) -> int:
        """Poll and process every pending message on the agent's queue once.

        Returns the number of messages processed. At-least-once semantics are
        provided by the underlying lease/retry_guard (LEG-023); this method
        never blocks or sleeps. A live replica is autonomous: it polls its own
        queue itself and is not scheduled by any central supervisor —
        there is no busy loop (AGENTS.md rule 8, LEG-023).
        """
        processed = await self._agent.run()
        if processed:
            logger.info("worker process agent=%s processed=%s", self._agent.agent_id, processed)
        else:
            logger.debug("worker idle agent=%s", self._agent.agent_id)
        return processed


__all__ = ["Worker"]
