# LEG-011 — FlowToken & messages (v1)

- **Status:** CLOSED (implementation green, maintainer approved, issue closed)
- **Rasante:** R-1 (contract)
- **GitHub issue:** #5
- **Source:** `docs/PLAN.md` (LEG-011)
- **Depends on:** ARCHITECTURE §3

## Goal
Define the immutable, typed FlowToken and the two message types that move work
through the system (`ExecutionRequestMessage`, `ExecutionResultMessage`),
including `schema_version` and the root/delivery semantics.

## Scope
- **In scope:** token fields, versioning, finality-by-position, root handling,
  delivery target semantics.
- **Out of scope:** authoring logic (R-5), serialization of payloads themselves.

## Contract & design
- FlowToken fields: `route_pattern_names`, `current_index`,
  `ultimate_return_agent_id`, `origin_node_id`, `root`, `task_id`.
- Root: `root=True`, `ultimate_return_agent_id = client:{task_id}`.
- "Is final?" derived from position: last step → delivery (parent or client),
  never a flag.
- Messages: `ExecutionRequestMessage` (start/deposit a step),
  `ExecutionResultMessage` (return); message type discriminates in the dual
  queue.
- Immutable pydantic models with `schema_version`; major mismatch → reject.

## Interface
- pydantic model definitions + serialization contract (JSON).

## Acceptance criteria
From `docs/PLAN.md` (LEG-011), verbatim:
- Serialization/deserialization round-trip preserves all fields; versioned,
  rejected on major mismatch; finality derived from position.

## Tests
- Contract tests (red first): round-trip, version guard, finality.

## Validation case
- Exercises LE-001-style token flows via unit tests (no real domain).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.