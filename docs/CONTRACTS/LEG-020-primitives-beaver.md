# LEG-020 — Native beaver substrate

- **Status:** APPROVED (native-beaver substrate — agents and the Runtime speak
  beaver directly; see `docs/ARCHITECTURE.md` §2)
- **Rasante:** R-2
- **GitHub issue:** #12
- **Source:** `docs/PLAN.md` (LEG-020)
- **Depends on:** LEG-011 (message types)

## Goal

Pin how legio consumes the beaver substrate: there is no legio-owned
`primitives` abstraction layer. `beaver` provides the persistent
queue/dict/lock primitives, and legio addresses them directly by name
(`db.queue`, `db.dict`, `db.lock`) exactly as castor's Manager does.

## Scope

- **In scope:** the native beaver semantics legio relies on — queue (priority,
  destructive pop), dict (per-scope registry), lock (TTL + renew), namespacing,
  async-only — and how the AgentBase/Runtime suites exercise them.
- **Out of scope:** anything above the substrate.

## Contract & design

- The agent's queue is a native beaver queue addressed by name:
  `db.queue("legio:queue:<agent>")`. `get(block=False)` pops destructively
  (`IndexError` when empty); an item is popped once and routed — no lease, no
  schedule gate (rule 8, polling only).
- Registries are native beaver dicts addressed by scope (`db.dict(scope)`):
  `tasks` (TaskRegistry), `gates`, `catalog`, `outbox`, `semaphore`.
- A native beaver lock (`db.lock(...)`) with TTL + `renew` is used only where
  genuine mutual exclusion over a shared key is required — not as a per-dispatch
  task lease.
- Namespacing: the sole legio-invented name is `legio:queue:<agent>`; dict
  scopes are beaver dict scopes. All calls are async.
- The dispatch is stateless and polling-only: an item is popped once and routed
  (rule 8). Failures are never silent (rule 9).

## Interface

- Native beaver asynchronous primitives (`db.queue`, `db.dict`, `db.lock`) as
  consumed by `AgentBase` and the Runtime — there is no legio wrapper API.

## Acceptance criteria

From `docs/PLAN.md` (LEG-020), verbatim:
- The AgentBase runner consumes from a native beaver queue and a temp beaver
  file, exercising priority ordering and namespace isolation directly.

## Tests

- Conformance suite against real beaver (temp file): queue priority/ordering,
  destructive pop, dict scope isolation, lock semantics — via the AgentBase/Runtime
  suites (`tests/conftest.py`).

## Validation case

- Substrate for every later example.

## Definition of done

- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.
