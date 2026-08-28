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

R-0 (Foundation) in progress: dependency list approved, governance reviewed and
frozen, package bootstrap and CI in place. Contract specs (R-1) come next.