"""`legio.api` — the node's external API surface (LEG-025, over LEG-014/024).

Exposes the mini-manager over REST (FastAPI): ``POST /submit`` creates a task
via the synthetic parent and ``GET /status/{task_id}`` reads it back with
ownership enforced (LEG-014/017 semantics). The API is *polling-only*: a client
creates a task and later polls ``status``; there are no callbacks. HTTP error
mapping follows the LEG-016 taxonomy (4xx/5xx with a stable ``code``).

Auth middleware is LEG-027 (out of scope here); these endpoints are the surface
a later guard sits in front of.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from legio import manager
from legio.flow import FlowToken
from legio.manager import TaskEntry, TaskState

logger = logging.getLogger(__name__)


class SubmitRequest(BaseModel):
    """Body of ``POST /submit``.

    ``agent`` is the *starting agent* (an entry point of the node, ARCH §6);
    ``payload`` is the client payload the synthetic parent stages.
    """

    client_id: str = Field(min_length=1)
    agent: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class SubmitResponse(BaseModel):
    task_id: str


class StatusResponse(BaseModel):
    task_id: str
    owner: str
    state: TaskState
    token: FlowToken
    output: dict[str, Any] | None = None
    result_key: str | None = None


def _to_status_response(entry: TaskEntry) -> StatusResponse:
    return StatusResponse(
        task_id=entry.task_id,
        owner=entry.owner,
        state=entry.state,
        token=entry.token,
        output=entry.output,
        result_key=entry.result_key,
    )


def create_app() -> FastAPI:
    """Build the FastAPI application exposing the mini-manager over REST."""
    app = FastAPI(title="legio", version="0.1.0")

    @app.post("/submit", response_model=SubmitResponse)
    async def submit(body: SubmitRequest) -> SubmitResponse:
        task_id = await manager.submit(body.client_id, body.agent, body.payload)
        logger.info("api submit task=%s client=%s agent=%s", task_id, body.client_id, body.agent)
        return SubmitResponse(task_id=task_id)

    @app.get("/status/{task_id}", response_model=StatusResponse)
    async def status(
        task_id: str,
        client_id: str | None = Query(default=None),
    ) -> StatusResponse | JSONResponse:
        try:
            entry = await manager.status(task_id, client_id)
        except PermissionError:
            logger.warning("api status denied task=%s client=%s", task_id, client_id)
            return JSONResponse(status_code=403, content={"code": "access_denied"})
        except KeyError:
            logger.warning("api status unknown task=%s", task_id)
            return JSONResponse(status_code=404, content={"code": "unknown_task"})
        return _to_status_response(entry)

    return app


__all__ = ["StatusResponse", "SubmitRequest", "SubmitResponse", "create_app"]
