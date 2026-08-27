# LEG-042 — Fan-in: dual queue by path identity, canonical hole resolution

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-4
- **GitHub issue:** #25
- **Source:** `docs/PLAN.md` (LEG-042)
- **Depends on:** LEG-052 (path identity), LEG-023

## Goal
The dual-queue (UNIQ-NUM-L2AΛ / NUM-L2A) fan-in with canonical hole
resolution: exactly-once join, path-stable even before children arrive, and
correct behavior when a child is bugged — for sequence and parallel alike.

## Scope
- **In scope:** dual structure, hole semantics and resolution (departure
  gate), join stability pre-arrival, gate follow-on conformation.
- **Out of scope:** agent-level behavior (sequence/parallel agents on top).

## Contract & design
- Per H3: join is executed when the DUAL manager confirms the hole resolved &
  departure gate settled; tokens of a step wait at the canonical hole until
  its predecessor resolves.
- Vikariated frames / out-gate treats union-merge as the canonical resolution.
- Enforced by LEG-052 path identity: two same-name steps are two distinct
  holes; no inter-merge by agent name.

## Interface
- Dual-queue composition API; step join resolution API.

## Acceptance criteria
From `docs/PLAN.md` (LEG-042), verbatim:
- [per LEG-052] same-named parallel branches at different positions do not
  merge; regression tests cover the earlier agent-name bug.

## Tests
- Contract tests (red first): hole canonical resolution, stability-pre-arrival,
  agent-name bug regression.

## Validation case
- Composite examples (`extract_and_summarize`, `distribute_summary`).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.