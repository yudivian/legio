# LEG-010 — Patterns YAML schema (S1)

- **Status:** APPROVED (S1 — one agent spec; see `docs/AGENT_LIFECYCLE.md`
  §4.10/§4.11)
- **Rasante:** R-1 (contract)
- **GitHub issue:** #4
- **Source:** `docs/PLAN.md` (LEG-010)
- **Depends on:** H1–H4 findings in `docs/VALIDATIONS/single-node-model.md`

## Goal

Define the S1 YAML schema for patterns. Patterns are **YAML data** (rule
7) defining **agents**: one single agent specification shared by every agent
(`atomic`|`composite` × `tool`|`linguistic`|`sequence`|`parallel`), with
**mandatory symmetric entry/output contracts** (full triples on every agent, no
exceptions), a **terse call vocabulary** for tools (`parameters: {arg:
dotted.path | literal}` — no `{from:}`/`bind:`/`emit:`/`children`), chain-wide
composability verification by **contract compatibility**, reuse of any
definition by `pattern:` and by repetition (position), and `main` as a root
capability. The full normative statement lives in `docs/AGENT_LIFECYCLE.md`
§4.10 / §4.11 Schema 1.

## Scope

- **In scope:** the one agent spec (§4.10.1); branch-exclusive structural
  enforcement (no inference); mandatory symmetric contracts with
  `input_as`/`output_as` (the anti-convention rule, §4.10.2) and contract
  compatibility as the composition relation; the terse call
  vocabulary and chain-wide resolution (§4.10.3); interior ↔ contract coherence
  (tool ↔ code signature; linguistic prompt variables ↔ `input_schema`;
  linguistic `output_schema` enforced at runtime) §4.10.4; reuse of every
  definition by `pattern:` / repetition and encapsulation (§4.10.5); composite
  output without `emit:` (the combination is the agent's implementation,
  §4.10.6); `main` as root capability not position (§4.10.7);
  load-time composability verification (§4.10.8).
- **Out of scope:** the tool registry + policy (Schema 3 / `available_tools`);
  the message/token envelope (Schema 2); materialization artifacts (queue
  names, compiled pydantic models, derived identities); the `output_schema`
  mini-grammar (defined by LEG-072 compilation semantics); the loader
  (LEG-021), dry-run validator (LEG-071).

## Contract & design

### The one agent spec (§4.10)

```yaml
type: atomic | composite
kind: tool | linguistic | sequence | parallel
name: <id>
description: <text>                     # optional
main: bool                              # optional; root capability, NOT position

# Entry contract — MANDATORY for every agent
input_as: <alias>                       # no magic word
input_type: text | json | binary
input_schema:                           # mandatory (json: object; text has none)

# Output contract — MANDATORY for every agent
output_as: <alias>
output_type: text | json | binary
output_schema:                          # mandatory (json: object; text has none)

# Interior — exactly one, by kind
tool: <available_tools-key>             # kind: tool; the CALL + the code's signature
parameters: { <arg>: <dotted.path | literal> }   # kind: tool; terse, no {from:}/{value:}/{default:}
prompt: "<template with {var}>"         # kind: linguistic
sequence: [ ... ]                       # kind: sequence (refs pattern:<name> or inline w/ name)
parallel: [ ... ]                       # kind: parallel (children bind only from input_as)
```

### Rules (normative subset)

- **Discriminators:** `type`/`kind` cross-validated; branch-exclusive fields
  (a tool branch never has `prompt`, etc.); atomic kinds exclusive; crossed or
  missing `kind`, both work keys, `parallel`+`sequence` together, a schema on a
  `text` type, a tool without `tool`, a linguistic without `prompt` → parse
  error.
- **Contracts:** entry + output **mandatory for every agent** — the full triples
  (`as`/`type`/`schema`), strict symmetry, no exceptions (even composites
  declare `output_schema`); `input_type`/`output_type` decide where a value
  lives (text/json/binary; text has no schema); schemas validate at the
  boundary (rule 9).
- **`input_as`:** reserved words are forbidden as a read root; every read starts
  from a declared alias.
