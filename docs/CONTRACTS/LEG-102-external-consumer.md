# LEG-102 — External consumer pins the released legio

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-10
- **GitHub issue:** #47
- **Source:** `docs/PLAN.md` (LEG-102)
- **Depends on:** LEG-101

## Goal
Prove the released package against a real consumer in its own repository (kept
separate — never consumer material in `legio`), pinning the released version
with its validation suite green.

## Scope
- **In scope:** consumer repo pins `legio==0.1.0`; its validation suite green.
- **Out of scope:** any consumer material inside `legio` (per AGENTS.md rule 7).

## Contract & design
- A separate consumer repository depends on the published `0.1.0` and runs its
  own validation suite against it (in editable mode during development is
  allowed, but this issue validates against the released artifact).
- Traceability: the consumer records the exact pinned version.

## Interface
- Dependency pin `legio==0.1.0`.

## Acceptance criteria
From `docs/PLAN.md` (LEG-102), verbatim:
- The consumer repo pins the released version; its validation suite runs green
  against it.

## Tests
- Consumer's suite in green on the pinned release.

## Validation case
- The external consumer integration run.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.