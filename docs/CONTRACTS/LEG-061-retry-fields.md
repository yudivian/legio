# LEG-061 — Retry as fields: next_run_at, attempts, queue priority

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-6
- **GitHub issue:** #32
- **Source:** `docs/PLAN.md` (LEG-061)
- **Depends on:** LEG-012, LEG-016, LEG-020

## Goal
Retry policy as data fields on the queue item — not a scheduler: `next_run_at`,
`attempts`, and queue priority evolve the item state.

## Scope
- **In scope:** the three fields, their semantics, priority-based queue.
- **Out of scope:** DLQ after max (LEG-062), failure policy per composite
  (LEG-063).

## Contract & design
- Sorted queue keyed by priority/schedule: `next_run_at` in the future → not
  leaseable before then; `attempts` increments per execution (driven by
  `retriable` from LEG-016 taxonomy); priority orders whichever item is next.
- Failure is recorded in the task result; a retry re-executes from the item,
  not from scratch.

## Interface
- Queue push/lease honoring `next_run_at`/priority; item fields.

## Acceptance criteria
From `docs/PLAN.md` (LEG-061), verbatim:
- Failed task with `next_run_at` in the future is not executed before it;
  `attempts` increments on each try.

## Tests
- Contract tests (red first): scheduling gate, attempts increment.

## Validation case
- Resilience scenario suite (LEG-064 part 2).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.