# LEG-070 — Cascade invalidation on invalid dependencies

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-7
- **GitHub issue:** #36
- **Source:** `docs/PLAN.md` (LEG-070)
- **Depends on:** LEG-021

## Goal
Pattern engine integrity: disabling or invalidating a (possibly broken)
pattern transitively disables every pattern that depends on it; the catalog
reflects the invalidation.

## Scope
- **In scope:** dependency graph, transitive invalidation, catalog state.
- **Out of scope:** startup gate behavior (LEG-071 owns fail-fast).

## Contract & design
- Catalog is a dependency DAG; invalidating a node marks all descendants
  invalid and removes them from the served catalog.
- Invalidation is visible (a pattern referencing an invalid dependent is
  reported as disabled), not masked.

## Interface
- `invalidate(pattern)`; catalog reflects invalid/disabled set.

## Acceptance criteria
From `docs/PLAN.md` (LEG-070), verbatim:
- Disabling one broken pattern transitively disables dependents; the catalog
  reflects it; test verifies the full chain.

## Tests
- Contract tests (red first): chain invalidation.

## Validation case
- Stale-pattern injection fixture.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.