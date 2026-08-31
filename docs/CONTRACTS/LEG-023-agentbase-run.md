# LEG-023 — AgentBase.run()

- **Status:** APPROVED — implementation green (maintainer-led resolution: this
  spec's acceptance criteria define the issue)
- **Rasante:** R-2
- **GitHub issue:** #15
- **Source:** `docs/PLAN.md` (LEG-023)
- **Depends on:** LEG-011, LEG-014

> **Revised 2026-08-30:** the `run(max_steps=100)` tick is the agent's **own
> internal loop** (an agent is not a task and not a worker): it polls the
> class's queue until idle, bounded by `max_steps` so a misbehaving step can
> never starve the loop. Each dispatch is stateless and carries no lease of its
> own — the items hold the leases (LEG-060).

## Goal
The generalized per-step runner unifying all atomic agents and composites into
a single loop: deliver that step's message, run the step's job with retry /
monitoring hooks, then decide where to deposit the result.

## Scope
- **In scope:** the `run()` loop, message-to-step dispatch, result routing,
  hooks, in-run task tracking.
- **Out of scope:** the actual steps (linguistic, tool, composite) — they plug
  in; retries policies (R-6).

## Contract & design
- `run()` leases data from the queue, identifies stage $K$, executes the step's
  job (**L2AΛ MPS** or per-agent equivalent) with hooks (`retry_guard`, lease
  refresh, monitor), reads `next from desk`-derived framing card, and deposits
  the result — mirroring Deliver's semantics at unit level.
- Each agent (atomic/composite/root) is a uniform `run()` unit; composite
  odresses L2A via its own dual queue (fan-in).
- Result routing: one more step → stage $K{+}1$ as `ExecutionRequestMessage`;
  finish → `ExecutionResultMessage` to parent or client (finality by position).

## Interface
- `AgentBase.run()` — the uniform loop every agent implements.

## Acceptance criteria
From `docs/PLAN.md` (LEG-023), verbatim:
- A single-step task completes with result in place; two-step task runs both
  steps and returns; a broken tool marks the task failed without crash; hooks
  (retry_guard, monitor) fire on the right events.

## Tests
- Contract tests (red first): single/two-step, failure path, hook firing.

## Validation case
- Foundation of every composite (`extract_and_summarize` seeds).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.