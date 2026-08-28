# legio

A board-and-queue agentic orchestration engine. Independent library, domain-free:
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

R-2 (walking skeleton) **shipped**. Done:

- R-0 (Foundation): governance frozen, package bootstrap, CI — **done**.
- R-1 (Contracts v1): specs approved with red contract tests for LEG-010..017 —
  **shipped**.
- R-2 (Walking skeleton): substrate primitives over beaver / in-memory
  (LEG-012/020), flow messages + token (LEG-011), tool registry (LEG-013),
  patterns loader + output schema (LEG-010/021), ToolAgent (LEG-022), uniform
  AgentBase.run loop (LEG-023), mini-manager + client pseudo-agent (LEG-014),
  federation + naming + errors + security (LEG-015/016/017), REST worker
  surface (LEG-025), E2E `transform` example (LEG-026), auth middleware
  (LEG-027) — **shipped** on a board-backed, decoupled polling base.

On the roadmap: R-3 (atomics), R-4 (composites), R-5 (token), R-6 (resilience),
R-7 (patterns engine), R-8 (runtime), R-9 (federation), R-10 (hardening &
release).