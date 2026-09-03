"""`legio.patterns.sequences` — starting-route derivation (R-3/R-4, LEG-032/043).

Derives the starting route the submit delivers to. The submit is a dumb
delivery point: it only hands the task to the **starting agent** (the entry) and
never resolves any DAG. That agent — atomic, sequence or parallel — concretizes
its own sub-DAG at runtime (ARCHITECTURE §3/§6):
- an atomic (tool/linguistic) starts on its own class;
- a parallel root starts on its own class (the ParallelAgent concretizes the
  fan-out);
- a ``main`` sequence is still flattened to its stage names (R-3 behaviour).

Nested composites inside a sequence (R-4+) raise a structured error rather than
guessing.
"""

from __future__ import annotations

from legio.errors import UnrecoverableError
from legio.patterns.schema1 import AgentKind, AgentSpec, AgentType


def _agent_name(spec: AgentSpec) -> str:
    return spec.name


def _collect_sequence_route(spec: AgentSpec) -> tuple[str, ...]:
    """Collect ordered stage names from a sequence composite."""
    if spec.kind is not AgentKind.SEQUENCE:
        raise UnrecoverableError(f"spec {spec.name!r} is not a sequence composite")
    if not spec.sequence:
        raise UnrecoverableError(f"sequence {spec.name!r} has no stages")
    return tuple(_agent_name(child) for child in spec.sequence)


def starting_route(spec: AgentSpec) -> tuple[str, ...]:
    """Return the route the submit delivers to for a starting agent.

    - A single atomic pattern (tool/linguistic) yields ``(spec.name,)``.
    - A ``main`` sequence is flattened to its stage names in order (R-3).
    - A parallel root yields ``(spec.name,)`` — the submit delivers to the
      parallel's own class and the ParallelAgent concretizes the fan-out.
    - Anything else (nested composite inside a sequence) raises.
    """
    if spec.type is AgentType.ATOMIC:
        # Atomic agent (tool/linguistic) is its own route
        return (spec.name,)

    if spec.kind is AgentKind.SEQUENCE:
        return _collect_sequence_route(spec)

    if spec.kind is AgentKind.PARALLEL:
        # A parallel root is itself the starting agent: the submit delivers to
        # its own class queue and the ParallelAgent concretizes the fan-out.
        return (spec.name,)

    raise UnrecoverableError(
        f"pattern {spec.name!r} is a composite without a linear atomic sequence"
    )


__all__ = ["starting_route"]