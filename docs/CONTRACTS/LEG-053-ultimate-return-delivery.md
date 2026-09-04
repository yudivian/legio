# LEG-053 — Final-result delivery semantics (Schema 2)

- **Status:** DRAFT (rewritten to the unified `type: composite` model)
- **Rasante:** R-5
- **GitHub issue:** #30
- **Source:** `docs/PLAN.md` (LEG-053); `docs/AGENT_LIFECYCLE.md` §4.11 Schema 2
- **Depends on:** LEG-050, LEG-051

## Goal

Define and enforce the delivery of the final result token: at **flow end**
(end-of-sequence AND `level == 1`), the result is delivered to
`end_of_level_queue` — the **final-result queue** assigned by the submit. There
is no `results` store and no `client:{task_id}` queue.

## Scope

- **In scope:** internal delivery (branch close to a creator's gathering queue)
  vs **flow-end** delivery (to the final-result queue) for root tasks, and the
  boundary between them.
- **Out of scope:** transport (REST/federation).

## Contract & design

- **Flow end** = end-of-sequence (`current_index == len(level_route)-1`) AND
  `level == 1` (generalized rule): deliver the final result to
  `end_of_level_queue`, which the **submit** set to the **final-result queue**.
  Nothing more is routed.
- **End-of-level with `level > 1`** = branch close: deliver an
  `ExecutionResultMessage` to `end_of_level_queue`, which the launching composite
  set to its **gathering queue**. The composite on fan-in completion decrements
  `level` (−1) and resumes its level.
- The agent never decides which queue: `end_of_level_queue` is always assigned by
  the flow creator (the submit or a composite).
- The composite engine chooses delivery precisely from the Schema 2 position +
  `level` finality (LEG-011).

## Interface

- Delivery-point decision internal to `run()`.

## Acceptance criteria

- A step in the last position of its level at `level == 1` delivers to the
  final-result queue; a branch in the last position at `level > 1` delivers to
  its creator's gathering queue; covered by contract tests.

## Tests

- Contract tests (red first): flow-end vs branch-close delivery.

## Validation case

- The S4 simulation flows (runs 1–4) — incl. composite-as-root.

## Definition of done

- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.
