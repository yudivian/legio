# LEG-062 — DLQ after max attempts

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-6
- **GitHub issue:** #33
- **Source:** `docs/PLAN.md` (LEG-062)
- **Depends on:** LEG-061

## Goal
After `attempts` reaches the max, the item moves to a dead-letter queue,
visible as a failed task result — never silently dropped.

## Scope
- **In scope:** DLQ landing, failed-task visibility, no silent loss.
- **Out of scope:** DLQ UX/retry-from-DLQ.

## Contract & design
- Max attempts from pattern/global config; on reaching max, deposit
  `ExecutionResultMessage` (failure, `recoverable=False`) to the caller as the
  authoritative result, and mark the queue item dead in DLQ.
- The task always ends in a known terminal state (`failed`) with the DLQ
  reference.

## Interface
- `DLQ` abstraction + failed state on `tasks`/`results`.

## Acceptance criteria
From `docs/PLAN.md` (LEG-062), verbatim:
- After `attempts` ≥ max, item lands in DLQ and is visible as a failed task
  result; never silently dropped.

## Tests
- Contract tests (red first): max attempts → DLQ + failed result.

## Validation case
- Resilience scenario suite (LEG-064 part 2).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.