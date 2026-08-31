# LEG-100 — Docs & examples hardening; glossary; consumer guide

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-10
- **GitHub issue:** #48
- **Source:** `docs/PLAN.md` (LEG-100)
- **Depends on:** R-0..R-9 outputs

## Goal
Hardening pass: executable consumer guide (adding tools + patterns to a node),
real glossary, and every in-repo example a green test (no bitrot).

## Scope
- **In scope:** consumer guide, glossary, examples-as-tests hardening.
- **Out of scope:** semantic versioning/release (LEG-101).

## Contract & design
- Consumer guide is executable top-to-bottom: register a tool → write a
  pattern → run the agent loop (or `legio server` bootstrap) → submit → read
  status (each step a runnable command).
- Glossary = LEG-016 identifiers + architecture terms, single canonical
  definition each.
- Examples glued to CI: any drift in a documented example breaks the suite.

## Interface
- Documentation artifacts (docs/); executable snippets.

## Acceptance criteria
From `docs/PLAN.md` (LEG-100), verbatim:
- Consumer guide (adding tools + patterns to a node) is executable
  top-to-bottom; examples are all green tests.

## Tests
- The documented snippets run in CI.

## Validation case
- The consumer guide walkthrough itself.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.