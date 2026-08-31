# LEG-081 — Runtime CLI (typer)

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-8
- **GitHub issue:** #41
- **Source:** `docs/PLAN.md` (LEG-081)
- **Depends on:** LEG-014, LEG-025, LEG-027, LEG-017, LEG-015

## Goal
Operational entry points: the runtime bootstrap (`legio server ...`) brings up
the node's agents and serves `submit`/`status`, and `legio agent ...` exposes the
Runtime's lifecycle verbs (§4.8 of AGENT_LIFECYCLE). Honors the LEG-017 config
shape (node id, federation token, client tokens, peer allowlist). Domain
knowledge enters **only as YAML data** (patterns) — the CLI never invents or
hosts domain logic (rule: domain-free library).

## Scope
- **In scope:** typer CLI for the node + the agent lifecycle, config loading per
  LEG-017.
- **Out of scope:** validate subcommand (LEG-071), federation internals (R-9),
  business domains (legio sees only patterns as YAML data, rule 7).

## Contract & design
- `legio server --config path`: runs the bootstrap (§8 of AGENT_LIFECYCLE) —
  brings up the node's agents from their pattern specs — and serves
  `submit`/`status`; honors `api.clients` (LEG-027 middleware).
- `legio agent <command>`: maps 1:1 to the Runtime lifecycle verbs
  (create/enable/disable/destroy at the class and instance levels, §4.8) — a
  thin wrapper over the Runtime, no new logic.
- **YAML is the data language of the lifecycle:** `create-class` takes the
  pattern spec as `<spec.yaml>` and `recreate-class` is driven by the cached
  YAML (`get_cached_spec`, §4.7); `--pool N` accompanies the spec at create
  (LEG-080). Read verbs (`list-classes`, `class-deps`, `class-state`,
  `list-instances`) delegate to the registry mirror.
- `legio server --config path --federation`: additionally exposes federation
  endpoints (once R-9 lands) with L1 federation-token guard + peer allowlist.
- Config YAML shape exactly per LEG-017 (`node`, `federation_token`,
  `api.clients[]`, `peers[]`).

## Interface
- Two typer commands; config schema per LEG-017.

## Acceptance criteria
From `docs/PLAN.md` (LEG-081), verbatim:
- The node starts via the CLI, exposes submit/status, and honors the LEG-017
  config shape; the lifecycle verbs are reachable through `legio agent`.

## Tests
- CLI contract tests: start/stop, config loading, endpoint exposure, lifecycle
  verb mapping.

## Validation case
- The E2E example run through the CLI.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.