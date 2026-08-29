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
- **`TaskManager`** — the **mini-castor task engine** (submit, status, workers
  draining a queue, scheduling by `next_run_at`). It is the **executor of
  facts**: it is what actually creates workers, starts/stops polling, dispatches
  work. It is **blind to the domain and to the AgentRegistry** — it only knows
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

- **Action** — what the `Runtime` asks the `TaskManager` to do (imperative: create
  a worker, stop polling, close dispatch).
- **Fact** — the reality that results in the world (a worker exists and polls its
  queue; a queue dispatch is closed). It is **provoked/administered by the
  `TaskManager`**, but it is the *reality itself*, not the TaskManager's output.
- **Record** — what the `AgentRegistry` stores, **after** the fact occurred
  (posteriori mirror). Never before.
- **Operation** — what the `Runtime` exposes (create_class, enable_class, ...);
  it is exactly *action → fact → record*.

So the `Runtime` is the **translator** between two languages: it asks the
`TaskManager` for *actions* (in task language) and then tells the `AgentRegistry`
which *records* to store (in catalog language). The `TaskManager` never knows the
AgentRegistry; the `AgentRegistry` never knows the TaskManager; only the `Runtime`
knows both and translates.

There is no central scheduler: replicas (instances) poll their own queue over
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
- Governed by the **AgentRegistry** (existence reflected in the live catalog)
  and materialized by the **TaskManager** at the **Runtime**'s direction (§0/§6).

### 1.2 Instance (a replica / worker)

