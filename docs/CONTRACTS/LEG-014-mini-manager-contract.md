# LEG-014 — Mini-manager contract (v1)

- **Status:** CLOSED (implementation green, maintainer approved, issue closed)
- **Rasante:** R-1 (contract)
- **GitHub issue:** #8
- **Source:** `docs/PLAN.md` (LEG-014)
- **Depends on:** ARCHITECTURE §3, LEG-011, LEG-015

> **Revised 2026-08-30:** the `client:{task_id}` pseudo-agent, its termination
> flow and the stuck-client reaper were **removed** — R-1 over-engineering,
> redundant with the `results` board from day one. The root result lands on
> `results:{task_id}` only; the client reads it via `status`. (The R-6 lease
> reaper, LEG-060, and the TaskManager reaper, R-8, are unrelated and remain.)
> **Re-revised 2026-08-30:** all "worker" language removed — an agent runs its
> own internal loop; there is no pseudo-agent and no client queue at all.

## Goal
Define the mini-manager (`submit`/`status` backed by boards) and how root-task
results are delivered to the client.

## Scope
- **In scope:** `submit`, `status`, root result delivery to `results:{task_id}`,
  task ownership tagging.
- **Out of scope:** REST surface (LEG-025), security/auth (LEG-027/LEG-017).

## Contract & design
- Submission: `submit(client_id, agent, payload)` → creates task with a
  root FlowToken (`root=True`, `ultimate_return_agent_id = client:{task_id}`),
  polls step 1 into the starting agent's queue, tags the `tasks` entry with
  owner `client_id`, returns `task_id`.
- Root delivery: when the root task finishes, the last agent writes the result
  to `results:{task_id}` (the root result board) — there is **no**
  `client:{task_id}` queue. The client reads it back via `status`.
- Ownership: `status`/results only readable by the owning client (LEG-017).

## Interface
- `submit(client_id, agent, payload) -> task_id`; `status(task_id, client_id)`.

## Acceptance criteria
From `docs/PLAN.md` (LEG-014), verbatim:
- Mini-manager accepts a `submit` request, tags the task with the owner, and
  delivers the root result to `results:{task_id}`; the submitted task stays
  visible (pending) until the root result arrives.

## Tests
- Contract tests (red first): submit, root delivery, ownership denial.

## Validation case
- Root flow via the E2E example (LEG-026).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.