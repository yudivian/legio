# legio

A queue-based agentic orchestration engine. Independent library, domain-free:
all domain knowledge lives in patterns (YAML) and a tool registry provided by the
consumer. The library never knows about any specific consumer; validation happens
through in-repo examples and external consumer repositories kept separate.

## Repo layout

- `AGENTS.md` — mandatory working rules for implementing agents.
- `docs/ARCHITECTURE.md` — the legio architecture (read before any work).
- `docs/CONTRIBUTING.md` — methodology, development flow and review checklist.
- `docs/PLAN.md` — complete plan and issue roadmap.
- `docs/DEPENDENCIES.md` — dependency list (approved).
- `docs/JOURNALS/` — turn-by-turn journaling; read the latest before working.

## State

R-3 (Atomics) **shipped**, on the Schema 2 engine. Done:

- R-0 (Foundation): governance frozen, package bootstrap, CI — **done**.
- R-1 (Contracts): specs approved with red contract tests for LEG-010..017.
  The contracts and `docs/PLAN.md` are aligned to the three schemas
  (`docs/AGENT_LIFECYCLE.md` §4.11): **S1** one agent spec (type × kind,
  mandatory symmetric contracts, terse `parameters`), **S2** the class token
  that travels between class queues (`level_route`/`current_index`/
  `end_of_level_queue`/`level`, no boards), **S3** the `available_tools`
  declaration (`implementation` + `policy`).
- R-2 (Walking skeleton): native beaver substrate (queues/dicts/locks spoken
  directly, no invented wrapper layer — LEG-048), flow messages + token
  (LEG-011/023), mini-manager `submit`/`status` over the final-result queue
  (LEG-014/024), federation + naming + errors + security (LEG-015/016/017),
  REST worker surface (LEG-025), E2E `transform` example (LEG-026), auth
  middleware (LEG-027) — **shipped** on a decoupled, polling base (Schema 2;
  no `results` board, no `client:` pseudo-agent).
- R-3 (Atomics): LinguisticAgent (LEG-030) with lingo's `MockLLM` producing a
  validated `output_model` record, structured-output/template contract with an
  explicit undefined-path error (LEG-031), and the `summarize` linguistic→tool
  example (LEG-032) — **shipped**.

**Pending migration (per issue, contract-first):** the S1 engine (patterns
loader LEG-010/021, ToolAgent LEG-022, `output_schema` compile LEG-072) and the
S3 tools registry (LEG-013) are still the v1 implementations — their contracts
in `docs/CONTRACTS/` specify the Schema 1/3 targets, and the code migration is
the next planned work stream.

On the roadmap: the S1/S3 code migration, then R-4 (composites), R-5 (token),
R-6 (resilience), R-7 (patterns engine), R-8 (runtime), R-9 (federation),
R-10 (hardening & release).