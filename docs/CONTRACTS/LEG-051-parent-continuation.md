# LEG-051 — Uniform parent continuation in every composite frontier (Schema 2)

- **Status:** DRAFT (awaiting maintainer approval; reworded 2026-08-31 to the
  Schema 2 continuation model — no `client:{task_id}`-style identity)
- **Rasante:** R-5
- **GitHub issue:** #28
- **Source:** `docs/PLAN.md` (LEG-051); `docs/AGENT_LIFECYCLE.md` §4.11 Schema 2
- **Depends on:** LEG-040, LEG-041

## Goal
Uniform rule: every composite frontier (sequence *and* parallel) continues along
`end_of_level_queue` — the exact creator (the launching parallel's gathering
queue, or the submit's final-result queue at flow end) — including nested
composites.

## Scope
- **In scope:** parent continuation across sequence/parallel, nested composites.
- **Out of scope:** the flow-end (final-result) delivery (LEG-053).

## Contract & design
- A composite completion at **end-of-level with `level > 1`** always deposits its
  `ExecutionResultMessage` to `end_of_level_queue` — the queue the launching
  parallel assigned (its **gathering queue**), which is the "parent" of that
  branch. There is no `client:{task_id}`-style identity and no store.
- Nested composite-inside-composite: an inner composite's branch-close surfaces
  first to its enclosing composite's gathering queue (via its own
  `end_of_level_queue`, `level` decrementing per completed fan-in); a composite
  at `level == 1` in last position delivers the final result to the submission's
  final-result queue (generalized end rule).
- The parent continuation is the endpoint named by `end_of_level_queue` in the
  token — assigned by the flow creator, never decided by the agent.

## Interface
- Completion routing internal to `run()` (LEG-023).

## Acceptance criteria
- Sequence *and* parallel continue to the exact creator that deposited them
  (per `end_of_level_queue`), including nested composites; the composite-inside-
  composite test satisfies the Schema 2 `level`/`end_of_level_queue` rules.

## Tests
- Contract tests (red first): parent-queue exactness, nesting, `level`
  bookkeeping.

## Validation case
- A composite-inside-composite in-repo test fixture (nested parallel, run 2).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.
