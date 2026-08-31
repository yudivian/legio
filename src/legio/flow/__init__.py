"""`legio.flow` — the FlowToken and the two queue message types (LEG-011)."""

from __future__ import annotations

from .merge import merge_carried
from .messages import (
    SCHEMA_VERSION,
    ExecutionRequestMessage,
    ExecutionResultMessage,
    MessageType,
)
from .token import FlowToken

__all__ = [
    "SCHEMA_VERSION",
    "ExecutionRequestMessage",
    "ExecutionResultMessage",
    "FlowToken",
    "MessageType",
    "merge_carried",
]
