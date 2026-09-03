# LEG-030 — Linguistic agent via lingo (Schema 1)

- **Status:** APPROVED (maintainer, 2026-08-28) — contract tests written first,
  implementation to follow
- **Rasante:** R-3
- **GitHub issue:** #20
- **Source:** `docs/PLAN.md` (LEG-030)
- **Depends on:** LEG-023, LEG-010 (S1), lingo (approved dependency)

## Goal
Implement the linguistic agent: a `kind: linguistic` step that calls an LLM
(via `lingo`) with a `prompt:` template and returns structured output validated
against its mandatory `output_schema`, advancing the route by position (Schema
2).

## Scope
- **In scope:** prompt templating (dotted paths + system vars), lingo call,
  output handling against the S1 mandatory contracts.
- **Out of scope:** `output_schema` compilation (LEG-072).

## Contract & design
- A `kind: linguistic` agent (Schema 1) declares mandatory
  `input_as`/`input_type`/`input_schema` and
  `output_as`/`output_type`/`output_schema`, with
  `prompt: "<template with {var}>"`. Interior↔contract coherence: every
  `{var}` in the prompt must be declared in `input_schema` (all used, all
  declared — undeclared is a load error); the linguistic `output_schema` is
  enforced at runtime.
- The prompt resolves dotted paths + system vars against the chain-in-scope;
  an undefined path is an explicit error (LEG-031), never silent.
- Called via lingo; the outcome builds the new payload and is routed by
  position (finality by position + `level`, Schema 2).

## Interface
- `LinguisticAgent(...)` runner over `AgentBase`, bound to a `kind: linguistic`
  spec.

## Acceptance criteria
From `docs/PLAN.md` (LEG-030), verbatim:
- A linguistic step run within a composite returns structured output whose
  template was resolved from the payload, validated against its
  `output_schema`; tests use a fake lingo. A prompt `{var}` not declared in
  `input_schema` is a load error.

## Tests
- Contract tests (red first) with a fake lingo: templating, structured result
  validated against `output_schema`, prompt-variable↔`input_schema` coherence.

## Validation case
- In-repo linguistic step (fake lingo) inside an example composite.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.