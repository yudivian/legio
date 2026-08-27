# LEG-090 — Per-node catalog (roster derived from capacity, symmetric)

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-9
- **GitHub issue:** #39
- **Source:** `docs/PLAN.md` (LEG-090)
- **Depends on:** LEG-015 (federation contract), LEG-021

## Goal
Each node serves its own catalog over `GET /catalog`: agents, interfaces and
`schema_version`, derived from the node's loaded pattern capacity — symmetric
(no orchestrator/provider roles).

## Scope
- **In scope:** catalog endpoint, capacity derivation, federation-token guard.
- **Out of scope:** remote resolution/deposit (LEG-091/092).

## Contract & design
- Catalog lists each agent's capability + interface and the `schema_version`;
  derived from what the node can actually execute (loaded patterns + tools +
  lingo).
- `GET /catalog` requires the shared federation token (L1) per LEG-017.

## Interface
- `GET /catalog` → `{schema_version, agents: [{agent, interface, kind}]}`.

## Acceptance criteria
From `docs/PLAN.md` (LEG-090), verbatim:
- Catalog served over GET /catalog lists agents, interfaces and
  `schema_version`; requester token (federation) validated.

## Tests
- Contract tests (red first): derivation, token guard.

## Validation case
- LEG-094 multi-node example (catalog discovery).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.