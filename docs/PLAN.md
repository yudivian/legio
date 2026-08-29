# PLAN — Development plan by verifiable issues

Process: **plan with issues → specs (approved) → implementation**. Every issue
below carries an explicit, testable acceptance criterion (marked **Accept**).
An issue is *done* only when its criterion is demonstrably met by a running
check (test, command, or CI job) — not by eyeballing. Each issue has its spec
in `docs/CONTRACTS/LEG-xxx-*.md`, and the GitHub issue links to that file. The
GitHub issues in this repo mirror this document one-to-one (labels R-0..R-10).

Read `docs/ARCHITECTURE.md` for the design these issues implement, and
`docs/CONTRIBUTING.md` for the methodology (contract-first TDD, dogfooding,
vertical slices).

## Rasantes (vertical slices)

`R-0` Foundation → `R-1` Contracts v1 → `R-2` Walking skeleton → `R-3` Atomics
→ `R-4` Composites → `R-5` Token → `R-6` Resilience → `R-7` Patterns engine →
`R-8` Runtime → `R-9` Federation → `R-10` Hardening & release.

Per-rasante definition of done: written contract + contract tests + implementation
+ validation case green (an external consumer repo or the in-repo fictitious
domain) + docs + journal entry.

## Issues

### R-0 — Foundation

- **LEG-001** Repository & package bootstrap: layout, `pyproject.toml`, `uv`
  init, docs set (this series), `.gitignore`.
  - **Accept**: `uv run python -c "import legio"` works; `uv lock` resolves
    against the approved dependency set only; package builds.
- **LEG-002** CI pipeline: ruff + tests + typecheck; environment via `uv`.
  - **Accept**: a PR triggers one pipeline running `uv run ruff check`,
    `uv run pytest`, and typecheck; a failing test turns the job red and a
    passing one green. No real network/LLM in CI.
- **LEG-003** Governance docs reviewed & frozen (AGENTS, CONTRIBUTING,
  ARCHITECTURE, PLAN, DEPENDENCIES, journal template).
  - **Accept**: every doc cross-references only existing files; all issue
    numbers mentioned in docs exist in this PLAN; an approval is recorded in
    the journal.

### R-1 — Contracts v1 (specs, approved before coding)

Each contract issue produces a spec document in `docs/CONTRACTS/` plus the
contract test file that fixes it (red before implementation). **Accept** for
every contract issue: spec approved (journal) and its contract tests exist and
are red for the yet-unimplemented surface.

- **LEG-010** Patterns YAML schema (v1): pattern kinds, stages, schemas,
  `input_mapping`, `output_as`, `main` flag. Incorporates the single-node model
  validation findings (H1–H4 from
  `docs/VALIDATIONS/single-node-model.md`):
  inline stages (parallel auto-named, linguistic self-executed), dotted
  template paths + system variables (H2), flat-union merge + cumulative
  sequence (H3), schema compilation with unions/recursion (H4).
  - **Accept**: a fixture translating two representative composite patterns
    into schema-valid YAML v1 loads and validates; a prompt with
    `{input.payload}`, `{substep.data}`, `{current_date}` fills
    from the scoped board.
- **LEG-011** FlowToken & messages (v1): fields, semantics, `schema_version`,
  root handling, delivery.
  - **Accept**: serialization/deserialization round-trip preserves all fields;
  versioned, rejected on major mismatch; finality derived from position.
- **LEG-012** Primitives interface (v1): Queue/Board/Lock API over beaver.
  Superseded by the native-beaver substrate (LEG-048) — no `legio.primitives`
  wrapper; beaver primitives are addressed directly (`docs/ARCHITECTURE.md` §2).
  - **Accept**: signature conformance tests against the contract; lease
    TTL/renew observable by test.
- **LEG-013** Tool registry interface (v1): registration, schemas, lifecycle.
  - **Accept**: registering a fake tool, resolving by `tool_type`, and
    validating input/output schemas are covered by contract tests.
- **LEG-014** Mini-manager contract (v1): `submit`/`status` over boards, client
  token ownership tagging (per LEG-017).
  - **Accept**: submit records `task_id` + `client_id`; status scopes to the
    requesting `client_id`.
- **LEG-015** Federation contract (v1): symmetric catalog, work-item, outbox
  with versioned interfaces.
  - **Accept**: contract tests cover read-before-write, idempotency, and
    interface/schema mismatch returning 4xx.
- **LEG-016** Naming & error conventions (v1): queue/board namespacing,
  namespace prefixes, error model.
  - **Accept**: a check (lint/unit) verifies every producer uses the
    `legio:queue:`/`legio:board:` prefixes and error types conform.
