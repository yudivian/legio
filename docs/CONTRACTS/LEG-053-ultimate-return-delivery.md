# LEG-053 — ultimate_return delivery semantics

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-5
- **GitHub issue:** #30
- **Source:** `docs/PLAN.md` (LEG-053)
- **Depends on:** LEG-050, LEG-051

## Goal
Define and enforce the distinction: head (internal) vs ultimate (client)
delivery of the final result token.

## Scope
- **In scope:** internal delivery for head tasks, client-bound delivery for
  root tasks (LEG-014), and the boundary between them.
- **Out of scope:** transport (REST/federation).

## Contract & design
- `ultimate_return_agent_id` naming: internal (parent PID agent) → deliver to
  parent queue; `client:{task_id}` → deliver to client pseudo-agent + write
  `results:{task_id}` (LEG-050).
- The composite engine chooses delivery precisely from LEG-011 finality.

## Interface
- Delivery-point decision internal to `run()`.

## Acceptance criteria
From `docs/PLAN.md` (LEG-053), verbatim:
- Head tasks deliver internally, root tasks to the client; covered by contract
  tests.

## Tests
- Contract tests (red first): head vs root delivery.

## Validation case
- The R-4 composite examples + root E2E.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.