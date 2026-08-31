# LEG-022 — ToolAgent + tool registry (implementation)

- **Status:** CLOSED (implementation green, maintainer approved, issue closed)
- **Rasante:** R-2
- **GitHub issue:** #14
- **Source:** `docs/PLAN.md` (LEG-022)
- **Depends on:** LEG-013, LEG-011

## Goal
Implement the ToolAgent: lease a tool work-item from its queue, take the
`input` from the message-carried payload, call the registered tool, validate
the output and deposit the result token (AGENT_LIFECYCLE §12.1: step state
rides in the messages; there is no out-of-message staging board).

## Scope
- **In scope:** the ToolAgent execution path, result deposit.
- **Out of scope:** concurrency semaphores (LEG-082), retries (R-6).

## Contract & design
- Per LEG-010 H1: inline tool steps are auto-named agents with their own queue
  and join; ToolAgent consumes them.
- Flow: lease item (queue contract) → assert stage expects a tool → read
  `input` from `request.payload` → validate against tool `input_schema` → call
  tool → validate `output_schema` → deposit `ExecutionResultMessage` back to
  parent (or client for last step), or advance to the next stage.
- Atomicity of the lease via lock on the queue item.

## Interface
- Internal `ToolAgent(registry, queue, board, locks)` runner.

## Acceptance criteria
From `docs/PLAN.md` (LEG-022), verbatim:
- A fake registered tool executes through ToolAgent end-to-end, validating
  schema on both edges, with results staged and token deposited.

## Tests
- Contract tests (red first): happy path, schema rejection both edges.

## Validation case
- `transform` fake tool example end-to-end.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.