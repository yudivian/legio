# LEG-040 — Sequence agent

- **Status:** APPROVED (maintainer, 2026-09-01 — R-4 stream directed)
- **Rasante:** R-4
- **GitHub issue:** #23
- **Source:** `docs/PLAN.md` (LEG-040)
- **Depends on:** LEG-023, LEG-031, LEG-011 (parent continuation),
  `docs/AGENT_LIFECYCLE.md` §12.3/§12.4

## Goal

Implement the **sequence** composite — one of the **two** composite agent
classes that `type: composite` forks into: `SequenceAgent` (`kind: sequence`,
this issue) and `ParallelAgent` (`kind: parallel`, LEG-041). A sequence is a
**forward-only** chain over the class inbox: each step deposits the next into
the following class's queue and the last processor closes the level
(AGENT_LIFECYCLE §12.3). No gathering queue.

**Ordering is by chain deposit, never by locking.** No agent waits on another
and nothing is blocked: a step runs as soon as its item arrives in its queue.
Step 2 simply cannot start until step 1's
result lands in step 2's queue — the order is encoded in the token's
`level_route`/`current_index`, not enforced by any lock. This is the polling,
decoupled philosophy (AGENTS.md rule 8).

## Scope

- **In scope:** sequential deposit of steps as routes over the next classes'
  inboxes, parent continuation (LEG-051), building the payload across steps.
  Covers the `kind: sequence` composite class only.
- **Out of scope:** the parallel composite class `ParallelAgent` (LEG-041),
  fan-in identity/path (LEG-052).

## Contract & design

- There are **two** composite agent classes (Schemas 1/4.11), one per
  composite `kind`: `SequenceAgent` for `kind: sequence` and `ParallelAgent`
  for `kind: parallel`. This issue specifies and implements
  `SequenceAgent` only; the parallel class is LEG-041.
- Sequence = forward deposit of each step as an `ExecutionRequestMessage` to
  the next class's inbox; each step's start follows the previous one's result
  (order encoded in the token's `level_route`/`current_index`; pure chain
  deposit, no locking or waiting).
- Advance is the single Schema 2 rule (AGENT_LIFECYCLE §12.4): while
  `current_index < len(level_route)-1`, deposit to `level_route[current_index+1]`
  (by position); at end-of-level (`current_index == len-1`) deliver to
  `end_of_level_queue` — the creator's gathering queue if `level > 1` (branch
  close) or the submit's final-result queue if `level == 1` (flow end). Nothing
  loops back through the sequence.
- Payload build across steps (AGENT_LIFECYCLE §12.1) — each step receives the
  incoming payload re-keyed under its `input_as`, applies its outcome and
  **builds a NEW payload via `legio.flow.build_payload` under its `output_as`**
  (construction, NOT accumulation — no "keeps every earlier step's keys"). When
  the step advances, the base re-keys the produced value under the next step's
  `input_as`; the last step delivers its `output_as` payload to the level closer.
  There is no out-of-message accumulator; the built dict is exactly what the
  next request carries as `payload` (or what the flow end delivers to the
  final-result queue).
- Parent continuation: at branch close the result returns via `end_of_level_queue`
  to the launching parallel's gathering queue (LEG-051).

## Interface

- Composite agent class `SequenceAgent` implementing the forward chain over
  the inbox for the **sequence** composite `kind`. The parallel composite
  class is `ParallelAgent` (LEG-041) — a distinct class, not a variant of
  `SequenceAgent`.

## Acceptance criteria

From `docs/PLAN.md` (LEG-040), verbatim:
- Two-step sequence with result from step 1 consumable in step 2; ordering
  guaranteed by the message/token order.

## Tests

- Contract tests (red first): order-dependency, payload build across steps.

## Validation case

- `extract_and_summarize` (R-4 example).

## Definition of done

- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.