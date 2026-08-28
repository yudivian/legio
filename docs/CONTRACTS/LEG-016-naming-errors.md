# LEG-016 — Naming & errors (v1)

- **Status:** APPROVED (contract tests red)
- **Rasante:** R-1 (contract)
- **GitHub issue:** #10
- **Source:** `docs/PLAN.md` (LEG-016)
- **Depends on:** none

## Goal
Normative glossary of identifiers and the canonical error taxonomy so names are
type-safe across the codebase, logs and APIs.

## Scope
- **In scope:** identifier types (node, agent, tool, pattern, step, task),
  namespacing, error taxonomy, reserved identities.
- **Out of scope:** string interning decisions beyond contracts.

## Contract & design
- **Identifiers** are cleared, immutable strings; each type has a regex and a
  reserved-value set:
  - node: `node_name@host` (interned, immutable)
  - agent: service/domain names; `client:{task_id}` is reserved for the mini-manager
  - tool: arbitrary (consumer namespaced)
  - task: `{origin_node_id}:{uuid}`, globally unique
- **Errors** are typed exceptions with `code`, `recoverable: bool`, and
  `retriable: bool` (feeds LEG-061); boundaries (HTTP, CLI, logs) render them
  consistently.

## Interface
- Identifier validation helpers + error classes as the module contract.

## Acceptance criteria
From `docs/PLAN.md` (LEG-016), verbatim:
- Identifiers typechecked in module signature; invalid names rejected at
  runtime; error codes/recoverable/retriable documented.

## Tests
- Contract tests (red first): naming rules, reserved identities, error mapping.

## Validation case
- Unit-level.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.