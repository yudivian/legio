# LEG-091 — Step resolver: required agent → local | remote

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-9
- **GitHub issue:** #43
- **Source:** `docs/PLAN.md` (LEG-091)
- **Depends on:** LEG-090

## Goal
The author resolves each step's required agent before deposit: local when
present, remote when a peer catalog offers it, error otherwise — resolution
happens before depositing.

## Scope
- **In scope:** resolution logic (local/remote/error), pre-deposit gate.
- **Out of scope:** the remote deposit transport (LEG-092).

## Contract & design
- Resolution order: local catalog → peer catalogs (interface + `schema_version`
  must match) → error (LEG-016 taxonomy).
- Happens at authoring time, before topping any queue; nothing is deposited
  unresolvable.

## Interface
- `resolve(agent) -> Local | Remote(node, catalog)`.

## Acceptance criteria
From `docs/PLAN.md` (LEG-091), verbatim:
- Author resolves each step locally when present, remote when the peer catalog
  offers it, error otherwise; resolution happens before deposit.

## Tests
- Contract tests (red first): local/remote/error resolution.

## Validation case
- LEG-094 multi-node example (remote delegation).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.