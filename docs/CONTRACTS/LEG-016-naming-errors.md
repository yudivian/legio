# LEG-016 — Naming & errors (v1)

- **Status:** CLOSED (implementation green, maintainer approved, issue closed)
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
  - agent: service/domain names (class-based per Schema 2; no `client:` family —
    the destination lives in the token as `end_of_level_queue`, not in an agent id)
  - tool: arbitrary (consumer namespaced)
  - task: `{uuid}`, globally unique; its final result is addressed by the helper
    `result_queue_key(task_id)` → `result:<task_id>` (the submit-seeded
    `end_of_level_queue` at level 1)
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