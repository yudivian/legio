# LEG-010 — Patterns YAML schema (v1)

- **Status:** CLOSED (implementation green, maintainer approved, issue closed)
- **Rasante:** R-1 (contract)
- **GitHub issue:** #4
- **Source:** `docs/PLAN.md` (LEG-010)
- **Depends on:** H1–H4 findings in `docs/VALIDATIONS/single-node-model.md`

## Goal
Define the v1 YAML schema for patterns — the only place where domain knowledge
lives — covering atomic (tool/linguistic) and composite (sequence/parallel)
kinds, stages, `input_mapping`/`output_as`, and the `main` flag.

## Scope
- **In scope:** schema + semantics for kinds, inline stages (H1), dotted
  template paths + system variables (H2), merge semantics (H3), schema
  compilation requirements (H4), cascade-invalidation rules delegated to
  LEG-070.
- **Out of scope:** the loader (LEG-021), compilation (LEG-072).

## Contract & design
- **H1 — Inline stages:** parallel inline → auto-named agent (own queue +
  join); linguistic inline → self-executed by the owning composite (no
  intermediate queue).
- **H2 — Dotted template paths + system vars:** prompts reference
  composite-scoped board entries (`input.payload`, `substep.data`, ...) and
  system variables such as `{current_date}`; the templating engine resolves
  dotted paths (implemented later, enforced by this schema).
- **H3 — Merge semantics:** fan-in merge = flat union of child outputs; rename
  via `output_as` on collision; sequences accumulate flat.
- **H4 — Schema compilation:** `output_schema` supports unions, arrays, nested
  objects, recursion → compiled to pydantic (LEG-072).
- Same schema for `main` and capabilities: `main` = starting agents.

## Interface
- YAML shape: `kind: main|atomic|composite`, atomic `tool`/`linguistic`,
  composite `sequence`/`parallel`, `input_mapping`, `output_as`,
  `output_schema`, optional `main: true`.

## Acceptance criteria
From `docs/PLAN.md` (LEG-010), verbatim:
- A fixture translating two representative composite patterns into schema-valid
  YAML v1 loads and validates; a prompt with `{input.payload}`, `{substep.data}`,
  `{current_date}` fills from the scoped board.

## Tests
- Contract tests (red first): YAML-v1 fixtures (two composites), dotted-path
  template resolution, system variables, schema-validity matrix.

## Validation case
- The two in-repo example composites from `docs/VALIDATIONS/single-node-model.md`
  as conformance fixtures.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.