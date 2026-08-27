# LEG-027 — Auth middleware (client & federation tokens)

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-2
- **GitHub issue:** #19
- **Source:** `docs/PLAN.md` (LEG-027)
- **Depends on:** LEG-017 (security), LEG-025, LEG-015

## Goal
A single FastAPI middleware enforcing the LEG-017 two-level security model:
per-client tokens on `submit`/`status` (Level 2) and the shared federation
token on federation endpoints (Level 1), with the endpoint→required-token map
as configuration.

## Scope
- **In scope:** token map config, middleware guard, agent allowlist per client,
  ownership enforcement integration, `401/403` mapping.
- **Out of scope:** federation endpoints themselves (R-9).

## Contract & design
- One middleware: reads request path → looks up which token(s) guard that
  endpoint → validates `Authorization` (or header) accordingly.
  - L2 endpoints (`submit`, `status`): valid client token; agent allowlist
    enforced (default: all starting agents; restricted when `agents:` set);
    ownership must already hold (LEG-014/025).
  - L1 endpoints (federation, once they exist): the single shared federation
    token.
- Config shape per LEG-017 (`api.clients` with `token`/`agents`).

## Interface
- Middleware over the FastAPI app; config schema per LEG-017.

## Acceptance criteria
From `docs/PLAN.md` (LEG-027), verbatim:
- Setup/teardown; `submit` with the right client token works, wrong token →
  401; status of another client's task → 403 enforced at token layer;
  restricted client denied on non-allowed agent; revocation of a token stops
  working (test explicitly).

## Tests
- Contract tests from LEG-017 §Tests, exercised in green.

## Validation case
- LEG-026 example runs behind auth; revocation scenario green.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.