"""`legio.flow.merge` — carried-state accumulation (AGENT_LIFECYCLE §12.1/H3).

A step's output is merged flat into the state the outgoing message already
carries: the request/result always carries the accumulated state of the task,
never only the last step's output. ``merge_carried`` is the single flat-union
rule; ``namespace`` (the pattern's ``output_as``) namespaces the whole output
under one key so collisions cannot occur.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

__all__ = ["merge_carried"]


def merge_carried(
    incoming: Mapping[str, Any] | None,
    output: Mapping[str, Any],
    *,
    namespace: str | None = None,
) -> dict[str, Any]:
    """Merge ``output`` into ``incoming``; return the carried state.

    ``incoming`` is the carried state so far (the request's ``payload["input"]``
    when message-shaped); ``output`` is the step's result. With ``namespace``
    the output is stored whole under that key; otherwise keys are flat-union'd
    and the step's keys win on collision (H3). Never mutates ``incoming``.
    """
    base = dict(incoming or {})
    if namespace is not None:
        base[namespace] = dict(output)
        return base
    base.update(dict(output))
    return base
