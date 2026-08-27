# LEG-080 — Pools (pool_size replicas per agent)

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-8
- **GitHub issue:** #40
- **Source:** `docs/PLAN.md` (LEG-080)
- **Depends on:** LEG-060 (leases)

## Goal
Horizontal capacity: `pool_size` replicas of an agent consuming the same queue
concurrently, each item leased exactly once; single-replica behavior unchanged.

## Scope
- **In scope:** pool_size, concurrent consumption, exactly-once lease.
- **Out of scope:** cross-node pools (R-9 owns federation).

## Contract & design
- A pool = N worker loops on the same agent queue; lease claims items
  atomically (LEG-060) so only one replica executes each item.
- `pool_size: 1` default equals the single-replica path.

## Interface
- Agent/pool config field; worker pool instantiation.

## Acceptance criteria
From `docs/PLAN.md` (LEG-080), verbatim:
- n replicas on the same queue process n items concurrently; each item leased
  exactly once; single-replica behavior unchanged.

## Tests
- Contract tests (red first): concurrency, exactly-once, n=1 regression.

## Validation case
- Load test with the `distribute_summary` example (slow fake tool).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.