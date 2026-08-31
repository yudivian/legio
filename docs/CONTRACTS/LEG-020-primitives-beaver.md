# LEG-020 — Primitives over beaver (implementation)

- **Status:** SUPERSEDED (decision: *no invented substrate layer* — the
  beaver-backed wrapper was deleted; agents and the Runtime now call
  beaver natively, LEG-048)
- **Rasante:** R-2
- **GitHub issue:** #12
- **Source:** `docs/PLAN.md` (LEG-020)
- **Depends on:** LEG-012 (interface), LEG-011 (message types)

> **Superseded by** the native-beaver substrate (LEG-048): the "combustion" of
> the three primitives *on top of* beaver is gone because beaver itself provides
> them. The behaviors this spec pinned (lease TTL + `renew` as the task lease,
> `next_run_at` scheduling via priority, namespacing, async-only) are now
> exercised directly in the AgentBase/Runtime suites against a real beaver
> file (see `docs/ARCHITECTURE.md` §2 and `tests/conftest.py`).

## Goal
Implement Queue, Board and Lock on top of beaver (Redis), satisfying the
LEG-012 contract.

## Scope
- **In scope:** beaver-backed combustion of the three primitives, lazy
  connection, namespacing.
- **Out of scope:** anything above the primitives.

## Contract & design
- **Queue:** sorted-set based (score = priority/schedule epoch) with
  `next_run_at` support; `lease` vs `ack` split so re-queuing after lease
  expiry is safe (LEG-060); dedup on push (idempotency key for LEG-093).
- **Board:** persistent hash/key-space per scope with TTL on volatile entries.
- **Lock:** beaver lock with TTL + `renew` (the lease); a lock is bound to a
  queue item id.
- Namespacing strictly per LEG-012; all calls async.

## Interface
- The LEG-012 protocols.

## Acceptance criteria
From `docs/PLAN.md` (LEG-020), verbatim:
- All LEG-012 conformance tests pass in green against real beaver; priority
  ordering, `next_run_at` retry scheduling, lease TTL + renew, and
  reclaim-after-expiry each behave as specified.

## Tests
- Conformance suite (red-first from LEG-012) run against beaver; lease claim/renew.

## Validation case
- Substrate for every later example.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.