- **LEG-017** Security contract (v1): two levels — shared federation token +
  per-system client tokens with individual revocation; default all starting
  agents unless restricted; ownership of task results.
  - **Accept**: contract tests confirm wrong/missing token → 401/403; a
    revoked client token is rejected immediately while others keep working;
    a restricted token cannot submit unlisted starting agents.

### R-2 — Walking skeleton

- **LEG-020** Primitives over beaver (Queue/Board/Lock + lease semantics).
  Superseded by the native-beaver substrate (LEG-048) — the wrapper
  implementation was deleted; its behaviors (lease TTL + renew, `next_run_at`
  priority, namespacing) are now exercised in the AgentBase/mini-manager suites
  directly against beaver.
  - **Accept**: priority ordering, `next_run_at` retry scheduling, lease TTL +
    renew, and reclaim-after-expiry each have a passing integration test
    against a temp beaver file.
- **LEG-021** Patterns loader (minimal): YAML → `PatternSpec` (pydantic).
  - **Accept**: minimal atomic+tool and sequence patterns load; invalid YAML
    raises a structured loader error (fail-fast).
- **LEG-022** ToolAgent + tool registry execution path.
  - **Accept**: fake tool executes through registry; result written to board
    under `output_as`; schema-validated; failure yields a visible error in the
    task result.
- **LEG-023** AgentBase `run()`: polling loop + lease + heartbeat.
  - **Accept**: one replicated agent consumes a message within lease; a dead
    replica's message becomes reclaimable before lease expiry; no infinite busy loop.
- **LEG-024** Mini-manager: `submit`/`status` backed by boards + client token
  ownership (LEG-014/017).
  - **Accept**: submitting with token A creates a task owned by A; status with
    a different token (or none) is rejected/empty.
- **LEG-025** Worker: single replica running one agent.
  - **Accept**: `legio worker --agent <name>` processes a deposited message to
    completion; observable state changes in boards.
- **LEG-026** E2E example: `transform` with a fake tool (domain-free).
  - **Accept**: submitting `transform` through the API yields its output
    in `results:{task_id}`; example is a green test (does not bitrot).
- **LEG-027** Auth middleware (v1): single middleware enforcing the
  LEG-017 endpoint→token map for the API surface.
  - **Accept**: middleware tests match the LEG-017 §9 contract list for
    `submit`/`status`.

### R-3 — Atomics

- **LEG-030** LinguisticAgent with lingo (`LLM` + `eng.create`).
  - **Accept**: linguistic pattern produces structured output via lingo with
    `MockLLM`; schedule recorded only when actually needed.
- **LEG-031** Structured output wiring + MockLLM tests.
  - **Accept**: malformed LLM output raises a visible structured error, never
    silent; MockLLM fixture drives golden tests.
- **LEG-032** Example `summarize` (linguistic, fake LLM).
  - **Accept**: `summarize` is a green test using MockLLM end-to-end.

### R-4 — Composites

- **LEG-040** SequenceAgent (advance index, chain, continuation).
  - **Accept**: a 3-stage sequence runs to completion on one node; index
    advances exactly once per stage; final stage delivers to parent/client.
- **LEG-041** ParallelAgent: dual queue, call-frames, fan-out.
  - **Accept**: single-node parallel with 3 children completes with all results;
    a missing child result blocks (tolerant policy is R-6).
- **LEG-042** Fan-in by DAG path + `output_as` merging (H3 semantics).
  - **Accept**: two occurrences of the same child pattern in one DAG are
    distinct tasks (dedupe by path, not agent name); merge is flat-union;
    collisions resolved by `output_as`.
- **LEG-043** Examples `extract_and_summarize` (sequence) and `distribute_summary`
  (parallel), domain-free.
  - **Accept**: both are green tests exercising real composite flows.

### R-5 — Token

- **LEG-050** Root token authoring & root delivery (`client:{task_id}`).
  - **Accept**: root task result lands in `results:{task_id}` exactly once and
    is readable via status; no re-delivery after ack.
- **LEG-051** Uniform parent continuation in every composite frontier.
  - **Accept**: sequence *and* parallel return to the exact parent that
    deposited them; nested composite returns correctly (tested with a
    composite-inside-composite).
- **LEG-052** Fan-in identity by path (not agent name); `output_as`
  namespacing fixes.
  - **Accept**: same-named parallel branches at different positions do not
    merge; regression tests cover the earlier agent-name bug.
- **LEG-053** `ultimate_return` delivery semantics (internal vs client).
  - **Accept**: head tasks deliver internally, root tasks to the client;
    covered by contract tests.

### R-6 — Resilience

- **LEG-060** Leases with heartbeat + reaper re-queue.
  - **Accept**: simulated crash mid-task → lease expires → reaper re-queues →
    task completes once, exactly.
