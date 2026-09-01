"""`legio.flow` — the FlowToken and the two queue message types (LEG-011)."""

from __future__ import annotations

from .messages import (
    SCHEMA_VERSION,
    ExecutionRequestMessage,
    ExecutionResultMessage,
    MessageType,
)
from .payload import build_payload
from .token import FlowToken

__all__ = [
    "SCHEMA_VERSION",
    "ExecutionRequestMessage",
    "ExecutionResultMessage",
    "FlowToken",
    "MessageType",
    "build_payload",
]
