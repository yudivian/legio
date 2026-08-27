# LEG-030 — Linguistic agent via lingo

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-3
- **GitHub issue:** #20
- **Source:** `docs/PLAN.md` (LEG-030)
- **Depends on:** LEG-023, lingo (approved dependency)

## Goal
Implement the linguistic agent: a step that calls an LLM (via `lingo`) with a
templated prompt and returns structured output, without introducing its own
queue (H1: linguistic inline = self-executed by the owning composite).

## Scope
- **In scope:** prompt templating (H2), lingo call, output handling,
  self-execution as inline step in composites.
- **Out of scope:** `output_schema` compilation (LEG-072), retries (R-6),
  structuring output response post-processing beyond v1 call contract.

## Contract & design
- A linguistic step declares `linguistic: {model, prompt}` (or the step is a
  sub-flow); prompt templated with dotted paths + system vars per LEG-010 H2.
- Called via lingo; result written to the step's `out` frame for the composite
  merge (H3).
- Inline/nested linguistic steps self-execute inside the owning composite (no
  intermediate queue), per H1.

## Interface
- `LinguisticAgent(lingo_client, board, locks)`; step config shape.

## Acceptance criteria
From `docs/PLAN.md` (LEG-030), verbatim:
- A linguistic step run within a composite returns structured output whose
  template was resolved from the scoped board; tests use a fake lingo.

## Tests
- Contract tests (red first) with a fake lingo: templating, structured result,
  inline self-execution.

## Validation case
- In-repo linguistic step (fake lingo) inside an example composite.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.