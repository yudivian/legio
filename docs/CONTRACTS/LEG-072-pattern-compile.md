# LEG-072 — Pattern compile: `output_schema` → pydantic models (Schema 1)

- **Status:** DRAFT (Schema 1 alignment; awaiting maintainer approval)
- **Rasante:** R-7
- **GitHub issue:** #42
- **Source:** `docs/PLAN.md` (LEG-072)
- **Depends on:** LEG-010 (S1 — the `output_schema` mini-grammar)

## Goal
Compile each agent's declared `output_schema` (Schema 1 mandatory output
contract) into validating pydantic models — supporting unions, arrays, nested
objects and recursive schemas — so outputs are validated at the boundary.

## Scope
- **In scope:** schema → pydantic compilation, boundary validation on output.
- **Out of scope:** tool/linguistic runtime (they consume compiled models).

## Contract & design
- The `output_schema` mini-grammar (used identically by Schema 1 agents and for
  the tool/linguistic output edges) compiles at load into a pydantic model;
  H4: unions, arrays, nested objects, recursion all supported.
- Every agent declares a mandatory `output_as`/`output_type`/`output_schema`
  (Schema 1); the compiled model validates the produced output at the boundary,
  giving DB-boundary rigor to step outputs (rule 9).

## Interface
- `compile_pattern_schemas(catalog)`; compiled models consumed by edges.

## Acceptance criteria
From `docs/PLAN.md` (LEG-072), verbatim:
- Unions, arrays, nested objects, and recursive schemas compile to validating
  pydantic models (H4); a compiled schema rejects a bad payload at the boundary.

## Tests
- Contract tests (red first): compile matrix + rejection.

## Validation case
- Example composites whose outputs use unions/arrays.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.