# LEG-015 — Federation contract (v1)

- **Status:** CLOSED (implementation green, maintainer approved, issue closed)
- **Rasante:** R-1 (contract)
- **GitHub issue:** #9
- **Source:** `docs/PLAN.md` (LEG-015)
- **Depends on:** ARCHITECTURE §9 (symmetric federation)

## Goal
Define the v1 federation contract between equal peer nodes: node registry /
roster, catalog, interfaces with `schema_version`, remote work items and the
outbox — with a single shared federation token guarding it.

## Scope
- **In scope:** peer list + allowlist, `GET /catalog`, `POST /work-items/*`,
  outbox polling semantics, symmetric author/helper roles, versioned interface
  negotiation, domain-free capability discovery.
- **Out of scope:** REST implementation (R-9), security details (LEG-017).

## Contract & design
- **Symmetric:** every node may act as author *and* helper; no
  orchestrator/provider roles (ARCHITECTURE §9).
- **Roster:** derived from each node's catalog under symmetric semantics;
  peer allowlist at config (L1 federation token).
- **Interfaces:** an agent is identified by its capability + `schema_version`
  (agent interface); negotiation happens before use.
- **Work items:** remote deposit into the acceptor's queue (dedup by task id
  via idempotency in LEG-093); read-then-ack via outbox.

## Interface
- `GET /catalog`, `POST /work-items/{agent}`, outbox `GET`/`DELETE`-consumed
  (details in R-9).

## Acceptance criteria
From `docs/PLAN.md` (LEG-015), verbatim:
- Federation messages accepted/rejected by interface conformance (versioned);
  catalog derived from capacity; symmetric 3-node example (LEG-094).

## Tests
- Contract tests (red first): catalog derivation, version conformance.

## Validation case
- Multi-node in-repo example `docs/VALIDATIONS/single-node-model.md` extended
  (LEG-094 is the full symmetric example).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.