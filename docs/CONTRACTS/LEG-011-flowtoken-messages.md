# LEG-011 — FlowToken & messages (Schema 2, revised)

- **Status:** REVISED 2026-08-31 (reconciled to Schema 2 after the S4
  simulation; supersedes the v1 CLOSED contract of the same name)
- **Rasante:** R-1 (contract)
- **GitHub issue:** #5
- **Source:** `docs/PLAN.md` (LEG-011); `docs/AGENT_LIFECYCLE.md` §4.11 Schema 2
- **Depends on:** ARCHITECTURE §3

## Goal
Define the immutable, typed FlowToken and the two message types that move work
through the system (`ExecutionRequestMessage`, `ExecutionResultMessage`),
including `schema_version`, the per-level token fields and the flow-end rule.

## Scope
- **In scope:** the Schema 2 token fields, versioning, the advancement /
  end-of-level / flow-end rule, `end_of_level_queue` semantics (no boards, no
  `next_queue`).
- **Out of scope:** authoring logic (the submit); serialization of payloads
  themselves; the `results` board / `client:{task_id}` return (removed).

## Contract & design
- FlowToken fields (Schema 2):

  | Field | Role |
  |---|---|
  | `schema_version` | int, `1000`; mismatch → reject. |
  | `level_route` | tuple of classes — the route of this level (a branch or sub-sequence). |
  | `current_index` | int, 0-based position of the class processing in `level_route` (advance `+1` = next). |
  | `end_of_level_queue` | queue at the end of this level's sequence — created by the **submit** (final-result queue) or by a **parallel** (its gathering queue). |
  | `level` | branch-depth counter: starts at 1; branching +1; leaving a branch −1. End-of-sequence AND `level == 1` ⇒ flow finished. |
  | `launcher_class` | class of the agent that started the flow; constant, informational, not control. |
  | `task_id` | str, the process's public id. |
  | `message_type` | enum `execution_request` \| `execution_result`. |
  | `payload` | the data (single container for both roles). |

- **Advance (request):** `current_index < len(level_route)-1` → deliver `payload`
  to class `level_route[current_index+1]` (by position, no `next_queue` field).
- **End-of-level:** `current_index == len(level_route)-1` → deliver to
  `end_of_level_queue`.
- **Flow end (generalized rule, addendum AV):** end-of-sequence AND `level == 1`
  ⇒ final: deliver the final result to `end_of_level_queue` (= the final-result
  queue set by the submit). Nothing more is routed. It holds regardless of the
  agent type (sequence step, atomic, or parallel-at-level-1).
- **Parallel (branching):** a parallel class on receiving its request does not
  advance while its branches run; it fans out giving each branch its
  `level_route` and `current_index = 0`, incrementing `level` (+1). Branches
  return to the parallel's **gathering queue** via their `end_of_level_queue`.
  On fan-in completion the parallel decrements `level` (−1) and resumes its own
  level (`current_index + 1` → next of its level), with `end_of_level_queue` the
  one its creator supplied.
- **Parallel as root:** submit passes its sequence as level 1 with
  `end_of_level_queue` = final-result queue; branches run at level 2 with
  gathering; after fan-in the parallel advances its level-1 sequence with the
  submit's final-result queue (addendum AM).
- **`root`** lives in the FlowToken (subclassing the message), not in the queue
  message; `end_of_level_queue` = final-result queue is the board-free equivalent
  of the old "results board". The agent does not decide where to deposit — who
  creates the flow assigns the class queue; the information lives always in the
  token (addenda AJ/AL). There is no `route_pattern_names` (global route),
  no `ultimate_return_agent_id`, and no `client:{task_id}`/`results:{}` board.
- Messages: `ExecutionRequestMessage` (start/deposit a step),
  `ExecutionResultMessage` (return); `message_type` discriminates in the dual
  queue.
- Immutable pydantic models with `schema_version`; major mismatch → reject.

## Interface
- pydantic model definitions + serialization contract (JSON).

## Acceptance criteria
- Serialization/deserialization round-trip preserves all Schema 2 fields;
  versioned, rejected on major mismatch.
- Flow-end derived from position + `level` (end-of-sequence AND `level == 1`),
  per the generalized rule; end-of-level with `level > 1` closes to the
  creator's gathering queue.
- No `next_queue`, no boards, no `ultimate_return_agent_id`: the destination is
  always `end_of_level_queue`, assigned by the flow creator.

## Tests
- Contract tests (red first): round-trip, version guard, flow-end/level logic,
  parallel fan-out/level bookkeeping, parallel-as-root.

## Validation case
- Exercises the S4 simulation flows (runs 1–4) via unit tests (no real domain).

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.
