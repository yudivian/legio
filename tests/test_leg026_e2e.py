"""LEG-026 — End-to-end example: ``transform`` with a fake, domain-free tool.

First real single-node capability over the REST surface. A client submits to the
``transform`` agent through the API; the agent polls its own queue and runs the
registered fake tool; the root result lands in the task's final-result queue
(``end_of_level_queue``, Schema 2) and the client reads it back via ``status``.
Boundary is the REST surface; all substrate is shared in-process over a single
native beaver database (one connection, one manager) as on a single node.
"""

from __future__ import annotations

import logging

import httpx
import pytest
from beaver import AsyncBeaverDB
from pydantic import BaseModel

from legio.agents.tool_agent import ToolAgent
from legio.api import create_app
from legio.naming import queue_key, result_queue_key
from legio.tools import ToolRegistry


class TransformInput(BaseModel):
    text: str
    factor: int = 2


class TransformOutput(BaseModel):
    transformed: str


class FakeTransformTool:
    @property
    def input_schema(self) -> type[BaseModel]:
        return TransformInput

    @property
    def output_schema(self) -> type[BaseModel]:
        return TransformOutput

    def __call__(self, **kwargs: object) -> dict:
        return {"transformed": str(kwargs["text"]).upper()}


def build_transform_agent(db: AsyncBeaverDB) -> ToolAgent:
    registry = ToolRegistry()
    registry.register("transform", FakeTransformTool(), TransformInput, TransformOutput)
    return ToolAgent(
        agent_id="transform",
        db=db,
        registry=registry,
        tool_type="transform",
    )


@pytest.mark.asyncio
async def test_transform_e2e_over_rest_and_agent(
    caplog: pytest.LogCaptureFixture, beaver_db: AsyncBeaverDB
) -> None:
    caplog.set_level(logging.INFO)
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/submit",
            json={
                "client_id": "client-a",
                "agent": "transform",
                "payload": {"text": "hello", "factor": 3},
            },
        )
        assert resp.status_code == 200, resp.text
        task_id = resp.json()["task_id"]

        agent = build_transform_agent(beaver_db)
        processed = await agent.run()
        assert processed == 1

        st = await ac.get(f"/status/{task_id}", params={"client_id": "client-a"})
        assert st.status_code == 200, st.text
        entry = st.json()
        assert entry["state"] == "completed"
        assert entry["output"] == {"text": "hello", "factor": 3, "transformed": "HELLO"}
        assert entry["result_key"] == result_queue_key(task_id)

        result_item = await beaver_db.queue(
            queue_key(result_queue_key(task_id))
        ).peek()
        assert result_item is not None
        assert result_item.data["payload"] == {
            "text": "hello",
            "factor": 3,
            "transformed": "HELLO",
        }

        log_text = caplog.text
        assert "manager submit" in log_text
        assert "agent run" in log_text
        assert "agent finish" in log_text
