"""`legio.flow.payload` — payload building (AGENT_LIFECYCLE §12.1).

An agent receives the incoming ``payload``, performs its processing, and builds
the **new** ``payload`` that travels in the outgoing message (exactly one
container, Schema 2). ``build_payload`` is that single rule: it never mutates
the incoming payload; the produced payload is the union of the incoming
keys plus the step's output keys (the step's keys win on collision, H3).
``namespace`` (the pattern's ``output_as``) stores the whole output under one
key so collisions cannot occur.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

__all__ = ["build_payload"]


def build_payload(
    payload: Mapping[str, Any] | None,
    output: Mapping[str, Any],
    *,
    namespace: str | None = None,
) -> dict[str, Any]:
    """Build the new ``payload`` from the incoming one and the step's output.

    ``payload`` is the incoming state (the request's single container of Schema
    2); ``output`` is the step's produced result. With ``namespace`` the output
    is stored whole under that key; otherwise the keys are unioned and the
    step's keys win on collision (H3). Never mutates ``payload``; the result is
    a new dict.
    """
    base = dict(payload or {})
    if namespace is not None:
        base[namespace] = dict(output)
        return base
    base.update(dict(output))
    return base