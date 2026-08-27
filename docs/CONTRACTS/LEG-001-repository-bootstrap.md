# LEG-001 — Repository & package bootstrap

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-0
- **GitHub issue:** #1
- **Source:** `docs/PLAN.md` (LEG-001)
- **Depends on:** none (first issue; must not use any dependency)

## Goal
Create the repository layout, `pyproject.toml` and `uv` environment for the
`legio` package so that the rest of the project builds on a clean, reproducible
foundation.

## Scope
- **In scope:** layout with `src/legio`, `pyproject.toml` (project metadata +
  dev tooling only), `.gitignore`, the docs set this series lives in.
- **Out of scope:** any runtime code, any runtime dependency install.

## Contract & design
- Package name `legio`, `src`-layout, managed with `uv` (Python >= 3.13, per
  `docs/DEPENDENCIES.md`).
- No dependency beyond what `docs/DEPENDENCIES.md` allows; at this stage only
  dev tooling (`ruff`, `pytest`, `pytest-asyncio`, `respx`, optional `pyright`)
  may be installed to let CI run.

## Interface
- `import legio` succeeds and exposes `__version__`.

## Acceptance criteria
From `docs/PLAN.md` (LEG-001), verbatim:
- `uv run python -c "import legio"` works; `uv lock` resolves against the
  approved dependency set only; package builds.

## Tests
- `uv run python -c "import legio; print(legio.__version__)"` (smoke).
- `uv lock` resolves; `ruff` runs clean on the empty skeleton.

## Validation case
- In-repo smoke (foundation rasante; no composite validation case yet).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.