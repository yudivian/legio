"""`legio.flow.token` — the immutable FlowToken (LEG-011).

The FlowToken is the immutable payload travelling with a route. Finality is
*derived from position* (``is_final(total_steps)`` compares ``current_index``
against the last step), never stored. A root token always returns to the client:
``ultimate_return_agent_id`` is forced to ``client:{task_id}``.
"""

from __future__ import annotations

from pydantic import model_validator

from .messages import ImmutableMessage


class FlowToken(ImmutableMessage):
    """Immutable route-travelling token; finality derived from position."""

    root: bool = False

    @model_validator(mode="after")
    def _root_returns_to_client(self) -> FlowToken:
        if self.root:
            object.__setattr__(self, "ultimate_return_agent_id", f"client:{self.task_id}")
        return self

    def is_final(self, total_steps: int) -> bool:
        """Whether this token points at the last step of ``total_steps``."""
        return self.current_index == total_steps - 1


__all__ = ["FlowToken"]
