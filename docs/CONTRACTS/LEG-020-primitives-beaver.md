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
> them. Queue/dict/lock semantics, namespacing and async-only are exercised
> directly in the AgentBase/Runtime suites against a real beaver file (see
> `docs/ARCHITECTURE.md` §2 and `tests/conftest.py`). The dispatch is
> polling-only and carries no lease: an item is popped once and routed (rule 8).

## Goal
Implement Queue, Registry and Lock on top of beaver (Redis), satisfying the
LEG-012 contract.

## Scope
- **In scope:** beaver-backed combustion of the three primitives, lazy
  connection, namespacing.
- **Out of scope:** anything above the primitives.

## Contract & design
- **Queue:** sorted-set based (score = priority epoch) with destructive `get`
  (an item is popped once and routed — no lease, no schedule gate); dedup on
  push (idempotency key for LEG-093).
- **Registry:** persistent hash/key-space per scope with TTL on volatile
  entries.
- **Lock:** beaver lock with TTL + `renew`, used only where genuine mutual
  exclusion over a shared key is required.
- Namespacing strictly per LEG-012; all calls async.

## Interface
- The LEG-012 protocols.

## Acceptance criteria
From `docs/PLAN.md` (LEG-020), verbatim:
- All LEG-012 conformance tests pass in green against real beaver; priority
  ordering and namespace isolation behave as specified.

## Tests
- Conformance suite (red-first from LEG-012) run against beaver; queue/lock semantics.

## Validation case
- Substrate for every later example.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.