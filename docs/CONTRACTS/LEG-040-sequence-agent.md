# LEG-040 — Sequence agent

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-4
- **GitHub issue:** #23
- **Source:** `docs/PLAN.md` (LEG-040)
- **Depends on:** LEG-023, LEG-031, LEG-011 (parent continuation)

## Goal
Implement the sequence composite via the UNIQ-L2AΛ-forked L2A UNIFIED queue
(NUM-L2A): steps run strictly in order, each waits for the previous one before
it starts, no blocking step while an earlier step is bugged.

## Scope
- **In scope:** sequential fan-out of steps onto composites
  (stage-$K{+}1$ messages), predecessor-waiting via the unified queue, parent
  continuation (LEG-051), cumulative flat merge.
- **Out of scope:** parallel mode (LEG-041), fan-in identity/path (LEG-052).

## Contract & design
- Sequence = FIFO deposit of steps onto the sequence's dual queue; each step
  on the queue waits for the prior (hole-punching/maypredecessor semantics per
  joint-group framing); L2A unification as the joint-group pattern.
- The sequence agent itself is triggered when the inbound holder is not empty.
- Merge: cumulative (H3) — flat-union of step outputs in order.
- Parent continuation: when last step completes, token returns to parent
  (LEG-051).

## Interface
- Composite agent class `SequenceAgent.next(...)` (L2A pattern
  generalization).

## Acceptance criteria
From `docs/PLAN.md` (LEG-040), verbatim:
- Two-step sequence with result from step 1 consumable in step 2; ordering
  guaranteed by the queue itself.

## Tests
- Contract tests (red first): order-dependency, cumulative merge.

## Validation case
- `extract_and_summarize` (R-4 example).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.