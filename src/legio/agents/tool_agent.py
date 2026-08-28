"""`legio.agents.tool_agent` — the ToolAgent runner (LEG-022, over LEG-023).

The ToolAgent executes a tool step of a route (LEG-010 H1: inline tool steps
are auto-named agents with their own queue and join). It is an ``AgentBase``
(LEG-023): the base provides the uniform lease/dispatch/hook/ack ``run()``
loop, while ``_handle`` implements the tool-specific job — read the staged
``input`` frame key, validate it against the tool's ``input_schema``, invoke
the registered tool as a callable, validate the result against the tool's
``output_schema``, stage the ``out`` frame and deposit the result to the
parent (or the client for the last step).

Schema failures on either edge are never silent: an error-carrying result is
deposited instead (see AGENTS.md rule 9).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import cast

from legio.agents.base import AgentBase
from legio.flow import ExecutionRequestMessage
from legio.primitives import Board, Queue
from legio.tools import Tool, ToolRegistry

logger = logging.getLogger(__name__)


class ToolAgent(AgentBase):
    """Runs a single tool step of a route against a registered tool."""

    def __init__(
        self,
        *,
        agent_id: str,
        registry: ToolRegistry,
        tool_type: str,
        queue: Queue,
        board: Board,
        queues: Mapping[str, Queue],
        frames_scope: str = "frames",
        lease_ttl: float = 60.0,
        results_board: Board | None = None,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            queue=queue,
            board=board,
            queues=queues,
            frames_scope=frames_scope,
            lease_ttl=lease_ttl,
            results_board=results_board,
        )
        self._registry = registry
        self._tool_type = tool_type
        self._tool: Tool = registry.resolve(tool_type)
        self._input_schema, self._output_schema = registry.schemas(tool_type)

    async def _handle(self, request: ExecutionRequestMessage) -> None:
        frame = await self._frame(request)

        error: str | None = None
        validated_output = None
        try:
            raw_input = frame.get("input", request.payload.get("input", {}))
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
            await self._finish(request, {"error": error or "tool produced no output"})
            return

        output = validated_output.model_dump()
        await self._store_out(request, "out", output)
        is_last = request.current_index >= len(request.route_pattern_names) - 1
        if is_last:
            await self._finish(request, output)
        else:
            await self._advance(request, output=output)


__all__ = ["ToolAgent"]
