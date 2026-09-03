# LEG-023 — AgentBase.run()

- **Status:** APPROVED — implementation green (maintainer-led resolution: this
  spec's acceptance criteria define the issue)
- **Rasante:** R-2
- **GitHub issue:** #15
- **Source:** `docs/PLAN.md` (LEG-023)
- **Depends on:** LEG-011, LEG-014

## Goal
The generalized per-step runner unifying all atomic agents and composites into
a single loop: deliver that step's message, run the step's job, then decide
where to deposit the result.

## Scope
- **In scope:** the `run()` loop, message-to-step dispatch, result routing,
  the `monitor` observability hook, in-run task tracking.
- **Out of scope:** the actual steps (linguistic, tool, composite) — they plug
  in.

## Contract & design
- `run()` is the agent's own internal loop (an agent is not a task and not a
  worker): it polls the class's queue until idle, bounded by `max_steps` so a
  misbehaving step can never starve the loop.
- Each dispatch pops a message from the class's native beaver queue
  (destructively — **no lease, no retry and no re-queue**; an item is popped
  once and routed, AGENTS.md rules 8/9), executes the step's job
  (**L2AΛ MPS** or per-agent equivalent) via a subclass `_handle`, and deposits
  the result — mirroring Deliver's semantics at unit level.
- Each agent (atomic/composite/root) is a uniform `run()` unit; composite
  addresses L2A via its own dual queue (fan-in).
- Result routing: one more step → stage $K{+}1$ as `ExecutionRequestMessage`;
  finish → `ExecutionResultMessage` to parent or client (finality by position).
- Failures are never silent: a step that raises is routed to an `error` result,
  never re-queued.

## Interface
- `AgentBase.run()` — the uniform loop every agent implements.

## Acceptance criteria
From `docs/PLAN.md` (LEG-023), verbatim:
- A single-step task completes with result in place; two-step task runs both
  steps and returns; a broken tool marks the task failed without crash; the
  `monitor` hook fires on the right events.

## Tests
- Contract tests (red first): single/two-step, failure path, hook firing.

## Validation case
- Foundation of every composite (`extract_and_summarize` seeds).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.