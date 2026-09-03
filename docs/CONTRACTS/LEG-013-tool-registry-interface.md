# LEG-013 — Tool registry interface (Schema 3)

- **Status:** APPROVED (Schema 3 — `available_tools` tools declaration; see
  `docs/AGENT_LIFECYCLE.md`)
- **Rasante:** R-1 (contract)
- **GitHub issue:** #7
- **Source:** `docs/PLAN.md` (LEG-013)
- **Depends on:** ARCHITECTURE §5, `docs/AGENT_LIFECYCLE.md` §4.11 Schema 3

## Goal
Define how tools are **declared and loaded** (Schema 3): the consumer injects
tools into a node as an `available_tools` declaration, each tool being an
independent, autosufficient resource that the flow can bind to.

## Scope
- **In scope:** the `available_tools: {<name>: {implementation, policy}}`
  declaration, resolution by name, and the reconciliation of a tool's declared
  contract to the using agents (execution-time verification).
- **Out of scope:** the tool implementations themselves (consumer side); the
  ToolAgent execution path (LEG-022); the loading mechanics (import vs
  programmatic registration) and the async execution mechanism — these are
  explicitly **not** fixed by the schema and are
  decided at implementation.

## Contract & design
- **Declaration (Schema 3 shape):**
  ```yaml
  available_tools:
    <name>:
      implementation: <dotted.path.to.resource>
      policy: { timeout: <seconds per call>, retries: <call retries> }
  ```
- A tool is an opaque, substitutable execution resource; it **never knows**
  which agents use it, and it does **not** declare its output capacity — the
  consuming agents declare the output via `output_as`/`output_schema`
  (Schema 1). The tool identifier is the explicit `available_tools` key, and
  that name is the bridge used in the agent's `tool: <name>` (Schema 1).
- **Two verification domains:**
  - **Static / load** — the flow-against-itself: agents' schemas (S1) verify the
    flow definition is coherent (§4.10). Load-time verification is NOT against
    the tool.
  - **Execution** — coherence against the tool (its signature/parameters) is
    checked **in execution**, because the tool is loaded dynamically; its
    contract is not verifiable before. An in-execution mismatch is a visible
    error (rule 9), not silently swallowed.
- `policy.retries` = how many times the executing entity retries the **call**;
  `policy.timeout` = how long you may wait **per call**.

## Interface
- `available_tools` declaration (above); a name-resolution API
  (`resolve(name) -> tool`) used by the executing agent once a tool is loaded.

## Acceptance criteria
From `docs/PLAN.md` (LEG-013), reworked for Schema 3:
- `available_tools` with `implementation` + `policy` loads and validates.
- A broken/missing `implementation` fails loudly at execution, never silently.
- A tool whose signature rejects an agent's `parameters` call is a visible
  execution error.

## Tests
- Contract tests (red first, once S1/S3 migration begins): declaration parsing,
  policy validation, execution-time signature mismatch surfaced, missing
  `implementation` surfaced.

## Validation case
- In-repo example tool (`transform` fake tool) declared via `available_tools`.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.