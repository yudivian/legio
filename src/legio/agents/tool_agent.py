"""`legio.agents.tool_agent` — the ToolAgent runner (LEG-022, over LEG-023).

The ToolAgent executes a tool step of a route. It is an ``AgentBase``
(LEG-023): the base provides the uniform lease/dispatch/hook/ack ``run()``
loop, while ``_handle`` implements the tool-specific job — take the carried
state from the request's single ``payload`` container (Schema 2), validate it
against the tool's ``input_schema``, invoke the registered tool as a callable,
validate the result against the tool's ``output_schema``, and return the merged
carried state (AGENT_LIFECYCLE §12.1: the step's state rides in the messages —
there is no out-of-message staging board). The base routes by position.

Schema failures on either edge are never silent: an error-carrying result is
deposited instead (see AGENTS.md rule 9).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, cast

from legio.agents.base import AgentBase
from legio.flow import ExecutionRequestMessage, merge_carried
from legio.tools import Tool, ToolRegistry

logger = logging.getLogger(__name__)


class ToolAgent(AgentBase):
    """Runs a single tool step of a route against a registered tool."""

    def __init__(
        self,
        *,
        agent_id: str,
        db: Any,
        registry: ToolRegistry,
        tool_type: str,
        lease_ttl: float = 60.0,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            db=db,
            lease_ttl=lease_ttl,
        )
        self._registry = registry
        self._tool_type = tool_type
        self._tool: Tool = registry.resolve(tool_type)
        self._input_schema, self._output_schema = registry.schemas(tool_type)

    async def _handle(self, request: ExecutionRequestMessage) -> dict[str, Any]:
        error: str | None = None
        validated_output = None
        try:
            raw_input = request.payload
            validated_input = self._input_schema.model_validate(raw_input)
            logger.debug("tool input ok agent=%s task=%s", self._agent_id, request.task_id)
            callable_tool = cast(Callable[..., object], self._tool)
            raw_output = callable_tool(**validated_input.model_dump())
            validated_output = self._output_schema.model_validate(raw_output)
        except Exception as exc:  # noqa: BLE001 - surfaced, never swallowed
            logger.warning(
                "tool schema failure agent=%s task=%s error=%s",
                self._agent_id,
                request.task_id,
                f"{type(exc).__name__}: {exc}",
            )
            error = f"{type(exc).__name__}: {exc}"

        if error is not None or validated_output is None:
            return {"error": error or "tool produced no output"}

        output = validated_output.model_dump()
        logger.debug(
            "tool output ok agent=%s task=%s",
            self._agent_id,
            request.task_id,
        )
        return merge_carried(request.payload, output)


__all__ = ["ToolAgent"]
