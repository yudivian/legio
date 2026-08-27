# LEG-064 — Resilience scenario tests

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-6
- **GitHub issue:** #35
- **Source:** `docs/PLAN.md` (LEG-064)
- **Depends on:** LEG-060..LEG-063

## Goal
Four explicit, green, in-repo resilience scenarios covering R-6 end to end.

## Scope
- **In scope:** the four scenario tests in CI.
- **Out of scope:** anything beyond the listed scenarios.

## Contract & design
The four scenarios (each a runnable test):
1. **Lease expiry / crash mid-task** — crash → lease expires → reaper
   re-queues → completes exactly once (LEG-060).
2. **Crash mid-task (deposit)** — result deposited then crash; no duplicate
   write (LEG-050/060).
3. **Provider outage** — unavailable tool → `next_run_at`-gated retry (LEG-061),
   then DLQ after max (LEG-062).
4. **Priority** — `next_run_at`/priority discipline observed during contention
   (LEG-061).

## Interface
- Test scenario harness over the worker.

## Acceptance criteria
From `docs/PLAN.md` (LEG-064), verbatim:
- The four scenarios are explicit green tests in CI.

## Tests
- The four scenarios.

## Validation case
- These scenarios *are* the resilience validation.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.