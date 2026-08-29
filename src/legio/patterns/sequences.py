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
from legio.patterns import PatternSpec, Stage, kind


def _stage_agent_name(stage: Stage) -> str:
    name = stage.name or stage.stage
    if not name:
        raise UnrecoverableError(
            "a sequence stage must carry a name or stage to form a static route"
        )
    return name


def starting_route(spec: PatternSpec) -> tuple[str, ...]:
    """Return the ordered sub-DAG (stage names) for a sequence starting pattern.

    - A single atomic pattern yields ``(spec.name,)``.
    - A ``main``/composite pattern with a linear ``sequence`` of atomic stages
      yields the stage names in order.
    - Anything else (parallel, nested composite) is out of R-3 scope and raises.
    """
    if spec.parallel:
        raise UnrecoverableError(
            f"pattern {spec.name!r} declares a parallel fan-out; not in R-3 route scope"
        )
    if spec.sequence:
        return tuple(_stage_agent_name(stage) for stage in spec.sequence)
    if spec.kind is kind.COMPOSITE:
        raise UnrecoverableError(
            f"pattern {spec.name!r} is a composite without a linear atomic sequence"
        )
    return (spec.name,)


__all__ = ["starting_route"]
