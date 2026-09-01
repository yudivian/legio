# LEG-XXX — <Title>

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-X
- **GitHub issue:** #NN
- **Source:** `docs/PLAN.md` (LEG-XXX)
- **Depends on:** (contracts/specs this references)

## Goal
One or two sentences: what this issue delivers and why.

## Scope
- **In scope:** ...
- **Out of scope:** ... (what later issues cover)

## Contract & design
- Key rules/decisions from `docs/ARCHITECTURE.md` and `docs/CONTRACTS/` that
  this issue implements. Point to the concrete mechanisms.

## Interface
- The public surface this issue defines (config shape, CLI, endpoints,
  function signatures, registry/queue names) — only what is externally observable.

## Acceptance criteria
From `docs/PLAN.md` (LEG-XXX), verbatim:
- ...

## Tests
- Contract tests written first (red), implementation second (green).
- Substitutes: MockLLM / fakes / `respx` / temporary beaver file.

## Validation case
- The green case that exercises this issue (in-repo example and/or an external
  consumer repo kept separate — never consumer material inside `legio`).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.