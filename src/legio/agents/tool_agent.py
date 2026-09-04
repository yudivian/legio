"""`legio.agents.tool_agent` — the ToolAgent runner (LEG-022, over LEG-023).

The ToolAgent executes a `kind: tool` agent step. It receives the incoming
payload from the request's single `payload` container (Schema 2), resolves the
terse `parameters` (`{arg: dotted.path | literal}`) against it, loads the bound
`tool: <name>` from `available_tools` (Schema 3), invokes it with the resolved
kwargs, validates the call against the tool's signature at execution time,
and builds the new payload with `build_payload` (AGENT_LIFECYCLE §12.1: the
state travels in the messages — nothing staged out-of-message). The base routes
by position.

Schema/signature failures on either edge are never silent: an error result is
deposited instead (see AGENTS.md rule 9).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from legio.agents.base import AgentBase
from legio.flow import ExecutionRequestMessage, build_payload
from legio.tools import AvailableToolsRegistry, resolve_parameters, validate_callable_signature

logger = logging.getLogger(__name__)


class ToolAgent(AgentBase):
    """Runs a single tool step of a route against a Schema 3 tool."""

    def __init__(
        self,
        *,
        agent_id: str,
        db: Any,
        available_tools: AvailableToolsRegistry,
        tool_name: str,
        parameters: Mapping[str, Any],
        input_as: str = "",
        output_as: str = "",
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            db=db,
            output_as=output_as,
        )
        self._available_tools = available_tools
        self._tool_name = tool_name
        self._parameters = dict(parameters)
        self._input_as = input_as

    async def _handle(self, request: ExecutionRequestMessage) -> dict[str, Any]:
        error: str | None = None
        try:
            # Resolve terse parameters against the incoming payload (explicit
            # `{input_as}.{key}` dotted paths, §4.12 — no implicit resolution).
            resolved_kwargs = resolve_parameters(self._parameters, request.payload)
            # Load the tool from available_tools (dotted path)
            tool = self._available_tools.load_tool(self._tool_name)
            # Validate against tool's signature at execution time
            validate_callable_signature(tool, resolved_kwargs)
            # Invoke
            raw_output = tool(**resolved_kwargs)
            logger.debug(
                "tool executed ok agent=%s task=%s tool=%s",
                self._agent_id,
                request.task_id,
                self._tool_name,
            )
            # Build the new payload (construction under output_as; re-keying at handoff)
            return build_payload(raw_output, output_as=self._output_as)
        except Exception as exc:  # noqa: BLE001 - surfaced, never swallowed
            logger.warning(
                "tool execution failure agent=%s task=%s tool=%s error=%s",
                self._agent_id,
                request.task_id,
                self._tool_name,
                f"{type(exc).__name__}: {exc}",
            )
            error = f"{type(exc).__name__}: {exc}"

        if error is not None:
            return {"error": error}

        # Should not reach here
        return {"error": "tool produced no output"}


__all__ = ["ToolAgent"]
