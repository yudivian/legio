# LEG-010 — Patterns YAML schema (S1)

- **Status:** REVISED 2026-08-31 (S1 — one agent spec; supersedes the v1 CLOSED
  contract of the same name)
- **Rasante:** R-1 (contract)
- **GitHub issue:** #4
- **Source:** `docs/PLAN.md` (LEG-010)
- **Depends on:** H1–H4 findings in `docs/VALIDATIONS/single-node-model.md`;
  the S1 design thread (session addenda, JOURNALS 2026-08-30 md end + 2026-08-31)

## Goal

Define the v2 (S1) YAML schema for patterns. Patterns are **YAML data** (rule
7) defining **agents**: one single agent specification shared by every agent
(`atomic`|`composite` × `tool`|`linguistic`|`sequence`|`parallel`), with
mandatory symmetric entry/output contracts, a single reference vocabulary
(`{from: alias.path}` | literal | omitted), binding at the usage site
(`parameters`/`bind`), chain-wide composability verification, reuse of any
definition by `pattern:` + `bind:`, and `main` as a root capability. The full
normative statement lives in `docs/AGENT_LIFECYCLE.md` §4.10.

## Scope

- **In scope:** the one agent spec (§4.10.1); branch-exclusive structural
  enforcement (no inference); mandatory symmetric contracts with
  `input_as`/`output_as` (the anti-convention rule, §4.10.2); the single
  reference vocabulary and chain-wide resolution (§4.10.3); interior ↔
  contract coherence (tool ↔ code signature S2; linguistic prompt variables ↔
  `input_schema`; linguistic `output_schema` enforced at runtime) §4.10.4;
  reuse of every definition by `pattern:` + `bind:` and encapsulation
  (§4.10.5); composite output (`emit:`) and parallel dependency rule
  (§4.10.6); `main` as root capability not position (§4.10.7); load-time
  composability verification (§4.10.8).
- **Out of scope:** the resource contract in code (S2, incl. tool
  input/output schemas and tool signature); config/registry + policy (S3);
  message envelope (S4); materialization artifacts (queue names, compiled
  pydantic models, derived identities); the `output_schema` mini-grammar (S5,
  defined by LEG-072 compilation semantics); the loader (LEG-021), dry-run
  validator (LEG-071).

## Contract & design

### The one agent spec (§4.10)

```yaml
type: atomic | composite
kind: tool | linguistic | sequence | parallel
name: <id>
description: <text>                     # optional
main: bool                              # optional; root capability, NOT position

input_as: <alias>                       # entry contract — MANDATORY (no magic word)
input_type: text | json | binary
input_schema:                           # mandatory only when input_type: json (S5)

output_as: <alias>                      # output contract — MANDATORY
output_type: text | json | binary
output_schema:                          # mandatory only when output_type: json (S5)

tool: <registered-tool-name>            # interior: kind: tool
prompt: "<template with {var}>"         # interior: kind: linguistic
children: [...] + emit: {}              # interior: kind: sequence | parallel

# usage site (inside a composite's children)
- pattern: <any-agent-name>
  bind: { <var>: {from: <producer>.<path>} | <literal> }
```

### Rules (normative subset)

- **Discriminators:** `type`/`kind` cross-validated; branch-exclusive fields
  (a tool branch never has `prompt`, etc.); atomic kinds exclusive; crossed or
  missing `kind`, both work keys, `type: parallel` → parse error.
- **Contracts:** entry + output **mandatory for every agent**; `input_type`/
  `output_type` decide where a value lives (text/json/binary; text has no
  schema); schemas validate at the boundary (rule 9).
- **`input_as`:** reserved words are forbidden as a read root; every read starts
  from a declared alias.
- **Reference vocabulary:** `{from: <alias>.<path>}` | literal | omitted. One
  mechanism, no positional role.
- **Chain-wide resolution:** `{from:}` resolves against the whole preceding
  chain in the node's scope (`input_as` of the encapsulating composite or
  `output_as` of any earlier child), not only the immediate predecessor;
  `.path` must exist in the producer's `output_schema`; static type
  compatibility.
- **Coherence:** tool `input_schema` ⊆ the registered code signature (S2,
  checked at load); linguistic template `{var}`s ↔ `input_schema` (all used,
  all declared); linguistic `output_schema` enforced at runtime.
- **Reuse:** definitions are source-agnostic; `pattern:` + `bind:` at the usage
  site; a `bind` satisfies the used agent's entry contract (subset of declared
  properties, `required` covered or defaulted, extras = load error).
- **Encapsulation:** interior opaque; `output_as` unique per scope; composition
  cycles rejected at catalog load.
- **Composite output:** sequence output = last child's deposit (or `emit:`);
  parallel output always via `emit:`; parallel children bind only from the
  composite `input_as` (serial dependencies nest as `sequence` inside a branch).
- **`main`:** root capability (submittable, returns to the client), reusable
  mid-DAG; no effect on contracts or binding.
- **Load-time composability:** every invalid spec fails at load (LEG-071).

## Interface

- The YAML shape above, plus the validation matrix (R-3 fixture set).

## Acceptance criteria

From `docs/PLAN.md` (LEG-010), reworked for S1:

- A fixture translating two representative composite patterns into S1 YAML
  loads and validates: (a) a `sequence` reusing a tool node and a linguistic
  node, with `emit:` on the composite output; (b) a `parallel` with `emit:`.
- A prompt with `{input_var}` variables fills from the entry contract aliases
  via `bind`; a `{var}` not declared in `input_schema` is a load error.
- `{from: producer.path}` resolves against any earlier producer in the chain
  (a 3-step chain where the last step reads the first step's output
  validates; a bind to an undeclared alias/path is a load error).
- The contracts are **mandatory**: a node missing `input_as`/`input_type`/
  `input_schema` or `output_as`/`output_type`/`output_schema` is rejected.
- Reuse: the same agent definition bound in two composites with different
  sources validates in both; a `bind` that fails to satisfy the used agent's
  entry contract or adds an undeclared key is rejected.
- Coherence: a tool whose `input_schema` does not match its registered
  signature; a linguistic with an unused/undeclared prompt variable; and a
  linguistic output that violates its declared `output_schema` at runtime —
  all produce detectable errors (load-time or rule-9 visible).
- Encapsulation/cycles: duplicate `output_as` in one scope and composition
  cycles are rejected at load.

## Tests

- Contract tests (red first, R-3 loader): S1 fixtures (two composites),
  chain-wide `{from:}` resolution, reuse with different binds, branch-exclusive
  matrix, mandatory-contract matrix, coherence checks (tool signature vs
  `input_schema`; linguistic prompt variables), `emit:` composition, parallel
  dependency rule (bind only from entry), duplicate `output_as`, cycles —
  all validated against the schema; linguistic runtime `output_schema`
  enforcement via MockLLM.

## Validation case

- Two in-repo example composites, re-expressed in the S1 shape (R-2/R-4
  conformance fixtures), plus the 3-step chain-reuse fixture above.

## Definition of done

- All acceptance criteria met by running checks (`ruff`, `pytest`, `pyright`).
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.