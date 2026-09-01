# LEG-042 — Fan-in: gathering queue by (parallel, task) identity, canonical hole resolution

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-4
- **GitHub issue:** #25
- **Source:** `docs/PLAN.md` (LEG-042)
- **Depends on:** LEG-023, `docs/AGENT_LIFECYCLE.md` §12

## Goal

The parallel fan-in (per-class **gathering queue**, bookkeeping
`state:parallel:<class>`, AGENT_LIFECYCLE §12.4) with canonical hole
resolution: exactly-once join, slot-stable even before children arrive, and
correct behavior when a child is bugged — for parallel; sequence is
forward-only and has no fan-in (§12.3).

## Scope

- **In scope:** gathering structure, hole semantics and resolution (departure
  gate), join stability pre-arrival, gate follow-on conformation.
- **Out of scope:** agent-level behavior (sequence/parallel agents on top).

## Contract & design

- The payload travels **in the messages** (AGENT_LIFECYCLE §12.1);
  the gathering queue of the parallel class holds the children's
  `ExecutionResultMessage` returns from which the parallel **builds its
  payload** — there is **no** out-of-message accumulator and no out-gate board.
- Per H3: join is executed when the parallel's bookkeeping (locked,
  `state:parallel:<class>`, keyed per task) confirms the hole resolved &
  departure gate settled; tokens of a step wait at the canonical hole until
  its predecessor resolves.
- Dedupe per **(parallel, child task id)** — enforced by bookkeeping keyed by
  the per-branch minted child task id (LEG-041) and by slot identity: two
  same-named branches are two distinct holes; no inter-merge by agent name.
- **Join→advance ordering (crash-safe).** The advance deposit happens **in the
  same lock section** as the join-row update, *before* the join row is deleted
  (advance-then-delete): a crash that lands between the two steps leaves a
  stale join row, which a periodic sweep reclaims (GC). Deleting first would
  open a window where a crash orphans the parent route.

## Interface

- Gathering-queue composition API; step join resolution API.

## Acceptance criteria

From `docs/PLAN.md` (LEG-042), verbatim:
- [per LEG-052] same-named parallel branches at different positions do not
  merge; regression tests cover the earlier agent-name bug.

## Tests

- Contract tests (red first): hole canonical resolution, stability-pre-arrival,
  agent-name bug regression.

## Validation case

- Composite examples (`extract_and_summarize`, `distribute_summary`).

## Definition of done

- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.