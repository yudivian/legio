"""`legio.manager` — the mini-manager (LEG-024) over native beaver (LEG-048).

The mini-manager owns task submission and status lookup. It is async and
polling-only (AGENTS.md rule 8): it never blocks or sleeps. All state lives on
native beaver primitives (LEG-048, no invented substrate layer): the ``tasks``
dictionary and the per-agent queues ``db.queue("legio:queue:<agent_id>")``.

Task submission (Schema 2) seeds the starting pattern's level-1 route with an
``end_of_level_queue`` = the task's final-result queue
(``result_queue_key(task_id)``); whichever class closes the level deposits the
``ExecutionResultMessage`` there, and ``status`` reads it back from that queue
(peek, non-destructive). There is **no** ``results`` board and no
``client:{task_id}`` family (ARCH §7, addendum AL). Task ids obey the naming
contract ``<origin>:<uuid>`` (LEG-016).
"""

from __future__ import annotations

import logging
import uuid
from enum import Enum
from typing import Any

from beaver import AsyncBeaverDB
from pydantic import BaseModel

from legio.flow import ExecutionRequestMessage, ExecutionResultMessage, FlowToken
from legio.naming import queue_key, result_queue_key

logger = logging.getLogger(__name__)

_TASKS_SCOPE = "tasks"

_DEFAULT_DB_PATH = "legio.db"
_DEFAULT_NODE_ID = "local"

_ROUTES: dict[str, tuple[str, ...]] = {}

_db: AsyncBeaverDB | None = None
_db_path: str = _DEFAULT_DB_PATH
_node_id: str = _DEFAULT_NODE_ID


class TaskState(str, Enum):
    """Lifecycle state of a submitted task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"


class TaskEntry(BaseModel):
    """A read-only view of a submitted task returned by ``status``."""

    task_id: str
    owner: str
    token: FlowToken
    state: TaskState
    output: dict[str, Any] | None = None
    result_key: str | None = None


async def connect_manager(
    db_path: str | None = None, *, node_id: str | None = None
) -> AsyncBeaverDB:
    """Open (or reuse) the manager's shared beaver database and return it.

    ``node_id`` is the origin node minted into new task ids (``<origin>:<uuid>``,
    LEG-016); it defaults to ``"local"`` and is only accepted on first bind.
    """
    global _db, _db_path, _node_id
    if db_path is not None:
        _db_path = db_path
    if node_id is not None:
        _node_id = node_id
    if _db is None:
        _db = AsyncBeaverDB(_db_path)
        await _db.connect()
        logger.info("manager connected db=%s node=%s", _db_path, _node_id)
    return _db


async def reset_manager(db_path: str | None = None, *, node_id: str | None = None) -> AsyncBeaverDB:
    """Bind the manager to a fresh database (typically a temp file for tests).

    Closes any previous connection so the new db starts empty.
    """
    global _db
    if _db is not None:
        await _db.close()
        _db = None
    return await connect_manager(db_path, node_id=node_id)


async def close_manager() -> None:
    """Close the manager's shared database (test teardown)."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None
        logger.info("manager closed db=%s", _db_path)


async def db() -> AsyncBeaverDB:
    """Return the manager database, connecting on first use if needed."""
    return await connect_manager()


async def tasks_board():
    """Return the ``tasks`` dictionary (native beaver dict, ARCH §2)."""
    return (await db()).dict(_TASKS_SCOPE)


async def results_board():
    """DEPRECATED (Schema 2): no results board exists; results live in a queue.

    Retained only so older callers fail loudly instead of silently writing to a
    board that the flow no longer writes to. Prefer ``status`` / the token's
    ``end_of_level_queue``.
    """
    raise NotImplementedError(
        "results board removed (Schema 2): results live on the final-result queue"
    )


def agent_queue(agent_id: str) -> Any:
    """Return the native beaver queue for an agent, by name.

    This is how any replica reaches an agent's queue: ``db.queue(...)`` maps the
    agent id onto a persistent, namespaced queue so an agent can poll it
    (LEG-048, ARCH §7.1, polling-only). The queue is created lazily by beaver.
    """
    return _current().queue(queue_key(agent_id))


def _new_task_id() -> str:
    """Mint a task id honoring the naming contract ``<origin>:<uuid>`` (LEG-016)."""
    return f"{_node_id}:{uuid.uuid4()}"


