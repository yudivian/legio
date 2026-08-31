"""Contract tests for LEG-025 — the agent loop over the mini-manager REST.

The REST surface exposes ``POST /submit`` and ``GET /status/{task_id}`` that
proxy the mini-manager, enforcing ownership (a foreign client's status request
is denied). Uses the ASGI transport with an async client (httpx) to exercise the
real FastAPI routes. All substrate is native beaver (LEG-048), bound via the
``beaver_db`` fixture.
"""

from __future__ import annotations

import httpx
import pytest
from beaver import AsyncBeaverDB
from pydantic import BaseModel

from legio.agents.tool_agent import ToolAgent
from legio.api import create_app
from legio.manager import status, submit
from legio.tools import ToolRegistry


class FlipInput(BaseModel):
    text: str


class FlipOutput(BaseModel):
    flipped: str


class FakeFlipTool:
    @property
    def input_schema(self) -> type[BaseModel]:
        return FlipInput

    @property
    def output_schema(self) -> type[BaseModel]:
        return FlipOutput

    def __call__(self, **kwargs: object) -> dict:
        return {"flipped": str(kwargs["text"])[::-1]}


@pytest.fixture
async def client() -> httpx.AsyncClient:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_submit_creates_task_and_status_returns_it(
    client: httpx.AsyncClient, beaver_db: AsyncBeaverDB
) -> None:
    resp = await client.post(
        "/submit", json={"client_id": "client-a", "agent": "flow_alpha", "payload": {"raw": 1}}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["task_id"].startswith("local:")

    task_id = body["task_id"]
    st = await client.get(f"/status/{task_id}", params={"client_id": "client-a"})
    assert st.status_code == 200, st.text
    entry = st.json()
    assert entry["task_id"] == task_id
    assert entry["owner"] == "client-a"
    assert entry["token"]["root"] is True
    assert entry["token"]["route_pattern_names"] == ["flow_alpha"]


@pytest.mark.asyncio
async def test_status_denies_foreign_client(
    client: httpx.AsyncClient, beaver_db: AsyncBeaverDB
) -> None:
    resp = await client.post(
        "/submit", json={"client_id": "client-a", "agent": "flow_alpha", "payload": {"raw": 1}}
    )
    task_id = resp.json()["task_id"]

    denied = await client.get(f"/status/{task_id}", params={"client_id": "client-b"})
    assert denied.status_code == 403
    assert denied.json()["code"] == "access_denied"

    anonymous = await client.get(f"/status/{task_id}")
    assert anonymous.status_code in (403, 422)


@pytest.mark.asyncio
async def test_status_unknown_task(client: httpx.AsyncClient, beaver_db: AsyncBeaverDB) -> None:
    resp = await client.get("/status/T-nope", params={"client_id": "client-a"})
    assert resp.status_code == 404
    assert resp.json()["code"] == "unknown_task"


@pytest.mark.asyncio
async def test_submit_missing_fields_is_rejected(
    client: httpx.AsyncClient, beaver_db: AsyncBeaverDB
) -> None:
    resp = await client.post("/submit", json={"client_id": "client-a"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_agent_loop_deposits_message_to_completion(
    beaver_db: AsyncBeaverDB,
) -> None:
    task_id = await submit("client-a", "flip", {"text": "abc"})

    registry = ToolRegistry()
    registry.register("flip", FakeFlipTool(), FlipInput, FlipOutput)
    agent = ToolAgent(
        agent_id="flip",
        db=beaver_db,
        registry=registry,
        tool_type="flip",
    )

    processed = await agent.run()
    assert processed == 1

    entry = await status(task_id, "client-a")
    assert entry.state.value == "completed"
    assert entry.output == {"text": "abc", "flipped": "cba"}
