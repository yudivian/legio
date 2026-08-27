# LEG-024 — Mini-manager implementation

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-2
- **GitHub issue:** #16
- **Source:** `docs/PLAN.md` (LEG-024)
- **Depends on:** LEG-014 (contract), LEG-011

## Goal
Implement the LEG-014 mini-manager: submit, root delivery to `client:{task_id}`,
termination and the reaper.

## Scope
- **In scope:** `submit`, `status`, internal `client:{task_id}` delivery,
  termination, reaper.
- **Out of scope:** REST (LEG-025), auth (LEG-027).

## Contract & design
- Per LEG-014. `status` enforces ownership (client only sees own tasks).
- Reaper periodic job cancelling `client:{task_id}` agents whose task is
  already in a terminal state / stuck.

## Interface
- `submit(client_id, agent, payload) -> task_id`; `status(task_id, client_id)`.

## Acceptance criteria
From `docs/PLAN.md` (LEG-024), verbatim:
- Contract test from LEG-014 in green against real primitives.

## Tests
- The LEG-014 contract suite (red-first) executed in green on beaver.

## Validation case
- E2E example (LEG-026) submit/status path.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.