"""`legio.flow.messages` — schema version, immutable base and envelope types.

Only two message types exist: ``ExecutionRequestMessage`` (client → root agent)
and ``ExecutionResultMessage`` (agent → parent or client). ``MessageType``
discriminates the two. Domain-free: payload/output are opaque dicts.
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
    route_pattern_names: tuple[str, ...] = Field(default_factory=tuple)
    current_index: int = 0
    ultimate_return_agent_id: str = ""
    origin_node_id: str = ""
    task_id: str = ""


class ExecutionRequestMessage(ImmutableMessage):
    """A request to execute a route, issued by the client."""

    message_type: MessageType = MessageType.EXECUTION_REQUEST
    payload: dict[str, Any] = Field(default_factory=dict)


class ExecutionResultMessage(ImmutableMessage):
    """The output of a completed step, deposited to parent/client."""

    message_type: MessageType = MessageType.EXECUTION_RESULT
    output: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "SCHEMA_VERSION",
    "ExecutionRequestMessage",
    "ExecutionResultMessage",
    "ImmutableMessage",
    "MessageType",
]
