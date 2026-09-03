# LEG-012 — Native beaver primitives

- **Status:** APPROVED (native-beaver substrate — agents and the Runtime speak
  beaver directly; see `docs/ARCHITECTURE.md` §2)
- **Rasante:** R-1 (contract)
- **GitHub issue:** #6
- **Source:** `docs/PLAN.md` (LEG-012)
- **Depends on:** ARCHITECTURE §2

## Goal

Pin the semantics of the three substrate primitives the whole system builds on.
There is no legio-owned `primitives` abstraction: `beaver`'s own persistent
dicts, queues and locks are addressed directly (`db.dict(scope)`,
`db.queue("legio:queue:<agent>")`, `db.lock(...)`).

## Scope

- **In scope:** the semantics and namespacing rules legio relies on.
- **Out of scope:** beaver internals.

## Contract & design

- **Queue** — persistent priority queue per agent; `get(block=False)` is a
  destructive pop (`IndexError` when empty); priority ordering. The agent pops
  an item once and routes it (rule 8, polling only) — no lease.
- **Registry** — persistent dict per scope: `tasks` (TaskRegistry), `gates`,
  `catalog`, `outbox`, `semaphore` (no `results:{task_id}` — Schema 2 delivers
  the root result to the task's final-result queue, not a registry).
- **Lock** — TTL + `renew`; used only where genuine mutual exclusion over a
  shared key is required (not as a per-dispatch task lease).
- Namespacing: `legio:queue:<agent>`; dict scopes are beaver dict scopes; all
  calls async.

## Interface

- Native beaver asynchronous primitives (`db.dict`, `db.queue`, `db.lock`).

## Acceptance criteria

From `docs/PLAN.md` (LEG-012), verbatim:
- Signature conformance tests against the contract; queue/lock semantics
  observable by test.

## Tests

- Contract tests (red first): conformance, queue/lock observability.

## Validation case

- Unit-level (primitives are the substrate).

## Definition of done

- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.
