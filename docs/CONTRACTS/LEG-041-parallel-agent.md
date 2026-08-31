# LEG-041 — Parallel agent

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-4
- **GitHub issue:** #24
- **Source:** `docs/PLAN.md` (LEG-041)
- **Depends on:** LEG-023, LEG-031, LEG-051,
  `docs/AGENT_LIFECYCLE.md` §12.3/§12.4

## Goal

Implement the parallel composite: concurrent fan-out over the children's class
inboxes, results gathered at the parallel class's **gathering queue**, joined
per (parallel, task) via the per-class bookkeeping
(`state:parallel:<class>`, AGENT_LIFECYCLE §12.4).

## Scope

- **In scope:** concurrent deposit of child tasks across class inboxes, fani-in
  join per (parallel, task), merge on all-complete.
- **Out of scope:** parallel failure policy (LEG-063), pools (LEG-080).

## Contract & design

- The parallel class has **two queues in the model**: its inbox and its
  **gathering queue** for fan-in returns (§12.3); collapsing them into one
  physical queue by message-type dispatch is an implementation choice.
  The accumulated state travels in the messages (§12.1); the gathering
  bookkeeping (`state:parallel:<class>`, locked, keyed per task) is the join
  state — not a frame/board accumulator.
- Fan-in identity: dedupe per **(parallel, child task id)**; each branch is one
  child task (LEG-052) — "two B-step tasks at different positions are distinct
  tasks". The fan-out **mints a distinct child task id (uuid) per branch**; the
  child id *is* the slot identity, and the parallel's bookkeeping maps
  child id → (parent task, slot). The join gathers exactly the step's children;
  join waits (in the bookkeeping, not by polling) until all present.
- Inline steps: tool → auto-named sub-agent class queue; linguistic → self-run
  by the gatherer (H1).
- Merge flat-union with `output_as` (H3) into the message-carried state, via
  `legio.flow.merge_carried`; fail policy hooks LEG-063.
- Nested composites need no token change: a composite is an ordinary class on
  the route — it is invoked like any capability agent through its inbox and
  returns via `ultimate_return_agent_id` (so a composite may appear as a branch
  of a parallel or a step of a sequence; LEG-051).

## Interface

- `ParallelAgent` composite class implementing the fan-out/in over inbox +
  gathering.

## Acceptance criteria

From `docs/PLAN.md` (LEG-041), verbatim:
- Two parallel branches both executes and their outputs merge on join;
  release parallelism (both late-started together) in tests.

## Tests

- Contract tests (red first): fan-out, join on all-complete, parallelism.

## Validation case

- `distribute_summary` (R-4 example).

## Definition of done

- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.