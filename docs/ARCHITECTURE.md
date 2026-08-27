# legio — Architecture

## 0. Principles

- **Polling only.** Never callbacks or push, neither inside a node nor between
  nodes.
- **BeaverDB local per node** is the only shared memory between processes of the
  same node. No broker, no central database.
- **Atomic agents.** Each agent decides using only its message and the flow
  token; there is no central engine driving them.
- **Composition is a DAG over instances.** Two occurrences of the same pattern
  (`B, B`) are two independent tasks (two messages).
- **The flow moves through messages in queues and frames in boards**, never
  through process-resident state.
- **Scale = replicas of the same agent** (pool); **federation = nodes sharing
  agents**.
- **Retry is a field** (`next_run_at`, `attempts`), not a mechanism.
- **Capability = a registered agent**; a tool is the internal resource backing
  it.
- **Domain knowledge lives 100% outside legio**: in patterns (YAML data) and in
  the tool registry injected by the consumer.

## 1. Layers

```
External API      mini-manager (submit/status) + FastAPI
Federation        catalog · resolver · work-item HTTP · outbox
Runtime           worker/crew · pools · reaper
Agents            linguistic · tool · sequence · parallel  (+ base, registry)
Flow              FlowToken (DAG + position + return) · call-frames
Patterns          YAML → PatternSpec → pydantic models (compile-time)
Primitives        queue · board · lock  (beaver, transparent)
```

## 2. Substrate (primitives)

- **Queue** — persistent priority queue per agent; `push` / `lease` / `ack` /
  `pop`; `next_run_at` schedules retries with no scheduler.
- **Board** — persistent dict per scope: `blackboard:{node}:{task_id}`
  (inputs/outputs), `frames:{agent}:{task_id}` (call-frames),
  `semaphore`, `results:{task_id}`, `catalog`, `outbox`, `tasks` (state for the
  mini-manager).
- **Lock** — TTL + `renew`; it is the *task lease*. If a replica dies, the lease
  expires and the item becomes reclaimable.
- **Messages** — `ExecutionRequestMessage` (starts/deposits a step) and
  `ExecutionResultMessage` (returns). The message type discriminates in the dual
  queue.

## 3. FlowToken — the contract that moves everything

Fields: `route_pattern_names` (the concrete DAG of this leg), `current_index`
(position), `ultimate_return_agent_id` (where to return), `origin_node_id`
(author node), `root` (root marker), `task_id` (public).

- **Who builds it**: the composite agent that starts a leg concretizes its DAG
  and inserts it into the token. If it is the root, it sets `root=True` and
  `ultimate_return_agent_id = client:{task_id}`.
- **"Is it final?" is derived from position**, not from a flag: last step means
  delivery (internal: to the parent; root: to the client).
- It is a CPS-style continuation: *what am I (my pattern), where am I, where am
  I going, to whom do I return*.

## 4. Agent types

```
atomic:
  ├─ linguistic  → lingo (LLM → structured pydantic output)
  └─ tool        → tool registry (concrete deterministic op, local or remote)
composite:
  ├─ sequence    → one-by-one; advances current_index
  └─ parallel    → the only join point; dual queue + call-frame
```

- **Common base** (what truly abstracts all agents): `run()` = polling loop with
  lease + heartbeat; `submit()`; `pool_size` replicas share the same queue; the
  input/output contract (`ExecutionRequest/ResultMessage` + `output_as`) is
  identical for every agent.
- Orchestration cannot tell a linguistic agent apart from a concrete one — only
  the internal resource differs.

## 5. The Tool

- **Definition**: an opaque, substitutable execution resource. It does not know
  about agents or queues; only `input_schema`/`output_schema` (pydantic).
- **Declaration**: an atomic tool pattern declares `tool_type`,
  `input_mapping`, `output_as`, `tool_config`. Several patterns may share a
  tool; each is its own agent/queue, the resource is shared guarded by a
  per-tool concurrency semaphore.
- **Runtime (ToolAgent)**: resolves `tool_type` against the node's tool
  registry (loaded at worker startup), validates inputs, executes (async or
  blocking via `to_thread`), writes into the blackboard under `output_as`, and
  completes with an `ExecutionResultMessage`. On failure there is no output;
  retry/DLQ is decided by the orchestration (lease / `next_run_at` /
  `attempts`), never by the tool.
- **lingo is bounded to linguistic agents.** Concrete agents never pass through
  it. lingo's tool-calling is reserved for a future agentic path where the LLM
  chooses a tool — not the deterministic case.

## 6. Roles: Starting vs Capability (orthogonal to atomic/composite)

- The **catalog registers agents by name**; `starting` is a registration flag =
  a public entry point of the node. Any agent (atomic or composite) may be a
  starting agent.
- **Starting agent**: its parent is the client. It receives work from the API,
  which acts as a *synthetic parent* (stages inputs and builds the root token).
  The only contract differences: `root=True` and
  `ultimate_return_agent_id = client:{task_id}` — on completion it deposits into
  `results:{task_id}` instead of re-depositing to any agent.
- **Capability**: only invoked by another agent through a queue deposit; returns
  to the parent. A composite delegated to another node is likewise just a
  routable agent with the same fan-in contract.

## 7. Task lifecycle

1. Client calls the API → **mini-manager**: creates `task_id`, registers state,
   stages inputs, deposits `ExecutionRequestMessage` into the starting agent's
   queue.
2. The starting agent (root) takes the message, concretizes the root token and
   walks its flow.
