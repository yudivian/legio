"""`legio.patterns.sequences` — linear starting-sequence DAG derivation (R-3, LEG-032).

Derives the concrete sub-DAG of a **sequence** starting pattern: the ordered list
of stage names the token travels. It feeds the construction of the *starting
agent* of that sequence (its ``starting_dag``), which concretizes the token at
runtime (ARCHITECTURE §3/§6) — it is **not** resolved by the manager at submit.

Only linear atomic chains are in R-3 scope. Parallel fan-out and nested
composites (R-4+) raise a structured error rather than guessing.
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
    """Return the ordered sub-DAG (stage names) for a sequence starting pattern.

    - A single atomic pattern (tool/linguistic) yields ``(spec.name,)``.
    - A ``main``/composite pattern with a linear ``sequence`` of atomic stages
      yields the stage names in order.
    - Anything else (parallel, nested composite inside sequence) is out of R-3
      scope and raises.
    """
    if spec.type is AgentType.ATOMIC:
        # Atomic agent (tool/linguistic) is its own route
        return (spec.name,)

    if spec.kind is AgentKind.SEQUENCE:
        return _collect_sequence_route(spec)

    if spec.kind is AgentKind.PARALLEL:
        raise UnrecoverableError(
            f"pattern {spec.name!r} declares a parallel fan-out; not in R-3 route scope"
        )

    raise UnrecoverableError(
        f"pattern {spec.name!r} is a composite without a linear atomic sequence"
    )


__all__ = ["starting_route"]