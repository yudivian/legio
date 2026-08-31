# Agent Lifecycle — dynamic loading and unloading of agents

Scope: how agent **classes** and agent **instances** are created, enabled,
disabled and destroyed, in a fully decoupled architecture.

This document is the authoritative design for the lifecycle of agents. It is
derived from the reference project `voice-notes-api` (used as the baseline) and
extends it with **dynamic** loading/unloading, which the reference does not
have. The vocabulary is deliberately fixed: **create / enable / disable /
destroy**, only — no other verbs such as "down"/"up"/"load"/"unload".

> Design note (AGENTS.md rule: decoupling is a hard rule). The manager never
> decides the DAG nor the routing. The agent that starts a leg concretizes and
> passes the DAG. The `AgentRegistry` governs only **existence and lifecycle**
> (create/enable/disable/destroy) as a *posterior mirror of facts* — never the
> DAG, never routing, and never the materialization itself (that is the
> `TaskManager`'s, orchestrated by the `Runtime`; see §0 and §6).

---

## 0. Decoupled roles: Runtime vs AgentRegistry vs TaskManager vs beaver vs lingo

`legio` keeps five independent layers that never know one another:

- **`Runtime`** — the only layer with initiative, and the **public face** of the
  lifecycle. It decides operations, exposes them (CLI / HTTP / programmatic),
  orchestrates the other two, and **records facts after they happen**. It never
  executes agent work itself. Its functions are detailed in §6.
- **`AgentRegistry`** — the **memory of the node's agent state at runtime**. It
  owns (a) the **live catalog** — the state of classes/instances/dependencies —
  and (b) the **runtime cache of YAML specs** (§4.7). It is a **mirror of facts**:
  every entry is written **after** (never before) the corresponding fact
  occurred, so the catalog never reports something that does not exist. It never
  materializes or executes anything.
- **`TaskManager`** — the **mini-castor task engine** (submit, status, task
  executors draining the task queues, scheduling by `next_run_at`). It is the
  **executor of facts**: the Runtime asks it for an *action* in task language,
  and it is what actually executes the fact — e.g. running the callable that is
  the internal loop of an agent the Runtime decided to create (§6.1). It is
  **blind to the domain and to the AgentRegistry** — it only knows
  "run this task / stop this task", never that a task is "the agent lifecycle".
  Implemented in `legio` itself (see `docs/DEPENDENCIES.md`, "Excluded on
  purpose"); its functional reference is `castor-io`. The `TaskManager` scales
  the Runtime and the Registry.
- **`beaver`** — the single substrate (boards, priority queues, locks). All of
  the above sit on it.
- **`lingo`** — LLM + structured output (the role the reference's `argo` played
  for LLM interaction).

**The regulating principle — registration is a mirror of facts.** Nothing is
registered before it happens. The vocabulary is strict:

- **Action** — what the `Runtime` asks the `TaskManager` to do, in task
  language (imperative: run/stop/pause a task — bring up an agent's loop, stop
  it). Opening/closing the class entry is **not** an Action: the entry
  gate is the Runtime's own submission-side check (§5.6, §6.1).
- **Fact** — the reality that results in the world (an agent's own loop runs and
  polls its class's queue; a task runs; a task is paused/cancelled). It is
  **provoked/administered by the `TaskManager`**, but it is the *reality itself*,
  not the TaskManager's output.
- **Record** — what the `AgentRegistry` stores, **after** the fact occurred
  (posteriori mirror). Never before.
- **Operation** — what the `Runtime` exposes (create_class, enable_class, ...);
  it is exactly *action → fact → record*.

So the `Runtime` is the **translator** between two languages: it asks the
`TaskManager` for *actions* (in task language) and then tells the `AgentRegistry`
which *records* to store (in catalog language). The `TaskManager` never knows the
AgentRegistry; the `AgentRegistry` never knows the TaskManager; only the `Runtime`
knows both and translates.

There is no central scheduler: instances (agents) poll their own queue over
beaver autonomously, and task scheduling is a field (`next_run_at`) — never
callbacks or sleeps (AGENTS.md rule 8). Nothing here uses Redis or any broker.

---

## 1. Two levels

Every operation lives at one of two levels:

### 1.1 Class (the agent type / pattern)

- The **definition**: the pattern spec (`PatternSpec`, derived from YAML).
- Its **queue**, named after the type (e.g. `summ`).
- Its **kind binding**: the concrete agent type (`linguistic` / `tool` /
  `sequence` / `parallel`) derived from the spec.
- Its **dependencies** (from the spec): a composite references other classes by
  name (its `sequence` / `parallel`). Depended-on classes are the class's
  **dependencies**; classes that reference it are its **dependents**.
- Governed by the **AgentRegistry** (existence reflected in the live catalog);
  its instances are brought up by the **TaskManager** executing the fact at the
  **Runtime**'s direction (§0/§6).

### 1.2 Instance (a concrete agent of the class)

- A concrete agent that runs and **polls** the class's queue with its own
  internal loop (LEG-023).
- An instance exists *in the catalog* only because an **agent was actually
  brought up** (the Runtime decided it, the TaskManager executed the fact at the
  Runtime's request) and the fact was then recorded in the `AgentRegistry` (§0,
  registration-is-a-mirror). There is no "instance supervisor" — the `Runtime`
  is what decides and orchestrates.

---

## 2. The four verbs

Only these verbs, applied to both levels:

| Verb | Meaning |
|---|---|
| **create** | bring into existence something that did not exist |
| **enable** | make active / operational (re-open, resume) — reversible |
| **disable** | make inactive / suspended, without removing existence — reversible |
| **destroy** | remove entirely — irreversible |

---

## 3. Two axes of state

For both a class and an instance:

1. **Existence:** `does not exist` → `created` → (destroyed).
2. **Activity** (only meaningful if it exists): `enabled` / `disabled`.

Verbs map to the axes:

- **create:** `does not exist` → `created` (policy decides if born enabled or
  disabled).
- **destroy:** `created` → `does not exist` (irreversible).
- **enable:** `created & disabled` → `created & enabled`.
- **disable:** `created & enabled` → `created & disabled`.

---

## 4. Verb matrix (Class and Instance)

| Verb | **Class** (type) | **Instance** (agent) |
|---|---|---|
| **create** | define the type + its queue | an agent is brought up; it polls the class's queue (requires the class to exist) |
| **enable** | open entry: accepts new items; pending work is processed | the agent resumes / starts polling |
| **disable** | close entry: does not accept new items; **keeps draining** pending work (policy A) | the agent stops polling (pauses); its class and queue are untouched; other agents keep running |
| **destroy** | **armageddon:** removes the class + its queue + **all** its instances | the agent dies (that instance only) |

### 4.1 Policy A — "disable the class" (confirmed)

Disabling a class means:

- The class's **queue stops accepting new items**.
- Its instances **keep processing the pending work** until drained.
- Re-enabling reopens entry. Nothing is lost, nothing is paused.

Disabling a class does **not** pause its instances; they keep draining.

### 4.2 Enable-by-dependencies (creation rule, confirmed)

A class is enabled at creation **only if all of its dependencies exist and are
enabled**. Otherwise (a dependency is missing or disabled) the class is created
**but disabled**.

- Creating a class does **not** create its dependencies in cascade (see §7
  dependencies). Only the existing ones are evaluated.
- Enabling a class whose dependencies are missing/disabled is a **conscious**
  operator decision, never automatic: it risks a queue that fills without
  anything processing it.
- Instances inherit the state of their class: if the class is born disabled, its
  instances are born disabled too.

### 4.3 Pool as a creation parameter (confirmed)

Creating a class takes the **pool size (number of instances) as a parameter**
(default `pool_size=1`):

- `.pool_size > 0` and dependencies satisfied → class is enabled, instances
  created (enabled).
- `.pool_size == 0` → class is born **disabled** (consistent with the corollary,
  §4.4), even if dependencies are satisfied. `0` is the explicit way to create a
  class without instances (leaving it to be brought up later).
- A class born disabled for dependency reasons: its instances, if any, are born
  disabled (ready to be enabled once dependencies are satisfied).

"Create class" is separated from "bring up instances": the bootstrap does both
(passing each class's `pool_size`), the dynamic operator may do either.

### 4.4 Corollary — no instances ⇒ class disabled (confirmed)

- **If a class has no instances, the class is automatically disabled** (there is
  nobody to process).
- **Brings up instances does not by itself enable a class**: a class is enabled
  only when its **dependencies are satisfied (§4.2)** and it **has instances
  (§4.3)**. A class disabled for dependency reasons stays disabled even after
  the first instance is brought up (its instances are born disabled too).
- **Option 2 — bringing up instances of a disabled class is allowed.** Instances
  may be created of a disabled class, to **drain / scale** the pending work.
  New instances of a disabled class receive no new work; they only help drain
  what is already queued (consistent with policy A).
- **Destroying all instances ≠ destroying the class.** The class keeps existing
  (spec + queue) but is disabled. Useful for dynamic resource management:
  bring up many instances, let them drain/work, destroy them, the class rests
  disabled; bring up instances again later to re-activate. The definition, queue
  and spec persist — nothing needs to be re-defined.
- **Effective state is derived on reads (safety net).** The stored state is a
  mirror of what the `Runtime` recorded; but `class_state()` / `list_classes()`
  report the **effective state**: `enabled` only if stored `enabled` **and** the
  class has at least one recorded instance. This makes the "no instances ⇒
  disabled" corollary hold atomically on the read side (no crash window between
  `remove_instance` and `set_class_state`, §5.7), while the stored record keeps
  the explicit decision for future re-enabling: bringing up instances does
  **not** auto-enable (the stored state stays `disabled` until the operator
  enables). Dependencies are **not** part of this derivation — an operator's
  conscious enable with missing deps (§4.2) stays enabled.

### 4.5 Destroy here, and what is not destroyed

- **Destroying an instance** only removes that agent. Class, queue, and other
  agents persist. If it was the last instance, the class becomes disabled
  (still exists).
- **Destroying a class** is the armageddon of that type: it removes the class
  (spec), its queue, and **all** its instances, irreversibly. It is an explicit,
  separate, hard operation — distinct from "destroying all instances".

### 4.6 Destroy parameter: `now` / `drain` (confirmed)

Destruction always happens **in hot** (never in the bootstrap) and is always an
armageddon of the class. It takes a parameter:

- **`now`** — everything goes immediately: spec, queue, all instances, including
  any pending / in-lease items. The operator must be conscious of the loss.
- **`drain`** — the class is destroyed **once nothing is pending** (it waits for
  its queue to drain before removing spec + queue + instances). Preserves no-loss.
  **`drain` is the default.**

**`drain` semantics (confirmed 2026-08-30):** the queue stays in place until it is
empty; the guarantee is that it **does not grow** (the entry gate is closed, so
nothing new enters); if everything works normally it will eventually finish. A
**large timeout** guards the wait as a safety valve (`drain` and the timeout must
be human-scale, not a busy loop — rule 8): on the (unexpected) expiry the
operation **fails visibly** (rule 9) leaving the class untouched, and the operator
decides what to do (fix the class, or escalate to `now`). A `drain` that never
terminates is therefore always an operator-visible problem, never a silent hang.

By default, destroying all instances of a class only disables it (it persists);
the destructive armageddon (removing the class entirely) is the explicit,
separate operation above.

### 4.7 The YAML and the local cache (confirmed)

- **Creating / re-creating a class is always driven by its YAML spec** (the
  spec shape is defined in §4.10).
- The **runtime YAML cache is owned by the `AgentRegistry`** (§0): it keeps the
  spec of every class that has actually been loaded. If a class is destroyed
  and the node has **not** been restarted, it can be re-created from the cached
  YAML (the operator does not have to re-supply it). The cache is lost when the
  node restarts; the bootstrap **rebuilds the initial state and the initial
  cache** from the catalog.
- The cache is a **mirror of facts**: a spec enters the cache only **after** its
  class was actually created (the fact "the spec was read/loaded" happened), and
  it **persists across `destroy_class`** (the class leaves the live catalog but
  its spec stays cached so it can be recreated).
- **Disabling does not touch the YAML** — the spec stays (in cache / catalog).
- **Destroying removes the class** (queue + instances + active spec), **but the
  YAML is kept**, so someone can re-create it later.
- The cache holds **definitions only** — it does **not** record *why* a class
  was disabled (the "reason / by whom"), which is not stored at all.
- **Which operation requires the YAML:** only **create / re-create**. Disable and
  destroy take only the class name (plus the `now`/`drain` parameter for
  destroy); they never use the YAML.

### 4.8 The `AgentRegistry` (confirmed) and who does what

The `AgentRegistry` owns the **runtime state of agent classes** — the live
catalog and the runtime YAML cache (§0, §4.7). It is the **posterior mirror**:
entries are written only after the corresponding fact occurred. It does **not**
materialize, run or destroy anything — that is the `TaskManager`'s job,
orchestrated by the `Runtime`. Its operations fall into two groups:

- **The `Runtime` exposes every lifecycle operation** (it is the public face,
  §6). For each, it (1) asks the `TaskManager` to perform the real action, and
  (2) only after success asks the `AgentRegistry` to **record the fact**.
- **The `AgentRegistry` records and answers queries**; it never initiates.

**Registry operations (all posteriori — the fact must have occurred first):**

| Operation | What the `AgentRegistry` records (posteriori) |
|---|---|
| `record_class(name, kind, *, dependencies, queue, state)` | The class entry **after** its queue was created (the class's existence fact, §5.2). Bind kind. Unknown kind → error before anything is recorded. A class in the catalog reflects a real, materialized class. |
| `cache_spec(name, yaml)` | The YAML, **once**, at `record_class` time (→ §4.7 cache). Never per-instance. |
| `record_instance(class_name, instance_id, *, state)` | One entry per agent actually brought up **and running** — the agent's own identity, recorded after the fact; never a `pool_size` promise. Count = sum of real facts. |
| `set_class_state(name, enabled\|disabled)` | A class state change that actually took effect. Unknown class → error (rule 9). |
| `set_instance_state(class_name, instance_id, enabled\|disabled)` | An instance activity change that actually took effect (the pause/resume transitions, §5.3/§5.5). Unknown instance → error (rule 9). |
| `remove_instance(class_name, instance_id)` | An instance whose agent was actually destroyed (confirmed terminal, §5.7/§5.8). |
| `remove_class(name)` | The class entry of a class whose spec and queue were actually destroyed (armageddon); the YAML stays cached (§4.7). |

**Identity and ordering rules (mirror):**
- `instance_id` is the **agent's own identity** (the concrete agent of the
  class), **never** a TM `task_id`: an agent is not a task. The task that
  executes the fact (the agent's loop, §6.1) has its own `task_id`; the catalog
  records the agent, not the task — there is **no** 1:1 instance ↔ task identity
  mapping, and no duplicated field.
- Within a create, the order is fixed:
  **queue created (Runtime fact) → `record_class` + `cache_spec` → per agent:
  brought up & confirmed running (TM) → `record_instance`** (§5.1/§5.2).
  A class is never recorded without a queue; an instance is never recorded
  before its agent is running; `record_instance` never precedes
  `record_class` (no orphan instances).
- **Confirmation is a TM read.** Every mutation waits for the TaskManager's
  observable state — `status(task_id)` `running` for a create; `tm_control`
  `run`/`pause` for enable/disable; a terminal state for destroy — before the
  `record_*`/`set_*`/`remove_*` call. The Runtime translates task-language facts
  into catalog records.

**Queries (granular, read-only — the `Runtime` delegates these):**

| Query | Returns |
|---|---|
| `list_classes()` | existing class names and their **effective** state (§4.4) |
| `class_state(name)` | the class's **effective** state — existence + activity (`None` if it does not exist) |
| `class_dependencies(name)` | the class's direct dependencies |
| `class_dependents(name, *, transitive=False)` | the class's direct dependents (inverse of the graph), or the **transitive** upward set (the cascade of §7) |
| `dependencies_satisfied(name)` | all direct dependencies exist and are enabled — read helper for the create/enable rules (§4.2/§4.3) |
| `list_instances(class_name)` | the class's instances and their state |
| `get_instance(class_name, instance_id)` | one instance record (does it exist, and in what state?) |
| `get_cached_spec(name)` | the cached YAML for `recreate_class` |

**Idempotence and error policy:**
- Recording a class/instance that already exists → **no-op**.
- Removing a non-existent class/instance → **no-op**.
- `set_class_state` / `set_instance_state` on a non-existent entry → **error**
  (rule 9): a `set` on something that does not exist would record a false fact;
  the `Runtime` shields the operator with a "not found / no-op" reply before
  calling.
- `cache_spec` is an **upsert**.

**Kind binding:** a fixed map `{"linguistic", "tool", "sequence", "parallel"}`
→ concrete agent class. An unrecognized kind → clear error before anything is
recorded.

#### CLI (public face = the Runtime)

The CLI talks to the **Runtime**, not to the registry directly. Each command is a
Runtime high-level operation that performs the fact (via the `TaskManager`) and
then records it (in the `AgentRegistry`), posteriori (§0).

```text
legio agent create-class <spec.yaml> [--pool N]        # Runtime.create_class
legio agent recreate-class <name> [--pool N]           # Runtime.recreate_class
legio agent enable-class <name>                        # Runtime.enable_class
legio agent disable-class <name>                       # Runtime.disable_class
legio agent destroy-class <name> [--mode drain|now] # Runtime.destroy_class (default: drain)
legio agent create-instance <class> [--count N]        # Runtime.create_instance
legio agent destroy-instance <class> [--count N]       # Runtime.destroy_instance
legio agent enable-instance <class> <id>               # Runtime.enable_instance
legio agent disable-instance <class> <id>              # Runtime.disable_instance

legio agent list-classes                               # Runtime → registry (read)
legio agent class-deps <name>                          # Runtime → registry (read)
legio agent class-dependents <name>                    # Runtime → registry (read)
legio agent class-state <name>                         # Runtime → registry (read)
legio agent list-instances <class>                     # Runtime → registry (read)
```

The CLI is a thin wrapper over the **Runtime** — no new logic. Idempotence follows
the registry (create of existing / destroy of non-existent → "ok", no-op).
`recreate_class` is **create driven by the cached YAML** (`get_cached_spec`):
precondition — the class does **not** exist (it was destroyed earlier, §4.7).
Plain text output by default.

#### HTTP API (public face = the Runtime)

The HTTP surface also exposes the **Runtime**. Read operations delegate to the
`AgentRegistry`; mutation operations perform the fact (via `TaskManager`) and
then record it (Registry), posteriori.

| Method | Path | Body | → Runtime |
|---|---|---|---|
| POST | `/agent/class` | `{spec}`(YAML), `{pool}` | `create_class` |
| POST | `/agent/class/{name}/recreate` | `{pool}` | `recreate_class` |
| POST | `/agent/class/{name}/enable` | — | `enable_class` |
| POST | `/agent/class/{name}/disable` | — | `disable_class` |
| DELETE | `/agent/class/{name}` | `{mode?: drain\|now}` (default: `drain`) | `destroy_class` |
| POST | `/agent/class/{name}/instance` | `{count}` | `create_instance` |
| DELETE | `/agent/class/{name}/instance` | `{count}` | `destroy_instance` |
| POST | `/agent/class/{name}/instance/{id}/enable` | — | `enable_instance` |
| POST | `/agent/class/{name}/instance/{id}/disable` | — | `disable_instance` |
| GET | `/agent/class` | — | `Runtime→registry: list_classes` |
| GET | `/agent/class/{name}/dependencies` | — | `Runtime→registry: class_dependencies` |
| GET | `/agent/class/{name}/dependents` | — | `Runtime→registry: class_dependents` |
| GET | `/agent/class/{name}/state` | — | `Runtime→registry: class_state` |
| GET | `/agent/class/{name}/instance` | — | `Runtime→registry: list_instances` |

Responses are JSON. `201` on a real create/recreate; `200` on enable/disable and
queries. Idempotent like the registry: create of an existing class → `200` with a
note ("already exists", not `409`); destroy of a non-existent class → `200`
("not found, no-op"). Real errors (invalid kind, broken YAML) → `400`/`422`.

Also a thin wrapper — no extra logic.

### 4.10 The pattern schema (S1) — one agent spec, contracts, binding, reuse

A pattern is **YAML data** (rule 7) defining **agents** — the only first-class
notion of this design. There is **one** agent specification shared by every
agent (tool, linguistic, sequence, parallel); the kinds differ only in their
**interior** — what executes — never in their contract or in how they are wired
into a flow. The pattern **declares**; the resource (the code) **defines** its
contract (S2); config/registration (S3) binds name → implementation + policy.
The shape language inside the schemas (S5) supports
string/number/integer/boolean/array/object, `required`, `properties` and
`default`. The reference model's flat merge + `output_as` namespacing is
inherited as *read semantics*, but S1 replaces its implicit names with declared
aliases (§4.10.2) and its `inputs` projection / `audio_path` hardcode with
`parameters`/`bind` (§4.10.4). No consumer domain, code name or resource
contract appears in a pattern (rule 7).

#### 4.10.1 The schema (one specification for every agent)

```yaml
type: atomic | composite                      # root discriminator; exactly these two
kind: tool | linguistic | sequence | parallel # second, explicit, cross-validated
name: <id>
description: <text>                           # optional
main: bool                                    # optional; root capability, NOT position

# Entry contract — MANDATORY for every agent
input_as: <alias>                             # names the incoming payload space; no magic word
input_type: text | json | binary
input_schema:                                 # mandatory only when input_type: json (S5)
  type: object
  required: [<var>]
  properties:
    <var>: {type: string|number|integer|boolean|array|object, default: <literal>}

# Output contract — MANDATORY for every agent
output_as: <alias>                            # names the deposited payload space
output_type: text | json | binary
output_schema:                                # mandatory only when output_type: json (S5)

# Interior — exactly one, by kind
tool: <registered-tool-name>                  # kind: tool
prompt: "<template with {var}>"               # kind: linguistic
children: [ ... ]                             # kind: sequence | parallel
emit: { <field>: {from: <child-output>} }     # composite (optional; see 4.10.6)

# At the usage site (inside a composite's children)
- pattern: <any-agent-name>
  bind:
    <var>: {from: <producer>.<path>} | <literal>
```

**Branch-exclusive fields, structurally enforced.** `type: atomic` → `kind:
tool` or `kind: linguistic`; `type: composite` → `kind: sequence` or `kind:
parallel`. A tool branch cannot carry `prompt`; a linguistic branch cannot
carry `tool`; atomic kinds are exclusive (a step is either a tool or a prompt —
never both). Crossed `type × kind`, a missing `kind`, both work keys on one
atomic, or `type: parallel` (a reference-model bug) are rejected at parse.
Discriminated union — nothing is inferred by key presence.

#### 4.10.2 Mandatory symmetric contracts

Every agent — atomic or composite, tool, linguistic, sequence or parallel —
declares an **entry contract** (what it consumes: `input_as`, `input_type`,
`input_schema`) and an **output contract** (what it produces: `output_as`,
`output_type`, `output_schema`). `input_type`/`output_type` ∈ {text, json,
binary} decide **where a value lives**: text → the payload *is* the string;
json → values are fields of the declared schema; binary → the payload is the
blob (or its reference). A `text` payload has no schema. Schemas validate at
the boundary (rule 9), and the contracts make **composability checkable**: a
use's `bind` must satisfy the used agent's entry contract, and every agent's
output becomes a producer for its scope's chain.

**`input_as` is the anti-convention rule.** The first segment of every read is
a **declared alias** — a node's `input_as` or a producer's `output_as` — never
a reserved word such as "input". Because it is mandatory and declared, a loader
can resolve and verify every reference; an unresolved alias or path is a **load
error** (rule 9), never a silent convention.

#### 4.10.3 One reference vocabulary

A value source is exactly one of: `{from: <alias>.<path>}` (a producer in
scope), a **literal** (a value fixed in this pattern/call), or **omitted** (the
code's default / the declared `default`). There is no other read mechanism and
no positional role: `{from:}` resolves against **the whole chain that precedes
the node in its scope** — the encapsulating composite's `input_as` or the
`output_as` of **any** earlier child of that scope, not only the immediate
predecessor. `.path` must exist in the producer's declared `output_schema`, and
the producer's output type must be statically assignable to the consuming
variable. Literal and omitted parameters need no producer. Failures are load
errors.

#### 4.10.4 Interior and its coherence with the contract

- **Tool.** `tool: <name>` selects a registered implementation (S2/S3);
  `parameters:` binds **each parameter of the executed code's signature** to a
  source of §4.10.3 (`{from:}` against the chain, a literal, or omitted for the
  code's default). The tool's `input_schema` must be a valid subset of the
  registered signature — checked at load against the registry (S2), so the
  declared contract can never be fiction.
- **Linguistic.** `prompt:` is a template whose `{var}` placeholders **are**
  the entry contract: every template variable must exist in `input_schema` and
  every declared variable must be used or flagged. The output contract is a
  declaration, not a code signature — it must be **enforced at runtime**
  (structured output / validation against `output_schema`), or the contract is
  a promise that nothing checks (rule 9).
- **Composites.** `children:` are references (`pattern: <name>`) or full inline
  nodes (must carry `name`). Their contract comes from their children and
  `emit:` (§4.10.6).

#### 4.10.5 Reuse belongs to every definition, and encapsulation

Any agent — atomic or composite — is defined once, **source-agnostic**, and is
**wired at the usage site**: a composite references it with `pattern: <name>`
and binds each required input variable to a source of its own chain (§4.10.3).
The same definition used in different composites can bind the same variables to
different producers; the interior never changes. A `bind` keeps its used
agent's contract: keys are a subset of its declared properties, `required`
covered unless a `default` exists, extras are load errors; the used agent's
`output_as` becomes a producer for later siblings.

Encapsulation: an agent's interior is **opaque** — a consumer sees only its
`output_as`/`output_schema`, never its internal names (those are checked
against the agent's own scope). **`output_as` is unique within its scope**
(collision = load error). Composition **cycles** (an agent transitively
containing itself) are detected at catalog load and rejected.

#### 4.10.6 Composite output

A sequence's output contract is the deposit of its **last** child, renamed to
its `output_as` — or an explicit `emit:` map when the output is composed from
more than one child or from a new shape:

```yaml
output_as: note_result
output_schema: {required: [summary], properties: {summary: string}}
emit:
  summary: {from: summarize.out}
```

A parallel's output is **always** declared through `emit:` (there is no "last
child"). Parallel children bind **only** from the composite's `input_as`; any
serial dependency between branches is expressed as a `sequence` nested inside a
branch (no hidden ordering, no races).

#### 4.10.7 `main` = root capability, not position

`main: true` marks an agent as a valid `submit` entry (token born root,
`ultimate_return_agent_id = client:{task_id}`). A `main` agent may also appear
in the middle of another DAG (`pattern: <name>`): there it executes its
functionality as part of the enclosing flow and advances, returning to the
client only when the flow started at it. A catalog may declare several `main`
agents. `main` never changes the contract or the binding mechanism.

#### 4.10.8 Checkable composability (redundancy against the silent)

Because every agent declares its entry and output contracts, the loader
verifies the catalog statically: every `bind`/`parameters` reference resolves
against a declared producer in the chain; every use satisfies the used agent's
entry contract with statically compatible types; `output_as` names are unique
per scope; interiors cohere with their contracts (vocabulary above); and there
are no cycles. A catalog with an invalid spec **fails at load** (rule 9;
LEG-071 dry-run) — nothing silently miswired ever runs.

---

## 5. Flows (states explicit at every step)

Conventions: class state = existence + activity; instance state = existence +
activity; "polls/drains" = an enabled agent consuming its class's queue.

**Who does each flow (all of §5):** every mutation flow follows the same split —
the **Runtime** (public face, the authority that creates/destroys/enables/
disables agents) exposes and orchestrates; it asks the **TaskManager** to
perform the real fact (bring up/destroy an agent, start/stop its loop); and
**only after** that fact is confirmed it asks the **AgentRegistry** to **record
it** (§0, registration-is-a-mirror). **Confirmation is a TM read** (§4.8) — every
mutation waits for the observable state (`status(task_id)` `running` on create;
`tm_control` `run`/`pause` on enable/disable; a terminal state on destroy) before
the `record_*`/`set_*`/`remove_*` call. The class **entry gate** is not a
TaskManager fact — it is the Runtime's own submission-side check against the
catalog (§5.6, §6.1). The state tables below describe the resulting transitions;
they happen *after* the fact, never before. Reads ("verify the class exists")
always go to the `AgentRegistry`.
There is **no** separate "instance supervisor" — bringing up agents is the
Runtime's orchestration over the TaskManager.

### 5.1 Create instance
Precondition: the class exists. Bringing up an instance does **not** by itself
enable the class (enablement comes from dependencies satisfied + having
instances, §4.2/§4.4); instances of a disabled class are born disabled.

| # | Action | Class | Instance |
|---|---|---|---|
| 1 | Verify the class exists (read) | created (enabled or disabled) | — |
| 2 | Bring up the agent: its own loop starts running on the class's queue; wait until `running` (TM read) | unchanged | agent running |
| 3 | Record the instance with the class's **effective** state — born `disabled` if the class is disabled (§4.2/§4.4); initial control `run` (enabled) or `pause` (disabled) | unchanged | `created / disabled` or `created / enabled` |
| 4 | (corollary) having instances is a precondition for the class being enabled, but does not enable it on its own | unchanged | — |

How: **Runtime** → `TaskManager` executes the fact (the callable that is the
agent's internal loop, §6.1) and confirms `status(task_id) == running` (TM read)
→ on success **Runtime** → `AgentRegistry` `record_instance(class, instance_id,
born_state)` (posteriori). If the agent never reaches `running` — nothing is
recorded (the mirror never reports an agent that was not actually brought up).

**No instance supervisor** — the Runtime orchestrates this (§5 convention).

### 5.2 Create class
Precondition: the class does not exist. Creation takes `pool_size` as a
parameter and evaluates dependencies; it does **not** create dependencies in
cascade.

| # | Action | Class | Instances / Queue |
|---|---|---|---|
| 1 | Create the type's queue (Runtime fact) | `created / disabled` | queue created (accepts nothing while disabled) |
| 2 | `record_class(name, kind, deps, queue, state)` + `cache_spec(name, yaml)` (posteriori, once) | `created / disabled` | — |
| 3 | Evaluate dependencies (all exist and are enabled?) and `pool_size` | (see below) | — |
| 4 | If all dependencies satisfied and `pool_size > 0`: per agent — bring it up, confirm `running`, `record_instance` (enabled) | `created / enabled` | instances created / enabled |
| 5 | Else (a dependency missing/disabled, or `pool_size == 0`): born disabled; instances, if any, born disabled | `created / disabled` | instances, if created by pool, `created / disabled` |

How: **Runtime** creates the type's queue (fact) → `record_class` + `cache_spec`
(posteriori to the queue, **once per class**) → for each agent of the pool, asks
the **TaskManager** to execute its fact (the agent's loop, one at a time) and
confirms `running` → on each success **Runtime** → **AgentRegistry**
`record_instance` (posteriori). The catalog count is the **sum of real facts**,
never a `pool_size` promise.

### 5.3 Enable instance
Precondition: the instance exists and is disabled.

| # | Action | Class | Instance |
|---|---|---|---|
| 1 | Resume the agent's loop | unchanged | `created / enabled` |

How: **Runtime** → **TaskManager** resumes that agent's loop
(`resume(task_id)`) and confirms `tm_control == run` (TM read; fact) → on success
**Runtime** → **AgentRegistry** `set_instance_state(enabled)` (posteriori).

### 5.4 Enable class
Precondition: the class exists and is disabled. Enabling is a **conscious**
operator action. If the class's dependencies are not satisfied, the operator
accepts the risk of a queue filling without anything processing it (§4.2).

| # | Action | Class | Instances |
|---|---|---|---|
| 1 | Check the class has at least one instance; if none, bring one up | — | created / disabled (then enabled) |
| 2 | Mark the class enabled (queue accepts new items again) | `created / enabled` | — |
| 3 | Resume **all** the class's instances | unchanged | enabled, draining |

Rule (§4.2/§4.3, symmetric): `enable_class` resumes **all** the class's
instances. The registry does not record *why* an instance was paused (§7), so an
explicit `disable_instance` of a single agent is a one-shot pause that the next
`enable_class` clears.

How: **Runtime** (conscious decision) → ensures an agent exists (via **TaskManager**,
confirmed `running`, recorded **posteriori** in **AgentRegistry**) → resumes
**all** instances (per-instance `resume`, `tm_control` `run`) → **AgentRegistry**
`set_instance_state(enabled)` for each + `set_class_state(enabled)` after the
facts hold.

### 5.5 Disable instance
Precondition: the instance exists and is enabled.

| # | Action | Class | Instance |
|---|---|---|---|
| 1 | Pause the agent (release its lease safely, at-least-once) | unchanged | `created / disabled` |

How: **Runtime** → **TaskManager** pauses that single agent's loop
(`pause(task_id)`, release lease, at-least-once) and confirms
`tm_control == pause` (TM read; fact) → on success **Runtime** → **AgentRegistry**
`set_instance_state(disabled)` (posteriori). Unlike disable-class, here **one
specific agent is stopped**.

### 5.6 Disable class (policy A)
Precondition: the class exists and is enabled.

| # | Action | Class | Instances |
|---|---|---|---|
| 1 | Mark the class disabled (queue stops accepting new items) | `created / disabled` | — |
| 2 | Instances keep draining the pending work | unchanged | enabled, draining (not paused) |
| 3 | Cascade-disable dependents (those that reference it) | dependents become `created / disabled` | — |

How (policy A): **Runtime** decides `disable_class`: from then on, its submit
path **rejects new items** against the catalog (the entry gate, §6.1) →
**AgentRegistry** `set_class_state(disabled)` records the fact → the agents are
**not touched** — they keep draining the pending work → for each dependent
(transitive), the Runtime gate applies and **AgentRegistry** marks it disabled,
agents still draining. **disable ≠ destroy**: disable closes entry, never kills
agents.

### 5.7 Destroy instance
Precondition: the instance exists.

| # | Action | Class | Instance |
|---|---|---|---|
| 1 | Terminate the agent (release its loop and lease) | unchanged | `does not exist` |
| 2 | (corollary) if it was the last instance, the class becomes disabled | `created / disabled` | — |

How: **Runtime** → **TaskManager** destroys that agent's loop (`cancel(task_id)`)
and confirms a terminal state (`failed(cancelled)` / `failed(executor_died)`)
(TM read; fact) → on success **Runtime** → **AgentRegistry** `remove_instance`
(posteriori); if it was the last instance, `set_class_state(disabled)` — and reads
report it via the **effective state** (§4.4) even across the two records.

### 5.8 Destroy class (armageddon)
Precondition: the class exists. Always in hot. Parameter `now` or `drain`
(**default: `drain`**, §4.6).

| # | Action | Class | Instances |
|---|---|---|---|
| 1 | Resolve parameter (`drain`: wait until queue empty, §4.6; `now`: proceed) | unchanged | unchanged |
| 2 | Destroy all its instances | unchanged | all `does not exist` |
| 3 | Destroy the queue | unchanged | — |
| 4 | Remove the spec from the catalog | `does not exist` | — |
| 5 | Cascade-disable dependents (they reference a destroyed class) | dependents become `created / disabled` | — |

Notes:
- **Down (dependencies) is not touched**: the classes this one depends on are
  never destroyed or disabled here, because others may depend on them.
- **Up (dependents)**: classes that reference the destroyed class are disabled
  (cascade, §7) — they remain existing but disabled, never destroyed by the
  cascade.

How: **Runtime** resolves `mode` (`drain` waits until queue empty; `now`
proceeds) → for each agent: **TaskManager** `cancel(task_id)` and confirm
terminal (fact) → **AgentRegistry** `remove_instance` (posteriori) → the Runtime
removes the queue and its entry gate and the **AgentRegistry** `remove_class`
(the YAML stays in the Registry's cache) → cascade-disable dependents (Runtime
gate + AgentRegistry `set_class_state(disabled)`; their agents keep draining).
**Down (dependencies) is never touched.** Irreversible.

---

## 6. Responsibilities (who owns what)

The lifecycle splits across the three layers described in §0:

- **`Runtime` (only layer with initiative, public face)** — decides every
  lifecycle operation, exposes it (CLI / HTTP / programmatic), and orchestrates
  the other two. For each mutation it asks the `TaskManager` to perform the real
  fact and, **only after success**, asks the `AgentRegistry` to record it
  (registration-is-a-mirror). It validates reads against the `AgentRegistry`.
  Functions: `create_class`, `recreate_class`, `create_instance`,
  `destroy_instance`, `enable_class`, `disable_class`, `destroy_class`,
  `enable_instance`, `disable_instance`, and the read queries.
- **`AgentRegistry` (posterior mirror, owner of the YAML cache)** — records the
  facts the `Runtime` confirms (classes, instances, state changes, specs in the
  cache) and answers the granular queries. It **never initiates, never
  materializes, never runs** anything. Governs only existence and lifecycle —
  **never the DAG or routing**.
- **`TaskManager` (executor of facts, blind to the domain)** — actually
  executes the fact, in task language: it runs the callable that is an agent's
  internal loop (creating an agent), pauses/resumes/cancels it. It does not know
  that a task is "the agent lifecycle", it never knows the DAG, and it is not
  involved in business submissions — the class entry gate belongs to the Runtime
  (§6.1).

The `TaskManager` holds the task/machine reality (the agent's life runs through
it); the `AgentRegistry` is its posterior mirror; the `Runtime` is the decision
point between them. An **agent is not a task**: the catalog records the agent by
its own identity; the TM task that executes its loop keeps a separate `task_id`
(§4.8).

**Invariant — no orphaned jobs (confirmed 2026-08-30).** A business task is
always traceable in the Runtime boards (`tasks` / `results`): it either reaches a
terminal state or stays visibly pending. The only deliberate-loss path is
`destroy_class --mode now`, which is explicit and operator-chosen (§4.6). There
must never be a job that exists nowhere and is seen by no one. **If an orphan
appears, that is a design error to fix — never a runtime condition to paper
over.**

### 6.1 The `TaskManager` — minimal task surface (design)

The `TaskManager` is the **executor of facts** (§0): a reduced, domain-free task
engine on beaver. It knows only **tasks** — a task is a `name` + `args/kwargs` +
a state + an execution time. It never knows agents, classes, agent queues,
patterns, the DAG, routing or the `AgentRegistry`. Its functional reference is
`castor-io`, reduced to what legio's lifecycle needs; it is **not** castor and
**not** an engine for business tasks (business `submit`/results stay in the
Runtime, `legio.manager`).

**What a task is (domain-free).** A task is identified by `task_id` (uuid). Its
record lives on the board `db.dict("tm_tasks")` and holds: `name`, `args`,
`kwargs`, `status`, `cancellable`, `next_run_at`, timestamps (`enqueued_at`,
`started_at`, `finished_at`), `result`, `error`, and the resilience fields
reserved for R-6 (`attempts`, `lease_expires_at`). Status is one of `pending |
running | success | failed | cancelling` (`cancelling` is the visible half-open
state of a cooperative cancel). Execution time is the `next_run_at` **field**
(rule 8 — no sleeps, no scheduler).

**Beaver footprint (all TaskManager-owned scopes):**

| Primitive | Scope | Role |
|---|---|---|
| dict | `tm_tasks` | task records (`task_id` → `TaskRecord`) |
| queue | `tm_scheduled` | task ids ordered by `next_run_at` (priority = timestamp) |
| queue | `tm_pending` | task ids due now (priority 0) |
| dict | `tm_control` | cooperative control per task: `run \| pause \| cancel` (TTL) |
| lock | `tm_lease:{task_id}` | execution lease (TTL + renew); a dead executor's lease expires and the task becomes stale to the reaper |

Result/error travel **inside the task record** — consumers poll
`status(task_id)`. There is no result queue: polling-only (rule 8).

**Surface.**

```
register(name, callable)                    # in-process: name → async fn | async generator
async submit(name, *args, *, next_run_at=None, **kwargs) -> task_id
async status(task_id) -> TaskRecord | None
async pause(task_id) / resume(task_id)      # disable ≠ destroy: non-terminal suspension
async cancel(task_id)                       # terminal, cooperative
```

- The **callable registry is in-process code**, never a board: it is the task
  executor's execution scope (castor's `_registry`); state — the authority of what
  happened — is always a board.
- The Runtime **registers the callables that are the agents' internal loops**
  (each agent's `AgentBase.run`, LEG-023). To the TM each is just a callable —
  it never sees what is inside, and the callable is **not** the agent: it is the
  vehicle through which the agent's life runs. The catalog records the agent by
  its own identity, with a separate `task_id` for the task executing its loop
  (§4.8) — never a 1:1 instance ↔ task identity.

**Task-executor algorithm.** A TM task executor is a polling loop over the task
queues:

```
1. tm_scheduled.peek() → get() the due head (next_run_at <= now) → dispatch
2. else tm_pending.get(block=False) → dispatch   (IndexError ⇒ nothing due; run() returns)
3. dispatch(task_id):
   a. acquire tm_lease:{task_id} (TTL; renew while running)
   b. status := running (+ started_at, lease_expires_at)
   c. cancellable? drive the generator, checking tm_control at each yield:
        run    → advance one step
        pause  → yield without advancing (lease kept; at-least-once)
        cancel → cancelling → failed(cancelled)
      not cancellable? await callable(*args, **kwargs)
   d. success + result | failed + error   (never silent, rule 9)
   e. release the lease
```

- **Reaper (`reap`)**: a task `running` whose `lease_expires_at` is stale is
  marked `failed(executor_died)` — the mirror must show when an agent's
  executor died. Lease-based **retry** (`attempts` → re-queue) and **DLQ** are
  R-6 (LEG-060/061/062); the fields exist already.
- **Multi-process concurrency**: several TM task executors (any process) drain
  the same queues; `get()` is destructive/atomic, so a task executes once; the
  lease arbitrates the reaper in crash windows.

**Lifecycle verbs → task language.** The TM executes these facts; the Runtime
decides them and records them in the `AgentRegistry` **after** each is confirmed
(registration-is-a-mirror):

| Runtime verb | TaskManager fact (task language) | Observable TM state | Registry record (posteriori) |
|---|---|---|---|
| create_instance | `submit(agent_loop, ...)` (the agent's internal loop, long-running, cancellable) | `running` | `record_instance` |
| destroy_instance | `cancel(task_id)` | `cancelling → failed(cancelled)` | `remove_instance` |
| disable_instance | `pause(task_id)` | `tm_control=pause` (loop yields; still exists) | `set_instance_state(disabled)` |
| enable_instance | `resume(task_id)` | `tm_control=run` | `set_instance_state(enabled)` |
| create_class (pool N) | N × `submit(agent_loop, ...)` | N tasks `running` | `record_class` + N×`record_instance` + `cache_spec` |
| destroy_class | N × `cancel(...)` | all tasks terminated | N×`remove_instance` + `remove_class` |

**What the TaskManager does NOT own** (decoupling boundaries):
- The **entry gate of a class queue** (what §0/§5.6/§5.8/§6 name "dispatch"):
  submitting into a disabled class is refused by the **Runtime** (it consults
  the catalog); business submits never pass through the TM. (Resolved — see §10,
  open decision 3.)
- The DAG, routing, delivery, results: all Runtime/agent concern.
- The AgentRegistry: the TM never records anything in it.

**Compliance (audit).** Polling-only / no sleeps (rule 8), scheduling as a field
(`next_run_at`); domain-free (rule 7 — names/states only, never agents); errors
never silent (rule 9 — `failed`+`error` visible, `failed(executor_died)`,
`cancelled`); everything is a board (rule 13 — callables are code, never
authority); logging with the implementation (rule 11); no instance supervisor
(the TM is executor only; the Runtime decides; the agent's internal cycle is the
callable's own — the agent is not a task, its identity lives in the catalog);
disable ≠ destroy (pause vs cancel); additive — the Runtime and
the agents are untouched. Implementation lands with the Runtime's lifecycle ops
(R-8), executed in task language by the TaskManager (§6.1).

---

## 7. Dependencies (from the YAML spec)

Dependencies come from the spec: a composite (`sequence` / `parallel`)
references other classes by name. These govern enable/disable/destroy behavior.

- **Create** evaluates its **dependencies (down)**: a class is created enabled
  only if all dependencies exist and are enabled; otherwise born disabled.
  Creation does **not** create its dependencies in cascade.
- **Disable / destroy** cascade over its **dependents (up)**: disabling or
  destroying a class disables the classes that reference it (recursively — a
  dependency cascade / chain of disablement). The cascade is **transitive
  upward**: if something depends on it, that dependent is disabled, and anything
  that depends on *that dependent* is disabled too (it will not be able to
  resolve). Dependents become `created / disabled`, never destroyed by the
  cascade.
- **Destroy does not touch down**: the classes a destroyed class depends on are
  left untouched, because others may depend on them.
- **Re-creating a class does not re-enable its dependents** automatically: the
  system does not record *why* a disablement happened (by whom: a cascade vs an
  explicit operator action), so restoring a class does not undo explicit
  decisions. Re-enabling dependents is an explicit operator decision, guided by
  the live catalog (§9), which exposes the dependency graph so the upward chain
  can be deduced.
- **Cycles** in the dependency graph (a class depends transitively on itself)
  break the topological order — they are detected and must be resolved (rejected
  / flagged) rather than silently looping.

## 8. Bootstrap — build the initial state and the initial cache

The bootstrap **constructs the initial state of the system and the initial
cache** in the `AgentRegistry` (§0). It does **not** "run tasks": it leaves the
agents idle and the node standing. The catalog holds all dependency information
(classes, instances, DAGs and states), so the full graph is known. The node is
brought up **by CLI or programmatically** (the Runtime is the entry point); the
bootstrap runs the ordering below against the loaded catalog.

Consistent with registration-is-a-mirror, **nothing is recorded before it
happens**: each entry enters the initial catalog/cache only after the fact (the
agent was actually brought up / the spec was actually read) is confirmed.

1. **Runtime** loads the source specs (classes + pool of each).
2. Build the **topological order** of the dependency graph (leaves first, then
   the classes that depend on them, etc.).
3. For each class in that order: **Runtime** creates its queue (fact) →
   `record_class` + `cache_spec` (once, posteriori to the queue) → **TaskManager**
   brings up its agents one at a time (each agent's own loop, §6.1), each
   confirmed `running` before the **Registry** records the instance
   (§5.2/§4.8 ordering). (`pool_size` is the *intent*; the catalog reflects the
   *real* count of agents actually brought up — never a promise.)
4. Because each dependency is created (enabled) before its dependents, the
   enable-by-dependencies rule (§4.2) is satisfied naturally → dependents are
   created enabled.
5. Anything whose dependencies are not satisfied stays disabled and is visible
   in the catalog (its agents, if any, are recorded but stay disabled).
6. A dependency cycle breaks the order → detected and resolved (rejected /
   flagged).
7. The agents are already running their own internal loops (each was brought up
   in step 3, §6.1); the node's task executors are up and drain the TM queues.

**Result:** the **initial catalog state** plus the **initial YAML cache** exist in
the `AgentRegistry`; agents are idle (nothing pending on their class queues);
**no business task has been started** (a task only begins when a work item
enters the starting agent's queue, Flows B/C in the execution model). The node
is ready to receive submits.

## 9. The live catalog (operator source of truth)

The catalog exposes classes, instances, DAGs and states (queues, enabled /
disabled, dependencies). The operator uses it to know what exists, what is
disabled and why, and to decide explicitly what to enable / re-enable / destroy.
No disablement-history is recorded; the live catalog is what guides decisions.

- **What the catalog exposes per class:** the class, its **direct dependencies**
  and its **dependents** (the inverse of the graph), its state, the instances it
  has, and the state of each instance. Exposed granularly via the queries in
  §4.8: `list_classes`, `class_dependencies`, `class_dependents`, `class_state`,
  `list_instances`.
- Exposing **dependents (the upward graph)** lets the operator deduce the
  cascade: when a class is disabled/destroyed, the whole transitive set of
  dependents is what got disabled, and re-enabling can walk that chain upward.
  (Even though the "by whom" is not recorded, the graph makes the candidates
  derivable.)

## 10. Open decisions and open risks

### Open decisions

1. **"Pending work" boundary / drain semantics (resolved 2026-08-30 by §4.6):**
   `now` destroys everything including **pending and in-lease** items (the
   operator consciously accepts the loss); `drain` waits for the queue to empty —
   in-flight leases keep running to completion, nothing new enters, and the
   drain completes. The queue does **not** grow, termination is eventual when
   things work, and a **large timeout** is the safety valve (visible failure on
   expiry — rule 9). No further boundary to decide.
2. **Destroy parameter default (resolved 2026-08-30):** the default is **`drain`**
   (`--mode`/`{mode}` optional in CLI/HTTP, §4.8; §5.8). `now` is the explicit
   escalation. A `drain` that never ends is an operator-visible problem, never a
   silent hang (large timeout → visible failure, §4.6).
3. **Entry gate / dispatch ownership (resolved 2026-08-30):** the class entry
   gate belongs to the **Runtime** — its submit path rejects new items against
   the catalog when the class is disabled. It is not a `TaskManager` fact (the
   TaskManager never sees business submissions, and there is no open/closed
   attribute on a beaver queue to "close"). §0/§5/§5.6/§5.8/§6 wording updated
   accordingly (reconciled thread 3).
4. **Lease reaper in the minimal TaskManager (resolved 2026-08-30):** the
   minimal TM includes the execution lease + the stale-lease →
   `failed(executor_died)` reaper. Without it the mirror would report a dead
   instance as alive — violates registration-is-a-mirror and rule 9. Retry
   (`attempts` → re-queue) and DLQ stay in R-6 (LEG-060/061/062).
5. **TaskManager scope names and placement (confirmed 2026-08-30):** module
   **`legio.taskmanager`**; class **`TaskManager`**; beaver scopes, all under the
   `tm_` prefix: `tm_tasks` (dict), `tm_scheduled` (queue), `tm_pending` (queue),
   `tm_control` (dict), `tm_lease:{task_id}` (lock). Normative in `legio.naming`
   (LEG-016) at implementation.

### Open risks

1. **The lifecycle layer must not absorb the DAG / routing** — it governs only
   existence and lifecycle. This is the central design risk.
2. **A disabled class, never re-enabled, accumulates or leaks pending work** —
   mitigate eventually via DLQ / reaper (R-6).
3. **Two state levels (class + instance) must stay coherent** — prefer that
   instances read (derive) the class state rather than the registry coordinating
   each instance individually.
4. **"Polling" means the agent's loop is scheduled / supervised** (reaper, not
   a busy loop — AGENTS.md rule 8), not a permanently active thread.
5. **The task executing an agent's loop can die outside any operator operation**
   (the agent's executor crashes → TM reaper marks `failed(executor_died)`),
   leaving a catalog instance that no longer exists and a class that *reads*
   `enabled` (or `disabled`) with zero live agents. The **effective state** read
   (§4.4) limits the damage — zero instances read as `disabled` — but the stale
   entry persists until an operator `destroy_instance`, or R-8 pooling
   reconciles/respawns it. Automatic reconciliation/respawn is **R-8 / LEG-080**
   (not part of this design).

---

## 11. Reference comparison

- From `voice-notes-api`: an `AgentFactory.create_all_pools` walks the compiled
  pattern catalog at boot and creates a pool per pattern, each pool being N
  replicas over the same `db.queue(pattern_name)`. Unloading / dynamic loading
  does **not** exist there.
- legio **improves** on this: the same catalog walk happens at boot, but agents
  can also be **created on the fly** (with their queue) and **destroyed** at
  runtime — without restarting the node — via the four verbs above.
- Additional legio improvements over the reference:
  - **Pool size is a creation parameter** (0 ⇒ born disabled), extending the
    reference's fixed `pool_size` per pattern.
  - **Dynamic lifecycle** governed by create / enable / disable / destroy,
    including a dependency cascade, enable-by-dependencies, and the live catalog
    as the operator's source of truth.
- Confirmed principles taken forward from the reference:
  - The **queue belongs to the type** (class), not to an instance.
  - Multiple instances of a type share and consume the **same** queue.
  - The agent that starts a task concretizes and passes the DAG; atomic agents
    only advance by position in the passed token.

---

## 12. Execution mechanics and the lifecycle × execution handshake

This section specifies the **runtime flow of a task** and how it meets the
class lifecycle (create / enable / disable / destroy). It is the execution
counterpart of §0-§8, and it is written so the decoupling rules cannot be
re-learned wrong: the flow is **forward-only (a DAG)**, state travels **in the
message**, and the only per-class data are a queue and (where relevant) a
gathering queue and a gate — never an accumulator "board".

### 12.1 Message-carried state: state lives in the messages, never in a board

The accumulated state of a task travels **inside the messages themselves**,
exactly as in the reference model (`voice-notes-api`):
an `ExecutionRequestMessage` carries `payload` (the inputs for the step) and
the flow token; an `ExecutionResultMessage` carries `output` (the partial
result of a child, or the error of a failed step). There is **no** board
that accumulates per-agent/task state out of the messages (see
`docs/JOURNALS/2026-08-30.md`, execution-mechanics thread); the message payload
is the state — polling-only, nothing central, nothing staged out-of-message for
later merge.

### 12.2 One inbox queue per class; every agent of the class polls it

- Every class has exactly **one inbox queue** (`legio:queue:<class>`); all of
  its agents (instances) poll and consume that same queue.
- Agents are **interchangeable, stateless** consumers of the unit of work the
  class knows; an agent learns *what to do, where it is, and whom to return
  to* **only from the message + token** it just consumed (CPS continuation,
  ARCH §3). There is no god agent, no per-task queue, no engine driving steps.
- The **agent's internal loop** (LEG-023, `AgentBase.run`) is the unit a
  brought-up agent executes per class: poll **one** due item from the class's
  inbox (`get(block=False)` → `IndexError` = idle, returns; rule 8) and process
  it, repeating until idle. Operational control (pause / cancel / shutdown)
  is checked **between dispatches** — never inside a step, and never by
  parking, leasing or task-ifying the loop. The loop is the agent's own, the
  vehicle of the fact the Runtime asks the TaskManager to execute; an agent is
  **not** a task and **not** a recorded TM identity (its identity lives in the
  catalog, §4.8).

### 12.3 Sequence is forward-only; parallel has a gathering queue

The model distinguishes the two composites *conceptually* (implementation may
collapse one physical queue with message-type dispatch — that is an
implementation detail, not the model):

- **Sequence.** Pure forward pass: nothing returns to the sequence itself. The
  last processor **deposits into the next class's queue**; if it is the final
  step of the route it deposits the result to `ultimate_return_agent_id`
  (or, for a root, the results board). **No gathering queue.**
- **Parallel.** Two queues in the model: the class **inbox** and a
  **gathering queue** for the fan-in of the branched tasks (§12.4). The second
  queue belongs to the parallel class, not to an individual task, not to a
  parent.

Both composites are themselves classes with their own queue/instances (§7,
dependencies); a composite is invoked like any capability agent — through its
inbox.

### 12.4 The flow: one `_advance_flow`, fan-out and fan-in

**Single advancement mechanism.** Every agent (atomic and composite) implements
the same continuation logic, forward-only over the route carried by the token:

```
for the current step (route[current_index]):
  next_index = current_index + 1
  if next_index < len(route_pattern_names):
      deposit an ExecutionRequestMessage into the next class's queue
  elif ultimate_return_agent_id:
      deposit an ExecutionResultMessage(output|error) to the return agent
  else:  # no return destination
      the LAST agent itself saves the final result (root → results board)
```

**Parallel fan-out.** A parallel instance pushes one child token per branch
(upto one route item, `ultimate_return_agent_id = the parallel class`): a child
is itself a task running over the child class's inbox. Fan-in returns land in
the parallel's **gathering queue** and are merged into the **message-carried
state** of the parent token (flat union, `output_as` for collisions — H3).
Completion of the last branch advances the parent token.

**Where does "am I finished" live?** In the per-class **gathering bookkeeping**
of the parallel (`state:parallel:<class>`, keyed by task, under a lock, as in
the reference), not in a frame/board accumulator and not in any central engine.
A sequence needs no such bookkeeping at all (§12.3).

**Failure and fan-in.** A child failure becomes an `ExecutionResultMessage`
with an `error` payload through the existing failure path (§7/ARCH §8, rule 9):
the parallel merges it (tolerant policy, R-6 refines) and the parent flow
continues or fails visibly. Exhausted attempts go to the DLQ (R-6). Errors are
never silent.

### 12.5 Handshake with the class lifecycle (deposit-time gate)

The one place execution and lifecycle meet is **deposit**: pushing work into
another class's queue. Rules (decoupled, local, no oracle):

1. **Nothing enters a non-enabled class** — neither a business submit (§6.1
   entry gate) nor an internal deposit by `_advance_flow`/fan-in. Enforcing at
   *consumption* is wrong: a disabled class keeps draining its pending work
   (policy A, §4.1/§4.6), so a message must never be allowed in.
2. **The gate is per-class data, not a central entity.** The class gate lives in
   one board (`db.dict("gates")`, keyed by class = `{state: enabled|disabled}`)
   and is written **only** by the Runtime (in the lifecycle ops) and **read** by
   any depositor (a submit or an internal task). This is the same mirror
   principle as the catalog — local, named, no central authority deciding
   routing.
3. **Destroyed class = cleared queue + no gate.** beaver auto-creates a queue on
   `put` and offers no queue-deletion API, so a `put` to a destroyed class would
   silently rebuild an orphan queue and make the class look alive. `destroy`
   **clears the class queue and removes its gate row**; once the gate is gone,
   every deposit to that class is **blocked at the gate** (step 2) — no global
   oracle is needed to "know" the class died, and a `put` failure must never be
   relied on as an existence signal.
4. **Race at the threshold is accepted.** A deposit can win the race against a
   concurrent `disable`/`destroy`; the item then drains with the queue (policy
   A). This is best-effort by design, never a leak: the no-orphans invariant
   (§6) holds because every deposited message is either processed, visibly
   failed, or drained.
5. **A blocked deposit is a visible failure** through the failure mechanism
   (§12.4): if the gate is closed at deposit time, the step fails with an
   `error` result to `ultimate_return_agent_id` (or failed task), never a silent
   no-op. **Exemptions**: a deposit whose target is a `client:{task_id}` root
   return, and an error-result deposit, always proceed regardless of the gate —
   a closed class keeps draining, and an error must always reach its return
   path.

### 12.6 Polling-only, fields not mechanisms (restated for execution)

- Retry is `next_run_at` (a field), never a sleep/delay in the flow.
- Idle is `get(block=False)` → `IndexError` → the instance loop returns.
- Scheduling/supervision of the instance loop is the TaskManager's (§6.1,
  §10 risks 3-5); the flow itself never sleeps, never loops waiting for a
  peer.
