# LEG-072 — Pattern compile: output_schema → pydantic models

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-7
- **GitHub issue:** #42
- **Source:** `docs/PLAN.md` (LEG-072)
- **Depends on:** LEG-010 (H4)

## Goal
Compile each pattern's declared `output_schema` into validating pydantic
models — supporting unions, arrays, nested objects and recursive schemas.

## Scope
- **In scope:** schema → pydantic compilation, boundary validation on output.
- **Out of scope:** tool/linguistic runtime (they consume compiled models).

## Contract & design
- `output_schema` (JSON-ish/YAML form) compiles at load into a pydantic model;
  H4: unions, arrays, nested objects, recursion all supported.
- Compiled model validates at boundaries (same name for atomic and composite
  outputs), giving DB-boundary rigor to step outputs.

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