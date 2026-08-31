# LEG-040 — Sequence agent

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-4
- **GitHub issue:** #23
- **Source:** `docs/PLAN.md` (LEG-040)
- **Depends on:** LEG-023, LEG-031, LEG-011 (parent continuation),
  `docs/AGENT_LIFECYCLE.md` §12.3/§12.4

## Goal

Implement the sequence composite: a **forward-only** chain over the class
inbox — steps run strictly in order, each waits for the previous one before it
starts; nothing returns to the sequence; the last processor deposits into the
next class's queue (AGENT_LIFECYCLE §12.3). No gathering queue.

## Scope

- **In scope:** sequential deposit of steps as routes over the next classes'
  inboxes, parent continuation (LEG-051), cumulative flat merge.
- **Out of scope:** parallel mode (LEG-041), fan-in identity/path (LEG-052).

## Contract & design

- Sequence = forward deposit of each step as an `ExecutionRequestMessage` to
  the next class's inbox; each step's start follows the previous one's result
  (order encoded in the token's `route_pattern_names`/`current_index`).
- Advance is the single `_advance_flow` (AGENT_LIFECYCLE §12.4): the last
  step of the route returns to `ultimate_return_agent_id` (or saves the final
  result if there is no return). Nothing loops back through the sequence.
- Merge: cumulative (H3) — each step's output is flat-merged into the carried
  state of the outgoing message (`legio.flow.merge_carried`; `output_as` as the
  `namespace` on collision), so a chain of any length keeps every earlier
  step's keys, in order. There is no out-of-message accumulator; the merged
  dict is exactly what the next request carries as `payload["input"]` (or what
  the root result writes to `results`).
- Parent continuation: when the last step completes, the result returns to
  the parent (LEG-051).

## Interface

- Composite agent class `SequenceAgent` implementing the forward chain over
  the inbox.

## Acceptance criteria

From `docs/PLAN.md` (LEG-040), verbatim:
- Two-step sequence with result from step 1 consumable in step 2; ordering
  guaranteed by the message/token order.

## Tests

- Contract tests (red first): order-dependency, cumulative merge.

## Validation case

- `extract_and_summarize` (R-4 example).

## Definition of done

- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.