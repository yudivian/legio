"""`legio.errors` — the typed error taxonomy (LEG-016).

All legio errors derive from ``LegioError`` and carry a stable ``code`` derived
from the message. Each error is either recoverable (retriable) or not; this
drives retry/DLQ policy (R-6). Failures are never silent (AGENTS.md rule 9).
"""

from __future__ import annotations

import re


def code(message: str) -> str:
    """Derive a stable, human-readable error code from a message."""
    slug = re.sub(r"[^a-z0-9]+", "_", message.lower()).strip("_")
    if not slug:
        slug = f"err_{abs(hash(message))}"
    return slug


class LegioError(Exception):
    """Base class for every legio error."""

    _recoverable = True
    _retriable = True

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    @property
    def code(self) -> str:
        return code(self.message)


class RecoverableError(LegioError):
    """A transient failure that may succeed when retried."""

    _recoverable = True
    _retriable = True


class UnrecoverableError(LegioError):
    """A fatal failure that must not be retried."""

    _recoverable = False
    _retriable = False


class InvalidNameError(RecoverableError):
    """An identifier violates its naming contract."""


def recoverable(error: LegioError) -> bool:
    """Whether the error type is recoverable (safe to retry)."""
    return isinstance(error, LegioError) and error._recoverable


def retriable(error: LegioError) -> bool:
    """Whether the error type is retriable (lease/NN retry eligible)."""
    return isinstance(error, LegioError) and error._retriable


__all__ = [
    "InvalidNameError",
    "LegioError",
    "RecoverableError",
    "UnrecoverableError",
    "code",
    "recoverable",
    "retriable",
]
