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
> `docs/ARCHITECTURE.md` §2. The design intent below (queue/lock semantics,
> scope model) still holds; the *wrapper API* does not. There is no lease in the
> dispatch: an agent pops an item once and routes it (rule 8, polling only).

## Goal
Pin the interface of the three substrate primitives (Queue, Registry, Lock) that
the whole system builds on, over beaver.

## Scope
- **In scope:** public signatures, semantics and namespacing rules.
- **Out of scope:** beaver internals, the beaver-backed implementation
  (LEG-020).

## Contract & design
- **Queue** — persistent priority queue per agent; `get` (destructive pop) /
  `put` / priority ordering; the agent pops an item once and routes it (rule 8).
- **Registry** — persistent dict per scope: `tasks` (TaskRegistry), `gates`,
  `catalog`, `outbox`, `semaphore` (no `results:{task_id}` — Schema 2 delivers
  the root result to the task's final-result queue, not a registry).
- **Lock** — TTL + `renew`; used only where genuine mutual exclusion over a
  shared key is required (not as a per-dispatch task lease).
- Namespacing: `legio:queue:<agent>`, `legio:registry:<scope>`.

## Interface
- Python interface definitions (e.g. `asyncio`-friendly protocol) for the three
  primitives.

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