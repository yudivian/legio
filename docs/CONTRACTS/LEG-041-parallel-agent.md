# LEG-041 — Parallel agent

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-4
- **GitHub issue:** #24
- **Source:** `docs/PLAN.md` (LEG-041)
- **Depends on:** LEG-023, LEG-031, LEG-051

## Goal
Implement the parallel composite: concurrent fan-out of steps, gathered at a
join via the dual queue with path-identity (LEG-052).

## Scope
- **In scope:** concurrent deposit of child tasks across agents, fan-in join
  on path, merge on all-complete.
- **Out of scope:** parallel failure policy (LEG-063), pools (LEG-080).

## Contract & design
- Critical: one step per child task; `task_id`+path naming per step
  (LEG-052) — "two B-step tasks at different positions are distinct tasks".
- Fan-in identity by path guarantees the join gathers exactly the step's
  children; join reads the hole (blocking skip) until all present.
- Inline steps: tool → auto-named sub-agent queue; linguistic → self-run by
  gatherer (H1).
- Merge flat-union with `output_as` (H3); fail policy hooks LEG-063.

## Interface
- `ParallelAgent` composite class implementing the fan-in join.

## Acceptance criteria
From `docs/PLAN.md` (LEG-041), verbatim:
- Two parallel branches both executes and their outputs merge on join;
  release parallelism (both late-started together) in tests.

## Tests
- Contract tests (red first): fan-out, join on all-complete, parallelism.

## Validation case
- `distribute_summary` (R-4 example).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.