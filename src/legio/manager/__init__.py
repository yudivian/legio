"""`legio.manager` — the mini-manager (LEG-024) over native beaver (LEG-048).

The mini-manager owns task submission, status lookup and the client
pseudo-agent lifecycle. It is async and polling-only (AGENTS.md rule 8): it
never blocks or sleeps. All state lives on native beaver primitives — the
``tasks`` dictionary and the ``results`` dictionary (LEG-048, no invented
substrate layer): ``db.dict("tasks")`` / ``db.dict("results")``, and per-agent
queues ``db.queue("legio:queue:<agent_id>")``. Task result output lives on the
``results`` dictionary; the ``client:{task_id}`` pseudo-agent queue receives the
root result. Termination is either clean (the client pseudo-agent handles the
terminating root result) or reaper-driven (a stuck client queue is
force-terminated).
"""

from __future__ import annotations

import logging
from enum import Enum
from itertools import count
from typing import Any

from beaver import AsyncBeaverDB
from pydantic import BaseModel

from legio.flow import ExecutionRequestMessage, FlowToken
from legio.naming import queue_key

logger = logging.getLogger(__name__)

_TASKS_SCOPE = "tasks"
_RESULTS_SCOPE = "results"

_DEFAULT_DB_PATH = "legio.db"

_ROUTES: dict[str, tuple[str, ...]] = {}

_counter: Any = count(1)

_db: AsyncBeaverDB | None = None
_db_path: str = _DEFAULT_DB_PATH


class TaskState(str, Enum):
    """Lifecycle state of a submitted task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CLIENT_TERMINATED = "client_terminated"


class TaskEntry(BaseModel):
    """A read-only view of a submitted task returned by ``status``."""

    task_id: str
    owner: str
    token: FlowToken
    state: TaskState
    output: dict[str, Any] | None = None
    result_key: str | None = None


async def connect_manager(db_path: str | None = None) -> AsyncBeaverDB:
    """Open (or reuse) the manager's shared beaver database and return it."""
    global _db, _db_path
    if db_path is not None:
        _db_path = db_path
    if _db is None:
        _db = AsyncBeaverDB(_db_path)
        await _db.connect()
        logger.info("manager connected db=%s", _db_path)
    return _db


async def reset_manager(db_path: str | None = None) -> AsyncBeaverDB:
    """Bind the manager to a fresh database (typically a temp file for tests).

    Closes any previous connection so the new db starts empty.
    """
    global _db
    if _db is not None:
        await _db.close()
        _db = None
    return await connect_manager(db_path)


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
    """Return the ``results`` dictionary (native beaver dict)."""
    return (await db()).dict(_RESULTS_SCOPE)


def agent_queue(agent_id: str) -> Any:
    """Return the native beaver queue for an agent, by name.

    This is how any replica reaches an agent's queue: ``db.queue(...)`` maps the
    agent id onto a persistent, namespaced queue so a worker can poll it
    (LEG-048, ARCH §7.1, polling-only). The queue is created lazily by beaver.
    """
    return _current().queue(queue_key(agent_id))


def client_queue(task_id: str) -> Any:
    """Return the client pseudo-agent queue for ``task_id``."""
    return agent_queue(f"client:{task_id}")


def next_counter() -> int:
    return next(_counter)


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
    (default: the single agent), stages the inputs on the ``tasks`` dictionary
    and deposits the first ``ExecutionRequestMessage`` (the root step) into the
    first agent's queue. From there the flow is fully decoupled: workers poll
    the agent queues and route by the DAG in the token.
    """
    task_id = f"T-{next_counter()}"
    route = _resolve_route(starting_agent)
    first_agent = route[0]
    token = FlowToken(
        route_pattern_names=route,
        current_index=0,
        ultimate_return_agent_id=f"client:{task_id}",
        origin_node_id=first_agent,
        root=True,
        task_id=task_id,
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
        route_pattern_names=route,
        current_index=0,
        ultimate_return_agent_id=f"client:{task_id}",
        origin_node_id=first_agent,
        task_id=task_id,
        payload={"input": payload},
    )
    await agent_queue(first_agent).put(request.model_dump(mode="json"), priority=0.0)
    logger.info(
        "manager submit task=%s owner=%s starting_agent=%s route=%s",
        task_id,
        client_id,
        starting_agent,
        ",".join(route),
    )
    return task_id


async def status(task_id: str, client_id: str | None) -> TaskEntry:
    """Return the task entry if ``client_id`` owns it, else raise."""
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
    results = await results_board()
    stored = await results.fetch(task_id)
    output = stored.get("output") if isinstance(stored, dict) else None
    state = TaskState(data["state"])
    if stored is not None:
        state = TaskState.COMPLETED
    return TaskEntry(
        task_id=task_id,
        owner=data["owner"],
        token=FlowToken.model_validate(data["token"]),
        state=state,
        output=output,
        result_key=f"results:{task_id}" if stored is not None else None,
    )


async def set_task_state(task_id: str, state: TaskState) -> None:
    """Update a task's lifecycle state on the ``tasks`` dictionary."""
    tasks = await tasks_board()
    data = await tasks.fetch(task_id)
    if data is None:
        return
    data["state"] = state
    await tasks.set(task_id, data)


class Reaper:
    """Force-terminates stuck client pseudo-agent queues."""

    async def reap_clients(self) -> list[str]:
        """Return the task_ids whose client queues were force-terminated."""
        cancelled: list[str] = []
        tasks = await tasks_board()
        async for task_id in tasks.keys():
            data = await tasks.fetch(task_id)
            if data is None or data["state"] == TaskState.CLIENT_TERMINATED:
                continue
            cancelled.append(task_id)
            data["state"] = TaskState.CLIENT_TERMINATED
            await tasks.set(task_id, data)
        if cancelled:
            logger.info("manager reaper cancelled client tasks=%s", ",".join(cancelled))
        return cancelled


__all__ = [
    "AsyncBeaverDB",
    "Reaper",
    "TaskEntry",
    "TaskState",
    "agent_queue",
    "client_queue",
    "close_manager",
    "connect_manager",
    "db",
    "register_starting_route",
    "reset_manager",
    "results_board",
    "set_task_state",
    "status",
    "submit",
    "tasks_board",
]