- **Terse call vocabulary:** a tool `parameters` value is **exactly one of** a
  plain dotted path (a producer reference) or a literal; there is no
  `{from:}`/`{value:}`/`{default:}` wrapper; the default lives in the code's
  signature and is never written.
- **Chain-wide resolution:** a dotted path resolves against the whole preceding
  chain in the node's scope (`input_as` of the encapsulating composite or
  `output_as` of any earlier child), not only the immediate predecessor;
  `.path` must exist in the producer's `output_schema`; static type
  compatibility.
- **Composition is contract compatibility, not exact subset:** a consuming
  step's entry contract must be satisfiable by the producer's output (the fields
  it consumes exist with the promised types); the step that produces only
  `{body}` cannot feed a step whose contract demands `{url}`.
- **Coherence:** tool `input_schema` ⊆ the registered code signature (checked at
  load); linguistic template `{var}`s ↔ `input_schema` (all used, all
  declared); linguistic `output_schema` enforced at runtime.
- **Reuse:** definitions are source-agnostic; `pattern: <name>` at the usage
  site; the same agent may appear more than once in a flow **by position**
  (distinguished by `current_index`), unless inside its own definition (cycle →
  infinite recursion, rejected); a use satisfies the used agent's entry contract
  (subset of declared properties, `required` covered or defaulted, extras =
  load error).
- **Encapsulation:** interior opaque; `output_as` unique per scope; composition
  cycles rejected at catalog load.
- **Composite output (no `emit:`):** how a composite combines its children's
  results into its declared `output_as`/`output_schema` is **its
  implementation**; there is no "last child renamed" and no
  `emit:` map. Parallel children bind only from the composite `input_as` (serial
  dependencies nest as `sequence` inside a branch).
- **`main`:** root capability (submittable, seeds the flow in level 1 with
  `end_of_level_queue` = the final-result queue), reusable mid-DAG; no effect on
  contracts or the calling mechanism.
- **Load-time composability:** every invalid spec fails at load (LEG-071).

## Interface

- The YAML shape above, plus the validation matrix (R-3 fixture set).

## Acceptance criteria

From `docs/PLAN.md` (LEG-010), reworked for S1:

- A fixture translating two representative composite patterns into S1 YAML
  loads and validates: (a) a `sequence` reusing a tool node and a linguistic
  node; (b) a `parallel` with two branches.
- A prompt with `{input_var}` variables fills from the entry contract aliases;
  a `{var}` not declared in `input_schema` is a load error.
- A tool `parameters` dotted path resolves against any earlier producer in the
  chain (a 3-step chain where the last step reads the first step's output
  validates; a path to an undeclared alias/path is a load error).
- The contracts are **mandatory**: a node missing `input_as`/`input_type`/
  `input_schema` or `output_as`/`output_type`/`output_schema` is rejected.
- Reuse: the same agent definition used in two composites validates in both; a
  use that fails to satisfy the used agent's entry contract or adds an
  undeclared key is rejected; repeated identical steps only chain when
  contract-compatible.
- Coherence: a tool whose `input_schema` does not match its registered
  signature; a linguistic with an unused/undeclared prompt variable; and a
  linguistic output that violates its declared `output_schema` at runtime —
  all produce detectable errors (load-time or rule-9 visible).
- Encapsulation/cycles: duplicate `output_as` in one scope and composition
  cycles are rejected at load.

## Tests

- Contract tests (red first, R-3 loader): S1 fixtures (two composites),
  chain-wide dotted-path resolution, reuse, branch-exclusive matrix,
  mandatory-contract matrix, coherence checks (tool signature vs
  `input_schema`; linguistic prompt variables), composite output via
  implementation, parallel dependency rule (bind only from entry), duplicate
  `output_as`, cycles — all validated against the schema; linguistic runtime
  `output_schema` enforcement via MockLLM.

## Validation case

- Two in-repo example composites, re-expressed in the S1 shape (R-2/R-4
  conformance fixtures), plus the 3-step chain-reuse fixture above.

## Definition of done

- All acceptance criteria met by running checks (`ruff`, `pytest`, `pyright`).
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.
