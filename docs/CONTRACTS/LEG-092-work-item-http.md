# LEG-092 — Work-item over HTTP + remote deposit (federation-token auth)

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-9
- **GitHub issue:** #44
- **Source:** `docs/PLAN.md` (LEG-092)
- **Depends on:** LEG-015, LEG-017 (L1 token), LEG-091

## Goal
Remote deposit: `POST /work-items/{agent}` with the shared federation token
(L1) and a matching interface deposits into the acceptor's queue.

## Scope
- **In scope:** the endpoint, federation-token auth, interface-mismatch errors.
- **Out of scope:** result return path (outbox, LEG-093).

## Contract & design
- Accept: valid federation token (L1 guard) + payload conforming to the
  declared interface of `{agent}` + `schema_version` match.
- Deposit into the acceptor's local queue (task id from the author for
  idempotency, LEG-093).
- Error mapping per LEG-016/017: no token → 401; mismatch → 4xx.

## Interface
- `POST /work-items/{agent}` body `{task_id, payload, schema_version}`.

## Acceptance criteria
From `docs/PLAN.md` (LEG-092), verbatim:
- POST /work-items/{agent} with valid federation token and matching interface
  deposits into the acceptor queue; mismatch → 4xx; no token → 401.

## Tests
- Contract tests (red first): ok, 401, 4xx-mismatch.

## Validation case
- LEG-094 multi-node example.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.