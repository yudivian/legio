# DEPENDENCIES — Report for approval

Status: **APPROVED** (decision of 2026-08-27). No dependency may be added or
removed before a reviewed PR to this file. Managed with `uv`. Python runtime:
**>= 3.13** (matching beaver's requirement).

## Runtime

| Package | Role in legio | Notes |
|---|---|---|
| `beaver-db` | boards, priority queues, locks (the substrate) | pinned by `uv.lock` at first install |
| `lingo-ai` | LLM + structured output for linguistic agents | provides `LLM`, `eng.create/decide/choose`, `MockLLM`, native tool-calling |
| `pydantic` (>=2) | types/validation of message, token, patterns, schemas | lingua franca of the system |
| `pydantic-settings` | configuration from env | node id, paths, peers |
| `pyyaml` | parse patterns YAML | |
| `fastapi` | API + federation server endpoints | |
| `uvicorn` | ASGI server for the above | |
| `httpx` | HTTP client for federation + tool calls | async |

## Dev

| Package | Role |
|---|---|
| `ruff` | lint + format |
| `pytest` | test runner |
| `pytest-asyncio` | async tests |
| `respx` | mock `httpx` (tools, inter-node HTTP) |
| `pyright` (optional) | type checking (optional; decide at R-0) |

## Excluded on purpose

- `castor-io`: outdated against current beaver; its role (worker/task
  registry) is implemented in legio itself.
- Any broker, Redis, DB server, workflow engine, scheduler library, or
  callback/event library: all covered by beaver + the design's polling/field
  semantics.

Approve, add or remove items. Changes only via reviewed PR to this file.