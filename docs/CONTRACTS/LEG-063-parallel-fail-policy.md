# LEG-063 — Parallel partial/fail policy (configurable per pattern)

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-6
- **GitHub issue:** #34
- **Source:** `docs/PLAN.md` (LEG-063)
- **Depends on:** LEG-041

## Goal
Configurable failure policy for parallel fan-outs declared in the pattern:
`fail_fast` (stop + report) vs tolerant (partial success with per-child error
entries).

## Scope
- **In scope:** the per-pattern policy field, both modes, result shape.
- **Out of scope:** retry interaction (LEG-061 covers attempts).

## Contract & design
- Pattern declares `fail_policy: fail_fast | tolerate_partial` (default
  documented).
- `fail_fast`: first child failure aborts fan-out and reports.
- `tolerate_partial`: join continues; result = partial success object with
  per-child error entries and both yielded data.

## Interface
- Pattern `fail_policy` field; parallel join honoring it.

## Acceptance criteria
From `docs/PLAN.md` (LEG-063), verbatim:
- Pattern with `fail_fast` stops fan-out and reports; with tolerant policy a
  failed child yields a partial success result with per-child error entries.

## Tests
- Contract tests (red first): both policies.

## Validation case
- `distribute_summary` example with both policies.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.