# LEG-003 — Governance docs reviewed & frozen

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-0
- **GitHub issue:** #3
- **Source:** `docs/PLAN.md` (LEG-003)
- **Depends on:** none

## Goal
A final consistency pass over the governance documents (AGENTS, CONTRIBUTING,
ARCHITECTURE, PLAN, DEPENDENCIES, spec template) so they form a coherent,
self-contained set before contracts are written.

## Scope
- **In scope:** cross-referencing, issue-number consistency, approval record.
- **Out of scope:** writing contracts (R-1).

## Contract & design
- Docs are the single source of truth for the process; no duplication of
  normative rules across files.
- No consumer material or names inside the repo (AGENTS.md rule 7).

## Interface
- None (documentation).

## Acceptance criteria
From `docs/PLAN.md` (LEG-003), verbatim:
- Every doc cross-references only existing files; all issue numbers mentioned
  in docs exist in this PLAN; an approval is recorded in the journal.

## Tests
- Scripted grep/link checks (dangling references, LEG numbers).

## Validation case
- None (documentation rasante).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.