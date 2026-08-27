# LEG-014 — Mini-manager & client pseudo-agent contract (v1)

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-1 (contract)
- **GitHub issue:** #8
- **Source:** `docs/PLAN.md` (LEG-014)
- **Depends on:** ARCHITECTURE §3, LEG-011, LEG-015

## Goal
Define the client pseudo-agent `client:{task_id}` (the submission entry point),
its lifecycle, and how root-task results are delivered to the client on the
internal queue.

## Scope
- **In scope:** `client:{task_id}` internal queue, root delivery, termination,
  reaper of stuck clients, task ownership tagging.
- **Out of scope:** REST surface (LEG-025), security/auth (LEG-027/LEG-017).

## Contract & design
- Submission: `submit(client_id, agent, payload)` → creates task with a
  root FlowToken (root=True, `ultimate_return_agent_id = client:{task_id}`),
  polls step 1 into the target (or local) queue, tags `tasks` entry with owner
  `client_id`, returns `task_id`.
- The `client:{task_id}` agent is *itself* an internal queue for root results.
- Termination: when root task finishes, a `client_termination_request` is
  deposited to `client:{task_id}`; the worker handling it drains the queue and
  marks the task `by`: `client_terminated`.
- A reaper cancels `client:{task_id}` agents that never get their termination
  (deadlock/stuck guard).
- Ownership: `status`/results only readable by the owning client (LEG-017).

## Interface
- `submit(client_id, agent, payload) -> task_id`; `status(task_id, client_id)`.

## Acceptance criteria
From `docs/PLAN.md` (LEG-014), verbatim:
- Mini-manager accepts a `submit` request, tags the task with the owner, and
  delivers the root result to `client:{task_id}` internally; reaper + clean
  termination covered by tests.

## Tests
- Contract tests (red first): submit, delivery-to-client, termination, reaper.

## Validation case
- Root flow via the E2E example (LEG-026).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.