# LEG-013 — Tool registry interface (v1)

- **Status:** CLOSED (implementation green, maintainer approved, issue closed)
- **Rasante:** R-1 (contract)
- **GitHub issue:** #7
- **Source:** `docs/PLAN.md` (LEG-013)
- **Depends on:** ARCHITECTURE §5

## Goal
Define how the consumer injects tools into a node: the single domain extension
point of `legio`.

## Scope
- **In scope:** registration API, resolution by `tool_type`, input/output
  schema validation, lifecycle (registered at worker startup).
- **Out of scope:** tool implementations (consumer side), the ToolAgent
  execution path (LEG-022).

## Contract & design
- A tool is an opaque, substitutable resource exposing only
  `input_schema`/`output_schema` (pydantic). It never knows about agents or
  queues.
- Registry per node; tools registered at startup against their `tool_type`.
- Several patterns may share a tool; the shared resource is guarded by a
  per-tool concurrency semaphore (mechanism in LEG-082).

## Interface
- `register(tool_type, tool, input_schema, output_schema)`,
  `resolve(tool_type) -> Tool`, `schemas(tool_type)`.

## Acceptance criteria
From `docs/PLAN.md` (LEG-013), verbatim:
- Registering a fake tool, resolving by `tool_type`, and validating
  input/output schemas are covered by contract tests.

## Tests
- Contract tests (red first): registration, resolution, schema validation.

## Validation case
- In-repo example tool (`transform` fake tool) through the registry.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.