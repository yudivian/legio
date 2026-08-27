# LEG-081 — Worker CLI (typer)

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-8
- **GitHub issue:** #41
- **Source:** `docs/PLAN.md` (LEG-081)
- **Depends on:** LEG-014, LEG-025, LEG-027, LEG-017, LEG-015

## Goal
Operational entry points: `legio worker ...` (run worker) and
`legio server ...` (run federation-facing server), honoring the LEG-017 config
shape (node id, federation token, client tokens, peer allowlist).

## Scope
- **In scope:** typer CLI for worker + server, config loading per LEG-017.
- **Out of scope:** validate subcommand (LEG-071), federation internals (R-9).

## Contract & design
- `legio worker --config path`: starts pools for the node's agents, serving
  `submit`/`status`; honors `api.clients` (LEG-027 middleware).
- `legio server --config path`: additionally exposes federation endpoints
  (once R-9 lands) with L1 federation-token guard + peer allowlist.
- Config YAML shape exactly per LEG-017 (`node`, `federation_token`,
  `api.clients[]`, `peers[]`).

## Interface
- Two typer commands; config schema per LEG-017.

## Acceptance criteria
From `docs/PLAN.md` (LEG-081), verbatim:
- `legio worker ...` and `legio server ...` start, expose submit/status, and
  honor the LEG-017 config shape.

## Tests
- CLI contract tests: start/stop, config loading, endpoint exposure.

## Validation case
- The E2E example run through the CLI.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.