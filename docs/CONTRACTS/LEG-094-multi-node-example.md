# LEG-094 — Multi-node example (3 symmetric nodes, domain-free)

- **Status:** DRAFT (awaiting maintainer approval)
- **Rasante:** R-9
- **GitHub issue:** #49
- **Source:** `docs/PLAN.md` (LEG-094)
- **Depends on:** LEG-090..LEG-093

## Goal
Proof R-9 in green: 3 symmetric nodes; author A triggers a 2-level flow that
delegates a capability to peer B (or C) via catalog + work-item + outbox, and
receives the final result — and B triggers A the same way (symmetric).

## Scope
- **In scope:** in-repo 3-node example, delegation round trip, symmetry.
- **Out of scope:** >3-node topology, real LLM/provider (fake tools suffice).

## Contract & design
- In-repo, domain-free: three nodes with complementary pattern/tool capacity
  (e.g. A holds the top-level flow + fake tool; B holds a delegatable
  capability; C stands idle as catalog witness).
- Author A: schema v1 patterns; step resolved remote (LEG-091) → deposited via
  LEG-092 → result via outbox LEG-093; final downstream step continues on A.
- Symmetry assertion: B triggering A works identically (no orchestrator).
- Single shared federation token (L1) per LEG-017 across A/B/C.

## Interface
- Full federation REST surface of all three nodes.

## Acceptance criteria
From `docs/PLAN.md` (LEG-094), verbatim:
- A triggers a 2-level flow that delegates a capability to B (or C) and
  receives the final result, all with the federation token; symmetric: B can
  trigger A the same way.

## Tests
- The 3-node example as a green integration test (real beaver, local HTTP).

## Validation case
- This example is the federation validation.

## Definition of done
- All acceptance criteria met by running checks.
- Maintainer approval recorded; the maintainer closes the GitHub issue.
- Journal entry appended.