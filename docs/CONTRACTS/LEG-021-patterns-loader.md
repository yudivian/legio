# LEG-021 — Patterns loader

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-2
- **GitHub issue:** #13
- **Source:** `docs/PLAN.md` (LEG-021)
- **Depends on:** LEG-010 (schema v1), LEG-070 (invalidation)

## Goal
Load and validate patterns from YAML v1 into typed in-memory models, with
dependency resolution between patterns.

## Scope
- **In scope:** parse, validate, resolve agent references between patterns,
  expose them immutably.
- **Out of scope:** compilation of `output_schema` (LEG-072), startup
  gates (LEG-071), tool registry wiring (LEG-022).

## Contract & design
- Patterns are loaded from a directory (or embedded dicts) into pydantic v1
  models per LEG-010.
- Agent references (`input_mapping`/steps) are resolved across the full catalog
  at load; invalid references mark the dependents invalid (delegates to
  LEG-070 semantics).
- Exposed as a read-only catalog consumed by the author.

## Interface
- `load_patterns(directory_or_dicts) -> Catalog`.

## Acceptance criteria
From `docs/PLAN.md` (LEG-021), verbatim:
- The LEG-010 fixtures load and validate; a pattern referencing a missing agent
  is reported (not silently accepted).

## Tests
- Fixture suite from LEG-010 in green; missing-agent case in red→fixed.

## Validation case
- Example patterns from `docs/VALIDATIONS/single-node-model.md`.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.