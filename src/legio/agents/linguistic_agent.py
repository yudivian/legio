"""`legio.agents.linguistic_agent` — the linguistic agent runner (LEG-030, over LEG-023).

Runs a linguistic step of a route: resolves its prompt template against the
message-carried payload (LEG-010 H2 dotted paths + system vars), asks an
injected lingo client (an ``LLM``/``MockLLM`` fake) for a structured pydantic
record validated against the pattern's compiled ``output_schema``, and deposits
a result to the parent or the client (finality by position, LEG-011), or
advances to the next step of the route. The step's state rides in the messages
(AGENT_LIFECYCLE §12.1): there is no out-of-message staging board.

The call is a single ``create(model, [system prompt])`` round-trip (LEG-030 v1
call contract). Failures from lingo are never silent (AGENTS.md rule 9): a
raised step error is routed by the base to an error-carrying result.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from lingo.llm import Message
from pydantic import BaseModel

from legio.agents.base import AgentBase
from legio.flow import ExecutionRequestMessage, merge_carried
from legio.patterns.template import resolve_template

logger = logging.getLogger(__name__)


class LinguisticAgent(AgentBase):
    """Runs a single linguistic step against a lingo client and the carried state."""

    def __init__(
        self,
        *,
        agent_id: str,
        db: Any,
        lingo_client: Any,
        prompt_template: str,
        output_model: type[BaseModel],
        lease_ttl: float = 60.0,
        system_vars: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            db=db,
            lease_ttl=lease_ttl,
        )
        self._lingo = lingo_client
        self._prompt = prompt_template
        self._output_model = output_model
        merged_vars = dict(system_vars or {})
        merged_vars.setdefault("current_date", datetime.now(UTC).date().isoformat())
        self._system_vars = merged_vars

    async def _handle(self, request: ExecutionRequestMessage) -> None:
        scoped: dict[str, Any] = dict(request.payload)
        logger.debug(
            "linguistic input agent=%s task=%s keys=%s",
            self._agent_id,
            request.task_id,
            ",".join(scoped),
        )
        prompt = resolve_template(self._prompt, scoped, self._system_vars)
        logger.info(
            "linguistic call agent=%s task=%s",
            self._agent_id,
            request.task_id,
        )
        messages = [Message.system(prompt)]
        result = await self._lingo.create(self._output_model, messages)
        output = result.model_dump()
        carried = merge_carried(request.payload.get("input", {}), output)
        logger.info(
            "linguistic result agent=%s task=%s",
            self._agent_id,
            request.task_id,
        )
        is_last = request.current_index >= len(request.route_pattern_names) - 1
        if is_last:
            await self._finish(request, carried)
        else:
            await self._advance(request, output=carried)


__all__ = ["LinguisticAgent"]
