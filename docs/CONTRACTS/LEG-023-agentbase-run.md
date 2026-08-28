# LEG-023 — AgentBase.run()

- **Status:** APPROVED — implementation green (maintainer-led resolution: this
  spec's acceptance criteria define the issue; PLAN.md replication/lease text is
  deferred to LEG-025 worker)
- **Rasante:** R-2
- **GitHub issue:** #15
- **Source:** `docs/PLAN.md` (LEG-023)
- **Depends on:** LEG-011, LEG-014

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