- **LEG-061** Retry as fields: `next_run_at`, `attempts`, queue priority.
  - **Accept**: failed task with `next_run_at` in the future is not executed
    before it; `attempts` increments on each try.
- **LEG-062** DLQ after max attempts.
  - **Accept**: after `attempts` ≥ max, item lands in DLQ and is visible as a
    failed task result; never silently dropped.
- **LEG-063** Parallel partial/fail policy configurable per pattern.
  - **Accept**: pattern with `fail_fast` stops fan-out and reports; with
    tolerant policy a failed child yields a partial success result with
    per-child error entries.
- **LEG-064** Resilience scenario tests (lease expiry, crash mid-task,
  provider outage, priority).
  - **Accept**: the four scenarios are explicit green tests in CI.

### R-7 — Patterns engine

- **LEG-070** Cascade invalidation on invalid dependencies.
  - **Accept**: disabling one broken pattern transitively disables dependents;
  the catalog reflects it; test verifies the full chain.
- **LEG-071** Dry-run validator + strict fail-fast startup.
  - **Accept**: `legio validate --dry-run` reports every invalid pattern and
    exits non-zero; startup refuses to serve a catalog with any invalid
    pattern.
- **LEG-072** Pattern compile: `output_schema` → pydantic models.
  - **Accept**: unions, arrays, nested objects, and recursive schemas compile
    to validating pydantic models (H4); a compiled schema rejects a bad
    payload at the boundary.

### R-8 — Runtime

- **Agent lifecycle** (create / enable / disable / destroy at the Class and
  Instance levels, including dynamic on-the-fly creation and the "disabled ⇒ no
  instances / destroy class = armageddon" rules) is specified in
  `docs/AGENT_LIFECYCLE.md`. This R-8 section is where it is implemented; LEG-080
  (pools) realizes "multiple instances consume the same class queue".
- **LEG-080** Pools (`pool_size` replicas per agent).
  - **Accept**: n replicas on the same queue process n items concurrently; each
    item leased exactly once; single-replica behavior unchanged.
- **LEG-081** Worker CLI (typer): run worker, run federation server
  (config: node id, federation token, client tokens, peer allowlist).
  - **Accept**: `legio worker ...` and `legio server ...` start, expose
    `submit`/`status`, and honor the LEG-017 config shape.
- **LEG-082** Graceful shutdown + concurrency semaphores (LLM, per-tool).
  - **Accept**: SIGTERM drains in-flight leases before exit; per-tool
    concurrency cap is honored under load (test with a slow fake tool).

### R-9 — Federation

- **LEG-090** Per-node catalog (roster derived from capacity, symmetric).
  - **Accept**: catalog served over `GET /catalog` lists agents, interfaces and
    `schema_version`; requester token (federation) validated.
- **LEG-091** Step resolver: required agent → local | remote.
  - **Accept**: author resolves each step locally when present, remote when the
    peer catalog offers it, error otherwise; resolution happens before deposit.
- **LEG-092** Work-item over HTTP + remote deposit, federation-token auth
  (LEG-015/017).
  - **Accept**: `POST /work-items/{agent}` with valid federation token and
    matching interface deposits into the acceptor queue; mismatch → 4xx;
    no token → 401.
- **LEG-093** Outbox polling by the author (write-before-ack, idempotency).
  - **Accept**: author polls outbox, ack consumes; re-read after ack is empty;
    duplicate work-item (same id) is not executed twice.
- **LEG-094** Multi-node example (3 symmetric nodes, domain-free).
  - **Accept**: A triggers a 2-level flow that delegates a capability to B (or
    C) and receives the final result, all with the federation token;
    symmetric: B can trigger A the same way.

### R-10 — Hardening & release

- **LEG-100** Docs & examples hardening; glossary; consumer guide.
  - **Accept**: consumer guide (adding tools + patterns to a node) is
    executable top-to-bottom; examples are all green tests.
- **LEG-101** semver `0.1` + packaging + changelog + tags.
  - **Accept**: `uv build` produces a wheel/archive; `git tag v0.1.0` exists;
    changelog lists every merged issue.
- **LEG-102** An external consumer (own repo) pins the released `legio`, its
  validation suite green.
  - **Accept**: the consumer repo pins the released version; its validation
    suite runs green against it.

## Ordering constraints

- LEG-0xx before LEG-1xx..., except documentation (LEG-003) can be updated
  continuously.
- No implementation issue starts before its contract spec (the LEG-01x range
  covering it) is approved and its contract tests exist (red).
- No dependency is used before `docs/DEPENDENCIES.md` is approved.
- Per-rasante DoD requires the journal entry and the green validation case.