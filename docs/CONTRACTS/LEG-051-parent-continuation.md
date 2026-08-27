# LEG-051 — Uniform parent continuation in every composite frontier

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-5
- **GitHub issue:** #28
- **Source:** `docs/PLAN.md` (LEG-051)
- **Depends on:** LEG-040, LEG-041

## Goal
Uniform rule: every composite frontier (sequence *and* parallel) returns to the
exact parent that deposited it — including nested composites.

## Scope
- **In scope:** parent continuation across sequence/parallel, nested composites.
- **Out of scope:** ultimate_return to client (LEG-053).

## Contract & design
- A composite completion always deposits `ExecutionResultMessage` to the
  parent's `client:{task_id}`-style identity that financed it (parent PID /
  task id + path).
- Nested composite-inside-composite: inner completion surfaces first to its
  enclosing composite; only the root leaves for the client.

## Interface
- Completion routing internal to `run()` (LEG-023).

## Acceptance criteria
From `docs/PLAN.md` (LEG-051), verbatim:
- Sequence *and* parallel return to the exact parent that deposited them;
  nested composite returns correctly (tested with a composite-inside-composite).

## Tests
- Contract tests (red first): parent identity exactness, nesting.

## Validation case
- A composite-inside-composite in-repo test fixture.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.