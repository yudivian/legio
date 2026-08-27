# CONTRIBUTING — Methodology and development flow

This document is the methodology for building `legio`. Complement to
`AGENTS.md` (operational rules) and `docs/PLAN.md` (issues).

## 1. Model: vertical slices with dogfooding

Each increment = **one capability of `legio` + the real validation case that
exercises it** (first consumer: `voicinha`, in its own repository). Hard rule:
*a feature is not closed if there is no real case in green exercising it.*

Work order per rasante: write contracts/specs → agree them → implement →
validate → journal.

## 2. Contract-first, TDD

1. **Tests fix the contract first** (red), implementation second (green). The
   contract tests *are* the specification.
2. Substitutes in tests: LLM → `MockLLM` (lingo); tools → fakes / `respx`;
   beaver → temporary file; inter-node HTTP → `respx`.
3. CI never touches real networks or real LLMs.

## 3. Validation and dogfooding

- Inside `legio`, the **examples are tests** (they must not bitrot): a minimal
  fictitious domain exercising each rasante without depending on `voicinha`.
- `voicinha` depends on `legio` in editable mode during development; each
  `legio` release ships with semver and a `voicinha` case in green pinned to
  that exact version.
- "Done" for a rasante: written contract + contract tests + implementation +
  validation cases green + docs.

## 4. Git, CI and releases

- Short-lived branches + PR (trunk-based). Conventional commits. English, in
  code as in commits.
- CI runs: `ruff` lint, typecheck, full test suite. Test the resilience
  scenarios explicitly (lease expiry, reaper, priority, cascade invalidation,
  partial failure).
- Strict semver from `0.1`; changelog and tags per release; each release is
  justified by its validation case.

## 5. Contracts and documentation

- Contracts change **only in writing**: versioned documents under
  `docs/CONTRACTS/` plus an ADR for each change; changes go through reviewed
  PRs.
- Minimal docs: README, ARCHITECTURE, PLAN, DEPENDENCIES, JOURNALS, glossary,
  and a guide for consumers (how a domain adds tools + patterns).

## 6. Design rules (non-negotiable)

1. **Zero domain dependencies**: `legio` never imports or knows consumer tools
   or patterns; only interfaces (injected registry, YAML as data).
2. **No global state**: explicit configuration through a `Manager`/`Engine`
   object (explicit over implicit) → testable.
3. **Polling only**: the public API exposes no callbacks or events; nothing
   sleeps — it is a field (`next_run_at`).
4. **Messages and token immutable and typed** (pydantic), with `schema_version`.
5. **Errors are never silent**: visible in boards + result with error + DLQ;
   swallowing exceptions is forbidden.
6. **Namespacing of queues/boards** per scope (`legio:queue:<agent>`,
   `legio:board:<scope>:<key>`) so domains/nodes sharing a beaver do not
   collide.
7. **Concurrency**: locks with TTL + `renew`; per-resource semaphores; **only
   the reaper re-queues**; replicas never reach consensus through their own
   process state.
8. **Single domain extension point**: the tool registry. Everything else is
   closed.
9. **Strict validation**: startup with cascade invalidation — a broken YAML is
   rejected, not ignored.

## 7. Review checklist (per PR)

- Does it introduce domain or global state? → no.
- Does it have contract tests fixing behavior? → yes.
- Is the real validation case green? → yes, except foundation.
- Are errors visible and never swallowed? → yes.
- Docs/contract/ADR updated if a contract changed? → yes.
- Journal updated describing what was done and what ran? → yes.
- Naming semantic-informative, English only? → yes.