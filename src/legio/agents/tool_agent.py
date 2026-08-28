"""`legio.agents.tool_agent` — the ToolAgent runner (LEG-022).

The ToolAgent executes a tool step of a route (LEG-010 H1: inline tool steps
are auto-named agents with their own queue and join). It leases a work item
from its queue, reads the staged ``input`` frame key from the blackboard,
validates it against the tool's ``input_schema``, invokes the registered tool
as a callable, validates the result against the tool's ``output_schema``,
stages the ``out`` frame and deposits an ``ExecutionResultMessage`` back to the
parent (or the client for the last step).

Schema failures on either edge are never silent: an error-carrying result is
deposited instead (see AGENTS.md rule 9).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import cast

from legio.flow import ExecutionRequestMessage, ExecutionResultMessage
from legio.primitives import Board, Queue
from legio.tools import Tool, ToolRegistry


class ToolAgent:
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
    ) -> None:
        self._agent_id = agent_id
        self._registry = registry
        self._tool_type = tool_type
        self._queue = queue
        self._board = board
        self._queues = queues
        self._frames_scope = frames_scope
        self._lease_ttl = lease_ttl
        self._tool: Tool = registry.resolve(tool_type)
        self._input_schema, self._output_schema = registry.schemas(tool_type)

    async def process_next(self, *, lease_ttl: float | None = None) -> bool:
        """Process at most one due work item; return whether one was handled.

        Returns ``False`` when the queue has no due item (idle), ``True`` after
        handling (or failing) one item.
        """
        ttl = lease_ttl or self._lease_ttl
        handle = await self._queue.lease(ttl)
        if handle is None:
            return False

        try:
            request = ExecutionRequestMessage.model_validate(dict(handle.item))
            await self._execute(request)
        finally:
            await self._queue.ack(handle)
        return True

    async def _execute(self, request: ExecutionRequestMessage) -> None:
        frame_key = f"{self._agent_id}:{request.task_id}"
        frame = await self._board.get(frame_key, default={}) or {}

        error: str | None = None
        try:
            raw_input = frame.get("input", request.payload.get("input", {}))
            validated_input = self._input_schema.model_validate(raw_input)
            callable_tool = cast(Callable[..., object], self._tool)
            raw_output = callable_tool(**validated_input.model_dump())
            validated_output = self._output_schema.model_validate(raw_output)
        except Exception as exc:  # noqa: BLE001 - surfaced, never swallowed
            error = f"{type(exc).__name__}: {exc}"
            validated_output = None

        if error is not None or validated_output is None:
            await self._deposit_error(request, error or "tool produced no output")
            return

        frame = dict(frame)
        frame["out"] = validated_output.model_dump()
        await self._board.update(frame_key, frame)
        await self._deposit_result(request, validated_output.model_dump())

    async def _deposit_result(self, request: ExecutionRequestMessage, output: dict) -> None:
        result = ExecutionResultMessage(
            route_pattern_names=request.route_pattern_names,
            current_index=request.current_index,
            ultimate_return_agent_id=request.ultimate_return_agent_id,
            origin_node_id=request.origin_node_id,
            task_id=request.task_id,
            output=output,
        )
        await self._push_result(result)

    async def _deposit_error(self, request: ExecutionRequestMessage, error: str) -> None:
        result = ExecutionResultMessage(
            route_pattern_names=request.route_pattern_names,
            current_index=request.current_index,
            ultimate_return_agent_id=request.ultimate_return_agent_id,
            origin_node_id=request.origin_node_id,
            task_id=request.task_id,
            output={"error": error},
        )
        await self._push_result(result)

    async def _push_result(self, result: ExecutionResultMessage) -> None:
        target = self._queues.get(result.ultimate_return_agent_id)
        if target is None:
            raise KeyError(
                f"no queue registered for return agent {result.ultimate_return_agent_id!r}"
            )
        await target.push(result.model_dump(mode="json"))


__all__ = ["ToolAgent"]
