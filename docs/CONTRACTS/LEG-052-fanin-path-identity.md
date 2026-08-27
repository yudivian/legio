# LEG-052 — Fan-in identity by path (not agent name)

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-5
- **GitHub issue:** #29
- **Source:** `docs/PLAN.md` (LEG-052)
- **Depends on:** LEG-041, ARCHITECTURE §6

## Goal
Correct fan-in identity: a step is identified by `task_id` + path position in
the DAG, *not* by agent name. Fixes the earlier agent-name bug.

## Scope
- **In scope:** step id semantics (`task_id`+path), naming of inline steps,
  dedup/regression of the agent-name merge bug.
- **Out of scope:** FINAL-identity semantics already covered by LEG-042.

## Contract & design
- Same agent name at two disk-positions = two distinct steps = two distinct
  fan-in holes (LEG-042). Identity = task + dotted path, no global agent
  collision.
- `output_as` namespacing resolves merge key collisions (H3).

## Interface
- Step ID composition API.

## Acceptance criteria
From `docs/PLAN.md` (LEG-052), verbatim:
- Same-named parallel branches at different positions do not merge; regression
  tests cover the earlier agent-name bug.

## Tests
- Regression + identity contract tests (red first).

## Validation case
- `distribute_summary` parallel branches.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.