def register_starting_route(starting_agent: str, route_names: tuple[str, ...]) -> None:
    """Register a static route for a starting pattern.

    INTERIM (R-3) mechanism, to be removed in R-4 (LEG-040/LEG-041): the
    manager currently resolves the DAG at submit via ``_resolve_route``, which
    contradicts the decoupled design (ARCH §3/§6 — the *starting agent*
    concretizes the token; the manager never knows the DAG). Keep until the
    starting sequence/parallel agents exist. Do not extend this API.
    """
    if not route_names:
        raise ValueError("a starting route must name at least one agent")
    _ROUTES[starting_agent] = tuple(route_names)
    logger.info("manager starting route %s=%s", starting_agent, ",".join(route_names))


def _resolve_route(starting_agent: str) -> tuple[str, ...]:
    """Return the route for ``starting_agent`` (default: the agent itself).

    INTERIM (R-3) — see ``register_starting_route``; routes are to be
    concretized by the starting agent, not resolved by the manager.
    """
    return _ROUTES.get(starting_agent, (starting_agent,))


def _current() -> AsyncBeaverDB:
    if _db is None:
        raise RuntimeError(
            "manager is not connected; call 'await connect_manager()' (or 'reset_manager()') first"
        )
    return _db


async def submit(client_id: str, starting_agent: str, payload: dict[str, Any]) -> str:
    """Submit a task; returns its ``task_id``.

    The synthetic parent (ARCH §6) resolves the starting pattern's static route
    (default: the single agent), creates the task's final-result queue, stages
    the inputs on the ``tasks`` dictionary and deposits the first
    ``ExecutionRequestMessage`` (the root step, Schema 2 token with
    ``end_of_level_queue`` = final-result queue) into the first agent's queue.
    From there the flow is fully decoupled: agents poll their own queues and
    route by the token.
    """
    task_id = _new_task_id()
    route = _resolve_route(starting_agent)
    first_agent = route[0]
    result_queue = result_queue_key(task_id)
    token = FlowToken(
        level_route=route,
        current_index=0,
        end_of_level_queue=result_queue,
        level=1,
        launcher_class=first_agent,
        task_id=task_id,
        root=True,
    )
    tasks = await tasks_board()
    await tasks.set(
        task_id,
        {
            "owner": client_id,
            "state": TaskState.PENDING,
            "token": token.model_dump(mode="json"),
            "payload": payload,
        },
    )

    request = ExecutionRequestMessage(
        level_route=route,
        current_index=0,
        end_of_level_queue=result_queue,
        level=1,
        launcher_class=first_agent,
        task_id=task_id,
        payload=payload,
    )
    await agent_queue(first_agent).put(request.model_dump(mode="json"), priority=0.0)
    logger.info(
        "manager submit task=%s owner=%s starting_agent=%s route=%s result_queue=%s",
        task_id,
        client_id,
        starting_agent,
        ",".join(route),
        result_queue,
    )
    return task_id


async def status(task_id: str, client_id: str | None) -> TaskEntry:
    """Return the task entry if ``client_id`` owns it, else raise.

    The completed result is read from the task's final-result queue (Schema 2,
    ``result_queue_key(task_id)``) via a non-destructive ``peek``; an empty queue
    means the task is still pending/running.
    """
    tasks = await tasks_board()
    data = await tasks.fetch(task_id)
    if data is None:
        logger.warning("manager status unknown task=%s", task_id)
        raise KeyError(f"unknown task {task_id!r}")
    if data["owner"] != client_id:
        logger.warning(
            "manager status denied task=%s owner=%s requester=%s",
            task_id,
            data["owner"],
            client_id,
        )
        raise PermissionError("task is scoped to its owning client")

    state = TaskState(data["state"])
    result_key: str | None = None
    output: dict[str, Any] | None = None
    result_queue = result_queue_key(task_id)
    result_item = await (await db()).queue(queue_key(result_queue)).peek()
    if result_item is not None:
        result = ExecutionResultMessage.model_validate(result_item.data)
        output = dict(result.payload)
        state = TaskState.COMPLETED
        result_key = result_queue
    return TaskEntry(
        task_id=task_id,
        owner=data["owner"],
        token=FlowToken.model_validate(data["token"]),
        state=state,
        output=output,
        result_key=result_key,
    )


__all__ = [
    "AsyncBeaverDB",
    "TaskEntry",
    "TaskState",
    "agent_queue",
    "close_manager",
    "connect_manager",
    "db",
    "register_starting_route",
    "reset_manager",
    "status",
    "submit",
    "tasks_board",
]
