# LEG-043 — Composite examples: extract_and_summarize (sequence), distribute_summary (parallel)

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-4
- **GitHub issue:** #26
- **Source:** `docs/PLAN.md` (LEG-043)
- **Depends on:** LEG-040, LEG-041, LEG-042, LEG-021

## Goal
Two in-repo, domain-free composite examples that prove the R-4 engine in
green: a sequence (steps chained on one path) and a parallel (fan-out/join).

## Scope
- **In scope:** in-repo example patterns + end-to-end composite tests.
- **Out of scope:** resilient parallel failure policies.

## Contract & design
- In-repo examples (no consumer material):
  - `extract_and_summarize`: `[linguistic → tool]` sequence (fake lingo).
  - `distribute_summary`: parallel fan-out of `n` branches, join by path.
- Both run on real beaver; correct scoping, ordering, payload building and root delivery.

## Interface
- Via LEG-025/LEG-027 REST as a client would.

## Acceptance criteria
From `docs/PLAN.md` (LEG-043), verbatim:
- Both are green tests exercising real composite flows.

## Tests
- Both examples as green end-to-end tests.

## Validation case
- `distribute_summary` (parallel) and `extract_and_summarize` (sequence).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.