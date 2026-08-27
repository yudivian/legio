# LEG-060 — Leases with heartbeat + reaper re-queue

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-6
- **GitHub issue:** #31
- **Source:** `docs/PLAN.md` (LEG-060)
- **Depends on:** LEG-012, LEG-020 (Lock TTL)

## Goal
Make task execution crash-safe: a task lease (Lock with TTL + heartbeat) that,
on expiry without renewal, is re-queued by the reaper and executed exactly once
overall.

## Scope
- **In scope:** lease heartbeat, lease expiry detection, reaper re-queue,
  exactly-once execution.
- **Out of scope:** retry attempts counters (LEG-061), DLQ (LEG-062).

## Contract & design
- Queue item carries lease lock (per-item id); worker heartbeats (renews TTL)
  while on `run()`; a reaper sweeps expired leases and re-queues the item.
- Exactly-once: `ack` only after the result is durably deposited; re-execution
  after crash is safe because deposit+ack are guarded (idempotency by id).

## Interface
- `Lease` (claim/renew) + `Reaper` over the Queue.

## Acceptance criteria
From `docs/PLAN.md` (LEG-060), verbatim:
- Simulated crash mid-task → lease expires → reaper re-queues → task completes
  once, exactly.

## Tests
- Contract tests (red first): crash simulation, re-queue, exactly-once.

## Validation case
- Resilience scenario suite (LEG-064 part 1).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.