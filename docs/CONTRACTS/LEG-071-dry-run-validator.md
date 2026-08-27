# LEG-071 — Dry-run validator + strict fail-fast startup

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-7
- **GitHub issue:** #38
- **Source:** `docs/PLAN.md` (LEG-071)
- **Depends on:** LEG-021

## Goal
Operational safety: `legio validate --dry-run` reports every invalid pattern
and exits non-zero; startup refuses to serve any catalog containing an invalid
pattern.

## Scope
- **In scope:** the validate CLI command, startup gate.
- **Out of scope:** package CLI bootstrapping details beyond validate
  (LEG-081).

## Contract & design
- `validate --dry-run` = load + correctness pass (deps exist, schema-valid,
  no cycle) with per-pattern and exit-code reporting.
- Startup: if any pattern invalid → refuse to serve (before listening),
  motivated by LEG-070 invisibility (never serve silently-broken).

## Interface
- `legio validate --dry-run [--dir DIR]` → exit != 0 on any invalid.

## Acceptance criteria
From `docs/PLAN.md` (LEG-071), verbatim:
- `legio validate --dry-run` reports every invalid pattern and exits non-zero;
  startup refuses to serve a catalog with any invalid pattern.

## Tests
- CLI contract tests (red first): invalid fixture → non-zero, startup refusal.

## Validation case
- Injecting a broken pattern fixture.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.