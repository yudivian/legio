# LEG-012 — Primitives interface (v1)

- **Status:** SUPERSEDED (decision: *no invented substrate layer* — agents and
  the mini-manager speak native beaver directly, LEG-048; `legio.primitives`
  was deleted and its contract tests migrated to native-beaver suites)
- **Rasante:** R-1 (contract)
- **GitHub issue:** #6
- **Source:** `docs/PLAN.md` (LEG-012)
- **Depends on:** ARCHITECTURE §2

> **Superseded by** the native-beaver substrate (LEG-048): the three primitives
> no longer wrap beaver behind a legio-owned interface. `beaver`'s own
> persistent dicts/queues/locks are addressed directly (`db.dict(scope)`,
> `db.queue("legio:queue:<agent>")`, `db.lock(...)`) — see
> `docs/ARCHITECTURE.md` §2. The design intent below (lease as lock, `next_run_at`
> field, no scheduler, scope model) still holds; the *wrapper API* does not.

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