# LEG-021 — Patterns loader (Schema 1)

- **Status:** REVISED 2026-09-01 (Schema 1 — one agent spec; supersedes the v1
  CLOSED contract of the same name)
- **Rasante:** R-2
- **GitHub issue:** #13
- **Source:** `docs/PLAN.md` (LEG-021)
- **Depends on:** LEG-010 (S1 schema), LEG-070 (invalidation)

> **Note on implementation state.** The current `legio.patterns` loader is still
> the v1 loader (`kind: main|atomic|composite`, `tool_type`, `tool: bool`,
> `input_mapping`, auto-naming / self-execution / queue-name materialization).
> This document is the **Schema 1 target contract** for the loader migration;
> the v1 code is pending migration, not yet conformant. Nothing here claims the
> v1 code already conforms.

## Goal
Load and validate patterns from YAML **Schema 1** into typed in-memory agent
models (one agent spec: `type` × `kind`, mandatory symmetric contracts, terse
`parameters`), with dependency resolution between patterns and the load-time
validations from LEG-010 (§4.10).

## Scope
- **In scope:** parse, validate (branch-exclusive matrix, mandatory contracts,
  chain-wide dotted-path resolution, contract compatibility, reuse,
  encapsulation/cycles, interior↔contract coherence), resolve agent references
  between patterns, expose them immutably as a catalog.
- **Out of scope:** compilation of `output_schema` (LEG-072), startup gates
  (LEG-071), tool registry wiring (LEG-022), the runtime materialization
  artifacts (queue names, compiled pydantic, derived identities — these belong
  to the executing engine, not the loader).

## Contract & design
- Patterns are loaded from a directory (or embedded dicts) into typed, immutable
  agent models per LEG-010 (Schema 1).
- Validations applied at load (LEG-010 §4.10 / acceptance): branch-exclusive
  structural enforcement; mandatory symmetric entry/output contracts; terse
  `parameters` (tool) with chain-wide dotted-path resolution; linguistic prompt
  variables ↔ `input_schema` (all used, all declared); tool `parameters` ↔
  registered signature (coherence, checked at load where statically possible);
  contract compatibility on composition; reuse via `pattern:`/repetition by
  position; `output_as` uniqueness per scope; composition cycles rejected.
- Agent references are resolved across the full catalog at load; invalid
  references mark the dependents invalid (LEG-070 semantics).
- Exposed as a read-only catalog consumed by the engine.

## Interface
- `load_patterns(directory_or_dicts) -> Catalog`.

## Acceptance criteria
From `docs/PLAN.md` (LEG-021), verbatim:
- The LEG-010 S1 fixtures load and validate; the branch-exclusive and
  mandatory-contract validation matrix is enforced at load; a pattern
  referencing a missing agent is reported (not silently accepted).

## Tests
- Fixture suite from LEG-010 (S1) in green; missing-agent case in red→fixed;
  the branch-exclusive / mandatory-contract / coherence matrices at load.

## Validation case
- Example patterns re-expressed in the S1 shape (two representative composites).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.