# LEG-050 — Root token authoring & root delivery

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-5
- **GitHub issue:** #27
- **Source:** `docs/PLAN.md` (LEG-050)
- **Depends on:** LEG-014, LEG-011

## Goal
Root token authoring (root=True, `ultimate_return_agent_id = client:{task_id}`)
and exactly-once root delivery into `results:{task_id}`.

## Scope
- **In scope:** authoring semantics, delivery into `results:{task_id}`, ack of
  client delivery, no re-delivery.
- **Out of scope:** termination flow (LEG-014 owns it at manager level).

## Contract & design
- On submit: authoring root token as LEG-011; result is written to
  `results:{task_id}`; client delivery ack'ed so it happens exactly once (a
  duplicate/retry cannot double-write — idempotency guard).
- No re-delivery after ack.

## Interface
- Internal authoring/token API + ack handshake.

## Acceptance criteria
From `docs/PLAN.md` (LEG-050), verbatim:
- Root task result lands in `results:{task_id}` exactly once and is readable
  via status; no re-delivery after ack.

## Tests
- Contract tests (red first): exactly-once, ack no-redelivery.

## Validation case
- E2E `transform` example asserting `results:{task_id}`.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.