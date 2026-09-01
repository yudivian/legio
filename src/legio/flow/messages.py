"""`legio.flow.messages` — schema version, immutable base and envelope types.

Only two message types exist: ``ExecutionRequestMessage`` (client → root agent)
and ``ExecutionResultMessage`` (agent → parent or final-result queue).
``MessageType`` discriminates the two. Domain-free: ``payload`` is the single
carried-data container (Schema 2) — the same container carries the accepted
request facts and the accumulated output; there is no separate ``output`` field
and no ``input`` nesting.

Token fields (Schema 2, AGENT_LIFECYCLE §4.11): ``level_route`` (the classes of
this level), ``current_index`` (0-based position), ``end_of_level_queue`` (the
queue that closes this level — the submit's final-result queue at level 1, a
parallel's gathering queue for branches), ``level`` (branch depth, starts at 1),
``launcher_class`` (informational) and ``task_id``. There is no ``next_queue`` /
``ultimate_return_agent_id`` / ``origin_node_id``: routing is by
position + ``level`` and the end of a level lands on ``end_of_level_queue``.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = 1000


class MessageType(str, Enum):
    """The only two message kinds exchanged over queues."""

    EXECUTION_REQUEST = "execution_request"
    EXECUTION_RESULT = "execution_result"


class ImmutableMessage(BaseModel):
    """Shared immutable envelope base for both messages and the token."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
    )

    @field_validator("schema_version")
    @classmethod
    def _only_exact_schema_version(cls, value: int) -> int:
        if value != SCHEMA_VERSION:
            raise ValueError("incompatible schema_version")
        return value

    schema_version: int = Field(default=SCHEMA_VERSION, frozen=True)
    level_route: tuple[str, ...] = Field(default_factory=tuple)
    current_index: int = 0
    end_of_level_queue: str = ""
    level: int = 1
    launcher_class: str = ""
    task_id: str = ""


class ExecutionRequestMessage(ImmutableMessage):
    """A request to execute a level route, issued by the client."""

    message_type: MessageType = MessageType.EXECUTION_REQUEST
    payload: dict[str, Any] = Field(default_factory=dict)


class ExecutionResultMessage(ImmutableMessage):
    """The accumulated output of a completed level, deposited to the closer."""

    message_type: MessageType = MessageType.EXECUTION_RESULT
    payload: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "SCHEMA_VERSION",
    "ExecutionRequestMessage",
    "ExecutionResultMessage",
    "ImmutableMessage",
    "MessageType",
]
