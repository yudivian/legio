# LEG-012 — Primitives interface (v1)

- **Status:** CLOSED (implementation green, maintainer approved, issue closed)
- **Rasante:** R-1 (contract)
- **GitHub issue:** #6
- **Source:** `docs/PLAN.md` (LEG-012)
- **Depends on:** ARCHITECTURE §2

## Goal
Pin the interface of the three substrate primitives (Queue, Board, Lock) that
the whole system builds on, over beaver.

## Scope
- **In scope:** public signatures, semantics and namespacing rules.
- **Out of scope:** beaver internals, the beaver-backed implementation
  (LEG-020).

## Contract & design
- **Queue** — persistent priority queue per agent; `push` / `lease` / `ack` /
  `pop`; `next_run_at` schedules retries as a field (no scheduler).
- **Board** — persistent dict per scope: `blackboard:{node}:{task_id}`,
  `frames:{agent}:{task_id}`, `semaphore`, `results:{task_id}`, `catalog`,
  `outbox`, `tasks`.
- **Lock** — TTL + `renew`; it is the task lease; expiry makes items reclaimable.
- Namespacing: `legio:queue:<agent>`, `legio:board:<scope>:<key>`.

## Interface
- Python interface definitions (e.g. `asyncio`-friendly protocol) for the three
  primitives.

## Acceptance criteria
From `docs/PLAN.md` (LEG-012), verbatim:
- Signature conformance tests against the contract; lease TTL/renew observable
  by test.

## Tests
- Contract tests (red first): conformance, lease observability.

## Validation case
- Unit-level (primitives are the substrate).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.