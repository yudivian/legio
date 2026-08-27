# LEG-093 — Outbox polling by the author (write-before-ack, idempotency)

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-9
- **GitHub issue:** #46
- **Source:** `docs/PLAN.md` (LEG-093)
- **Depends on:** LEG-092, LEG-020 (queue dedup)

## Goal
Result readback for remote work: author polls the node's outbox; ack consumes
(read-after-ack = empty). Duplicate work-item (same id) is executed only once.

## Scope
- **In scope:** outbox read/ack, write-before-ack ordering, idempotency.
- **Out of scope:** transport beyond the outbox endpoints.

## Contract & design
- The helper *writes* the result to the outbox *before* acknowledging the
  work-item (write-before-ack), so a crash after ack never loses it.
- Author polls outbox, ack consumes; ack is destructive (re-read empty).
- Idempotent deposit: queue dedup by task id means a duplicated
  `POST /work-items/{agent}` with the same id executes once (LEG-020 dedup).

## Interface
- Outbox `GET /outbox` (auth L1) + consume/ack endpoint.

## Acceptance criteria
From `docs/PLAN.md` (LEG-093), verbatim:
- Author polls outbox, ack consumes; re-read after ack is empty; duplicate
  work-item (same id) is not executed twice.

## Tests
- Contract tests (red first): poll/ack, write-before-ack, dedup-once.

## Validation case
- LEG-094 multi-node example (round trip).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.