- A concrete copy that runs and **polls** the class's queue.
- An instance exists *in the catalog* only because a **worker was actually
  materialized** (by the `TaskManager`, at the `Runtime`'s request) and the fact
  was then recorded in the `AgentRegistry` (§0, registration-is-a-mirror). There
  is no "instance supervisor" — the `Runtime` is what decides and orchestrates
  materialization/scaling over the type's queue.

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

| Verb | **Class** (type) | **Instance** (replica) |
|---|---|---|
| **create** | define the type + its queue | a replica is born; it polls the class's queue (requires the class to exist) |
| **enable** | open entry: accepts new items; pending work is processed | the replica resumes / starts polling |
| **disable** | close entry: does not accept new items; **keeps draining** pending work (policy A) | the replica stops polling (pauses); its class and queue are untouched; other replicas keep running |
| **destroy** | **armageddon:** removes the class + its queue + **all** its instances | the replica dies (that instance only) |

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

### 4.5 Destroy here, and what is not destroyed

- **Destroying an instance** only removes that replica. Class, queue, and other
  replicas persist. If it was the last instance, the class becomes disabled
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

By default, destroying all instances of a class only disables it (it persists);
the destructive armageddon (removing the class entirely) is the explicit,
separate operation above.

### 4.7 The YAML and the local cache (confirmed)

- **Creating / re-creating a class is always driven by its YAML spec.**
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
| `record_class(spec, kind, queue, deps, state)` | The class entry once it was actually created. Bind kind; a class in the catalog reflects the real, materialized class. |
| `record_instance(class, instance_id, state)` | One instance per worker actually materialized by the `TaskManager` (never a pool_size promise). Count = sum of real facts. |
| `remove_instance(class, instance_id)` | An instance whose worker was actually destroyed. |
| `remove_class(name)` | A class whose spec/queue were actually destroyed (armageddon). |
| `set_class_state(name, enabled\|disabled)` | A state change that actually took effect. |
| `cache_spec(name, yaml)` | The YAML, once the class was actually created (→ §4.7 cache). |

**Queries (granular, read-only — the `Runtime` delegates these):**

| Query | Returns |
|---|---|
| `list_classes()` | existing class names and their state |
| `class_dependencies(name)` | the class's direct dependencies |
| `class_dependents(name)` | the class's direct dependents (inverse of the graph) |
| `class_state(name)` | the class's state (existence + activity) |
| `list_instances(class_name)` | the class's instances and their state |
| `get_cached_spec(name)` | the cached YAML for `recreate_class` |

**Idempotence (no-op, never raises on these):**
- Recording a class/instance that already exists → **no-op**.
- Removing a non-existent class/instance → **no-op**.

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
legio agent destroy-class <name> [--mode drain|now]    # Runtime.destroy_class
legio agent create-instance <class> [--count N]        # Runtime.create_instance
legio agent destroy-instance <class> [--count N]       # Runtime.destroy_instance

legio agent list-classes                               # Runtime → registry (read)
legio agent class-deps <name>                          # Runtime → registry (read)
legio agent class-dependents <name>                    # Runtime → registry (read)
legio agent class-state <name>                         # Runtime → registry (read)
legio agent list-instances <class>                     # Runtime → registry (read)
```

The CLI is a thin wrapper over the **Runtime** — no new logic. Idempotence follows
the registry (create of existing / destroy of non-existent → "ok", no-op). Plain
text output by default.

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
| DELETE | `/agent/class/{name}` | `{mode: drain\|now}` | `destroy_class` |
| POST | `/agent/class/{name}/instance` | `{count}` | `create_instance` |
| DELETE | `/agent/class/{name}/instance` | `{count}` | `destroy_instance` |
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

---

## 5. Flows (states explicit at every step)

Conventions: class state = existence + activity; instance state = existence +
activity; "polls/drains" = an enabled replica consuming its class's queue.

**Who does each flow (all of §5):** every mutation flow follows the same split —
the **Runtime** (public face) exposes and orchestrates; it asks the **TaskManager**
to perform the real fact (materialize/destroy a worker, start/stop polling,
close/remove a queue dispatch); and **only after** that fact is confirmed it asks
the **AgentRegistry** to **record it** (§0, registration-is-a-mirror). The state
tables below describe the resulting transitions; they happen *after* the fact,
never before. Reads ("verify the class exists") always go to the `AgentRegistry`.
There is **no** separate "instance supervisor" — materialization/scaling is the
Runtime's orchestration over the TaskManager.

### 5.1 Create instance
Precondition: the class exists. Bringing up an instance does **not** by itself
enable the class (enablement comes from dependencies satisfied + having
instances, §4.2/§4.4); instances of a disabled class are born disabled.

| # | Action | Class | Instance |
|---|---|---|---|
| 1 | Verify the class exists | created (enabled or disabled) | — |
| 2 | Create the replica (binds to the class's queue) | unchanged | `created / disabled` |
| 3 | If the class is enabled, enable it → starts polling; else it stays disabled | unchanged | `created / disabled` or `created / enabled` |
| 4 | (corollary) having instances is a precondition for the class being enabled, but does not enable it on its own | unchanged | — |

How: **Runtime** → `TaskManager` materializes a worker (fact) → on success **Runtime** → `AgentRegistry` records the instance (posteriori).

**No instance supervisor** — the Runtime orchestrates this (§5 convention).

### 5.2 Create class
Precondition: the class does not exist. Creation takes `pool_size` as a
parameter and evaluates dependencies; it does **not** create dependencies in
cascade.

| # | Action | Class | Instances / Queue |
|---|---|---|---|
| 1 | Register the spec in the catalog, bind kind, resolve dependencies | `created / disabled` | — |
| 2 | Create the type's queue | `created / disabled` | queue created (accepts nothing while disabled) |
| 3 | Evaluate dependencies (all exist and are enabled?) and `pool_size` | (see below) | — |
| 4 | If all dependencies satisfied and `pool_size > 0`: create (enabled) instances | `created / enabled` | instances created / enabled |
| 5 | Else (a dependency missing/disabled, or `pool_size == 0`): born disabled; instances, if any, born disabled | `created / disabled` | instances, if created by pool, `created / disabled` |

How: **Runtime** → for each worker of the pool, asks the **TaskManager** to
materialize it (fact, one at a time) → on each success **Runtime** → **AgentRegistry**
`record_instance` + `cache_spec` (posteriori). The catalog count is the **sum of
real facts**, never a pool_size promise.

### 5.3 Enable instance
Precondition: the instance exists and is disabled.

| # | Action | Class | Instance |
|---|---|---|---|
| 1 | Resume the replica's polling | unchanged | `created / enabled` |

How: **Runtime** → **TaskManager** resumes the worker's polling (fact) → on
success **Runtime** → **AgentRegistry** `set_instance_state` (posteriori).

### 5.4 Enable class
Precondition: the class exists and is disabled. Enabling is a **conscious**
operator action. If the class's dependencies are not satisfied, the operator
accepts the risk of a queue filling without anything processing it (§4.2).

| # | Action | Class | Instances |
|---|---|---|---|
| 1 | Check the class has at least one instance; if none, bring one up | — | created / disabled (then enabled) |
| 2 | Mark the class enabled (queue accepts new items again) | `created / enabled` | — |
| 3 | Instances resume / continue draining | unchanged | enabled, draining |

How: **Runtime** (conscious decision) → ensures a worker exists (via **TaskManager**,
recorded **posteriori** in **AgentRegistry**) → **TaskManager** starts polling of
the now-enabled instances → **AgentRegistry** `set_class_state(enabled)` after the
facts hold.

### 5.5 Disable instance
Precondition: the instance exists and is enabled.

| # | Action | Class | Instance |
|---|---|---|---|
| 1 | Pause the replica (release its lease safely, at-least-once) | unchanged | `created / disabled` |

How: **Runtime** → **TaskManager** pauses that single worker (release lease,
at-least-once; fact) → on success **Runtime** → **AgentRegistry**
`set_instance_state(disabled)` (posteriori). Unlike disable-class, here **one
specific worker is stopped**.

### 5.6 Disable class (policy A)
Precondition: the class exists and is enabled.

| # | Action | Class | Instances |
|---|---|---|---|
| 1 | Mark the class disabled (queue stops accepting new items) | `created / disabled` | — |
| 2 | Instances keep draining the pending work | unchanged | enabled, draining (not paused) |
| 3 | Cascade-disable dependents (those that reference it) | dependents become `created / disabled` | — |

How (policy A): **Runtime** → **AgentRegistry** `set_class_state(disabled)` →
**TaskManager** **closes the dispatch** of the class's queue (stops accepting new
items) but **does not destroy the workers** (they keep draining) → for each
dependent (transitive), **AgentRegistry** marks it disabled and **TaskManager**
closes its dispatch, workers still draining. **disable ≠ destroy**: disable
closes entry, never kills workers.

### 5.7 Destroy instance
Precondition: the instance exists.

| # | Action | Class | Instance |
|---|---|---|---|
| 1 | Terminate the replica (release worker and lease) | unchanged | `does not exist` |
| 2 | (corollary) if it was the last instance, the class becomes disabled | `created / disabled` | — |

How: **Runtime** → **TaskManager** destroys that worker (fact) → on success
**Runtime** → **AgentRegistry** `remove_instance` (posteriori); if it was the last
instance, `set_class_state(disabled)`.

### 5.8 Destroy class (armageddon)
Precondition: the class exists. Always in hot. Parameter `now` or `drain`.

| # | Action | Class | Instances |
|---|---|---|---|
| 1 | Resolve parameter (`drain`: wait until queue empty; `now`: proceed) | unchanged | unchanged |
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
proceeds) → **TaskManager** destroys every worker of the class and removes the
queue's dispatch (facts) → on success **Runtime** → **AgentRegistry** `remove_instance`
(all), destroys the queue record, and `remove_class` (the YAML stays in the
Registry's cache) → cascade-disable dependents (AgentRegistry marks + TaskManager
closes their dispatch; workers keep draining). **Down (dependencies) is never
touched.** Irreversible.

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
  materializes / destroys workers, starts / stops polling, opens / closes queue
  dispatch. It does not know that a task is "the agent lifecycle", and it never
  knows the DAG.

The `TaskManager` holds the worker/machine reality; the `AgentRegistry` is its
posterior mirror; the `Runtime` is the decision point between them.

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
workers idle and the node standing. The catalog holds all dependency information
(classes, instances, DAGs and states), so the full graph is known. The node is
brought up **by CLI or programmatically** (the Runtime is the entry point); the
bootstrap runs the ordering below against the loaded catalog.

Consistent with registration-is-a-mirror, **nothing is recorded before it
happens**: each entry enters the initial catalog/cache only after the fact (the
worker was actually materialized / the spec was actually read) is confirmed.

1. **Runtime** loads the source specs (classes + pool of each).
2. Build the **topological order** of the dependency graph (leaves first, then
   the classes that depend on them, etc.).
3. For each class in that order: **Runtime** → **TaskManager** materializes its
   workers one at a time; on each success **Registry** records the instance and,
   once the class is up, records the class entry and **caches its YAML**
   (initial cache). (`pool_size` is the *intent*; the catalog reflects the *real*
   materialized count — never a promise.)
4. Because each dependency is created (enabled) before its dependents, the
   enable-by-dependencies rule (§4.2) is satisfied naturally → dependents are
   created enabled.
5. Anything whose dependencies are not satisfied stays disabled and is visible
   in the catalog (its workers, if any, are recorded but stay disabled).
6. A dependency cycle breaks the order → detected and resolved (rejected /
   flagged).
7. **Runtime** → **TaskManager** starts the workers' idle polling and the
   heartbeat.

**Result:** the **initial catalog state** plus the **initial YAML cache** exist in
the `AgentRegistry`; workers are idle; **no business task has been started**
(a task only begins when a work item enters the starting agent's queue, Flows
B/C in the execution model). The node is ready to receive submits.

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

1. **"Pending work" boundary (policy A):** what exactly is drained when a class
   is disabled — only items already enqueued at the moment of disabling, or also
   items currently under lease (mid-flight)? (`drain` destroys once "nothing is
   pending"; the precise boundary ties to this.)
2. **Destroy parameter default:** whether destruction defaults to `now` or
   `drain`, and how `drain` interacts with a queue that never empties.

### Open risks

1. **The lifecycle layer must not absorb the DAG / routing** — it governs only
   existence and lifecycle. This is the central design risk.
2. **A disabled class, never re-enabled, accumulates or leaks pending work** —
   mitigate eventually via DLQ / reaper (R-6).
3. **Two state levels (class + instance) must stay coherent** — prefer that
   instances read (derive) the class state rather than the registry coordinating
   each instance individually.
4. **"Polling" means the worker is scheduled / supervised** (reaper, not a busy
   loop — AGENTS.md rule 8), not a permanently active thread.

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
  - The agent that starts a leg concretizes and passes the DAG; atomic agents
    only advance by position in the passed token.
