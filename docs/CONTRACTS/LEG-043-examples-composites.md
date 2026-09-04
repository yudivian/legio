# LEG-043 — Composite examples: extract_and_summarize (single branch), distribute_summary (multi-branch)

- **Status:** DRAFT (rewritten to the unified `type: composite` model)
- **Rasante:** R-4
- **GitHub issue:** #26
- **Source:** `docs/PLAN.md` (LEG-043)
- **Depends on:** LEG-040, LEG-042, LEG-021

## Goal

Two in-repo, domain-free composite examples that prove the R-4 engine in
green: a single-branch composite (sequence behavior) and a multi-branch
composite (parallel behavior). Both run on the **same unified composite
runner** — no separate classes.

## Scope

- **In scope:** in-repo example patterns + end-to-end composite tests.
- **Out of scope:** resilient failure policies, pools.

## Contract & design

- In-repo examples (no consumer material):
  - `extract_and_summarize`: a composite with **one branch** containing two
    steps `[linguistic → tool]` (fake lingo); exercises the single-branch
    code path (sequence behavior).
  - `distribute_summary`: a composite with **two branches**, each a linguistic
    step (fake lingo); exercises the multi-branch code path (parallel
    behavior) — fan-out, gather, build `output_as`.
- Both run on real beaver; correct scoping, ordering, payload building (§12.1
  construction + re-keying) and root delivery.
- Both are `type: composite` + `branches`; neither carries `kind: sequence` nor
  `kind: parallel` — those do not exist.

## Interface

- Via LEG-025/LEG-027 REST as a client would.

## Acceptance criteria

From `docs/PLAN.md` (LEG-043), verbatim:
- Both are green tests exercising real composite flows.
- Examples behave identically under the unified model (single-branch and
  multi-branch cases use the same runner).

## Tests

- Both examples as green end-to-end tests.

## Validation case

- `distribute_summary` (multi-branch) and `extract_and_summarize`
  (single-branch).

## Definition of done

- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.
