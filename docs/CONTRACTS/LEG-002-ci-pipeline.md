# LEG-002 — CI pipeline

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-0
- **GitHub issue:** #2
- **Source:** `docs/PLAN.md` (LEG-002)
- **Depends on:** LEG-001 (repo layout)

## Goal
A CI pipeline (GitHub Actions) that runs lint, typecheck and the full test
suite on every PR, using the `uv` environment, so "green" means something
reproducible.

## Scope
- **In scope:** one workflow with jobs lint → typecheck → tests; env via `uv`.
- **Out of scope:** deployment, releases, secrets.

## Contract & design
- Pipeline must never touch real networks or real LLMs (per
  `docs/CONTRIBUTING.md` §2).
- Runs on every PR to `main`; must be the single gate for merging.

## Interface
- PR checks: `ruff`, typecheck, `pytest` — one combined status.

## Acceptance criteria
From `docs/PLAN.md` (LEG-002), verbatim:
- A PR triggers one pipeline running `uv run ruff check`, `uv run pytest`, and
  typecheck; a failing test turns the job red and a passing one green. No real
  network/LLM in CI.

## Tests
- A deliberately failing test turns the job red (manual verification once).
- Normal suite is green.

## Validation case
- In-repo (foundation; the pipeline itself is the validation).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.