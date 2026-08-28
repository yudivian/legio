"""`legio.manager` — the mini-manager (LEG-024).

The mini-manager owns task submission, status lookup and the client
pseudo-agent lifecycle. It is async and polling-only (AGENTS.md rule 8): it
never blocks or sleeps, and it stores task data on real (async) primitives.
Task result output lives on a ``results`` board; the ``client:{task_id}``
pseudo-agent queue receives the root result. Termination is either clean (the
client pseudo-agent handles the terminating root result) or reaper-driven (a
stuck client queue is force-terminated).
"""

from __future__ import annotations

import logging
from enum import Enum
from itertools import count
from typing import Any

from pydantic import BaseModel

from legio.flow import FlowToken
from legio.primitives import Board
from legio.primitives.inmemory import BoardInMemory, QueueInMemory

logger = logging.getLogger(__name__)

_RESULTS_SCOPE = "results"


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


def _new_substrate() -> dict[str, Any]:
    return {
        "queues": {},
        "boards": {},
        "tasks": {},
        "counter": count(1),
    }


_SUBSTRATE = _new_substrate()


def reset_manager() -> None:
    """Reset the in-memory substrate (test isolation)."""
    global _SUBSTRATE
    _SUBSTRATE = _new_substrate()


def _tasks() -> dict[str, Any]:
    return _SUBSTRATE["tasks"]


def _queues() -> dict[str, QueueInMemory]:
    return _SUBSTRATE["queues"]


def _boards() -> dict[str, BoardInMemory]:
    return _SUBSTRATE["boards"]


def next_counter() -> int:
    return next(_SUBSTRATE["counter"])


def _ensure_client_queue(task_id: str) -> None:
    agent_id = f"client:{task_id}"
    _queues().setdefault(agent_id, QueueInMemory(agent_id=agent_id))


async def submit(client_id: str, starting_agent: str, payload: dict[str, Any]) -> str:
    """Submit a task; returns its ``task_id``."""
    task_id = f"T-{next_counter()}"
    token = FlowToken(
        route_pattern_names=(starting_agent,),
        current_index=0,
        ultimate_return_agent_id=f"client:{task_id}",
        origin_node_id=starting_agent,
        root=True,
        task_id=task_id,
    )
    _tasks()[task_id] = {
        "owner": client_id,
        "state": TaskState.PENDING,
        "token": token.model_dump(mode="json"),
        "payload": payload,
    }
    _ensure_client_queue(task_id)
    logger.info(
        "manager submit task=%s owner=%s starting_agent=%s",
        task_id,
        client_id,
        starting_agent,
    )
    return task_id


async def status(task_id: str, client_id: str | None) -> TaskEntry:
    """Return the task entry if ``client_id`` owns it, else raise."""
    data = _tasks().get(task_id)
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
    result_board = _boards().get(_RESULTS_SCOPE)
    stored = await result_board.get(task_id) if result_board else None
    output = stored.get("output") if isinstance(stored, dict) else None
    return TaskEntry(
        task_id=task_id,
        owner=data["owner"],
        token=FlowToken.model_validate(data["token"]),
        state=TaskState(data["state"]),
        output=output,
        result_key=f"results:{task_id}" if stored is not None else None,
    )


async def results_board() -> Board:
    """Return the manager's ``results`` board (scope-based)."""
    return _boards().setdefault(_RESULTS_SCOPE, BoardInMemory(_RESULTS_SCOPE))


def client_queue(task_id: str) -> QueueInMemory:
    """Return the client pseudo-agent queue for ``task_id``."""
    _ensure_client_queue(task_id)
    return _queues()[f"client:{task_id}"]


def set_task_state(task_id: str, state: TaskState) -> None:
    data = _tasks().get(task_id)
    if data is not None:
        data["state"] = state


class Reaper:
    """Force-terminates stuck client pseudo-agent queues."""

    async def reap_clients(self) -> list[str]:
        """Return the task_ids whose client queues were force-terminated."""
        cancelled: list[str] = []
        for task_id, data in list(_tasks().items()):
            if data["state"] == TaskState.CLIENT_TERMINATED:
                continue
            cancelled.append(task_id)
            data["state"] = TaskState.CLIENT_TERMINATED
        if cancelled:
            logger.info("manager reaper cancelled client tasks=%s", ",".join(cancelled))
        return cancelled


__all__ = [
    "Reaper",
    "TaskEntry",
    "TaskState",
    "client_queue",
    "reset_manager",
    "results_board",
    "set_task_state",
    "status",
    "submit",
]
