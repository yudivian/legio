# LEG-031 — Structured output / template values

- **Status:** APPROVED (maintainer, 2026-08-28) — contract tests written first, implementation to follow
- **Rasante:** R-3
- **GitHub issue:** #21
- **Source:** `docs/PLAN.md` (LEG-031)
- **Depends on:** LEG-010 (H2), LEG-030

## Goal
Enforce structured output transmission: atomic agents return a
declared/validated output shape, and templates (dotted paths + system vars)
resolve against a single validated record dot-opened for the prompt.

## Scope
- **In scope:** the standard "output" shape (single pydantic record per step),
  template resolution, system variables.
- **Out of scope:** the compile of declared `output_schema` (LEG-072 uses
  these shapes).

## Contract & design
- Every atomic output is one validated pydantic record (validated at the
  edges per LEG-013/022 or lingo response).
- Dot-opened record is templated into prompts; system vars (`{current_date}`,
  etc.) always available.
- Undefined path → clear template error (never silent).

## Interface
- `resolve_template(template, board_entry) -> str`; output record contract.

## Acceptance criteria
From `docs/PLAN.md` (LEG-031), verbatim:
- A structured value flows through a step and into a later template as a
  dot-opened record; undefined path → explicit error.

## Tests
- Contract tests (red first): structured flow, dot resolution, error path.

## Validation case
- In-repo composite example consuming an earlier step's structured output.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.