3. Composite: concretizes its sub-DAG; sequence chains; parallel fans out (each
   child's dual queue + call-frame in a board).
4. Atomic: lingo if linguistic, tool registry if concrete.
5. Each child returns an `ExecutionResultMessage`; the parallel fans in
   (dedupe by DAG path, not by agent name), merges the call-frame and continues.
6. Final step → delivery: internal = deposit into `ultimate_return`; root =
   `results:{task_id}`.
7. The client polls `status(task_id)` → mini-manager reads boards. No
   in-memory handles: everything is a board.

## 8. Failure and resilience

- **Lease with heartbeat**: a live replica renews the item's lock; if it dies,
  the lease expires and the item is reclaimable (re-queue).
- **Reaper**: detects expired leases and re-queues; after `attempts` max → DLQ.
  Retry policy lives in `next_run_at`/`attempts`, never in sleeps.
- **Tolerant parallel**: waits for all children; a child failure yields a final
  result with error / partial content according to the pattern's policy.

## 9. Federation between nodes (local-first, symmetric)

- Each node has **its own beaver** and **its own catalog**. The roster is
  **derived from its capacity**: a node registers an atomic because it
  implements its tool; a composite if it depends only on servable agents (local
  or reachable).
- **Nodes are symmetric peers — no roles.** There is no orchestrator/provider
  distinction. Any node may act as *author* (triggers work, owns results) and as
  *acceptor* (executes delegated work), depending on the task. Same codebase,
  different roster and starting agents via configuration only.
- **Starting agents are entry points** of their own node: only the node's own
  mini-manager invokes them. They are not delegable; delegation applies to
  capability agents.
- Because agent resolution happens *before* deposit (in the author, against the
  catalog), an acceptor's workers never receive work for a pattern they do not
  serve.
- **Contract**: a step that needs an absent local agent may be delegated to a
  peer that registers it: a work-item (agent name + inputs) goes over HTTP → is
  deposited into the acceptor's queue → executed (atomic or a whole sub-DAG) →
  the result exits via **outbox**, consumed by the author via **polling**
  (write-before-ack; at-least-once documented).
- The **author owns the result**; the acceptor executes and returns. Work-item
  lease/heartbeat give tolerance to an acceptor's outage.
- **Interfaces are versioned**: the catalog declares each agent's interface and
  `schema_version`; the author validates the interface on POST (4xx on
  mismatch). Only configured peers (`federation.peers`) are reachable (see
  Security).

## 10. Security — two coarse levels, two secrets

**Principle**: legio provides coarse access control at two separated levels, each
with its own token and blast radius; granular authorization (users, roles,
tenants, limits) is the application's layer on top of the node.

**Level 1 — nodes talking to nodes.** One **federation token**, the same value
in every node of the federation ("if you know the key, you're in"). Every
federation endpoint (`/catalog`, `/work-items/{agent}`, `/outbox/*`,
`/health`) requires `Authorization: Bearer <federation_token>`. Delegation only
between explicitly configured peers (`federation.peers` allowlist). Setup is
configuration, not a handshake.

**Level 2 — systems using a node.** Each system registered on a node gets its
own **client token** (`api.clients`), individually revocable: if one system has
problems, only its token is invalidated, the others keep working. The
mini-manager API (`submit`/`status`) requires a client token;

```yaml
api:
  clients:
    voicinha-mobile: { token: <t1>, agents: [idea, to_do] }  # restricted
    invoice-bot:     { token: <t2> }                         # all by default
```

- **Default granularity**: a client token without a restriction may access all
  starting agents; listing `agents` restricts it.
- **Task ownership**: every task is tagged with its `client_id`; `status` and
  results are only readable with the token of that `client_id`.

**A token of one level never grants the other; a single middleware enforces
the endpoint → token map.**

**Hook for the consumer**: the node is embedded in an application. The app may
wrap or replace the auth middleware (e.g. user login on top of the client
token) for granular control.

**Out of scope for legio** (operational/application layers): TLS termination
(reverse proxy), token rotation policy, rate limiting, mTLS, RBAC, audit
trails. TLS is required in production; tokens are secrets rotated by the
operator.

**Threat model accepted**: compromised client → revoke its token (blast radius =
one system); compromised node → rotate the federation token in all nodes.
Internal state (queues, boards, beaver) is local to the node and never served
over the network.

## 11. Patterns (YAML)

- `main` = starting agents (entry points); `atomic` + `composite` =
  capabilities. `output_schema` → pydantic model at compile time; `output_as` =
  result namespacing; `input_mapping` = which blackboard keys feed a step.
- Load is **fail-fast** with **cascade invalidation**: a pattern with an invalid
  dependency is deactivated along with everything that depends on it
  transitively. A dry-run validator ships with it.

## 12. Dependency map (see docs/DEPENDENCIES.md)

| Capability | Library |
|---|---|
| Queues/boards/locks | `beaver-db` |
| LLM / linguistic agents | `lingo-ai` |
| Types/validation/config | `pydantic` (+ `pydantic-settings`) |
| API + federation endpoints | `fastapi` + `uvicorn` |
| HTTP client (tools + nodes) | `httpx` |
| Patterns YAML | `pyyaml` |
| CLI | `typer` |
| Tests | `pytest`, `pytest-asyncio`, `respx`, `MockLLM` |

## 13. Deliberate exclusions

Broker, Redis/central DB, workflow engine, scheduler library, callbacks, vector
store, castor (outdated against current beaver), session layer, in-memory
handles, and "pattern instances" with their own identity — two `B`s are two
tasks.