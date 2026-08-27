# LEG-082 — Graceful shutdown + concurrency semaphores

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-8
- **GitHub issue:** #37
- **Source:** `docs/PLAN.md` (LEG-082)
- **Depends on:** LEG-060, LEG-013 (per-tool)

## Goal
Operational hygiene: SIGTERM drains in-flight `<lease>{task}</lease>` before
exit; per-tool and per-LLM concurrency semaphores are honored.

## Scope
- **In scope:** graceful drain, per-tool + per-LLM semaphores.
- **Out of scope:** load-balancing (LEG-080), queue priorities (LEG-061).

## Contract & design
- On SIGTERM: stop leasing, drain in-flight items (result always deposited),
  then exit; lease renewal stops only after deposit (LEG-060 safety).
- Sempahores cap concurrent LLM calls and per-tool executions; a constrained
  tool simply waits rather than failing.

## Interface
- `Semaphore`-based guards; shutdown hook in worker/server lifecycle.

## Acceptance criteria
From `docs/PLAN.md` (LEG-082), verbatim:
- SIGTERM drains in-flight leases before exit; per-tool concurrency cap is
  honored under load (test with a slow fake tool).

## Tests
- Contract tests (red first): drain on SIGTERM, per-tool cap.

## Validation case
- Slow-tool load test (LEG-080 lane).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.