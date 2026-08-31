"""Contract tests for LEG-032 — Example: ``summarize`` (linguistic → tool).

The first R-3 domain-free example: a ``summarize`` flow composed of two
*independent, standing* atomic agents — a ``summ`` linguistic agent (driven by a
``MockLLM`` fake) that produces structured output, and an ``assess`` tool agent
that consumes that structured output and produces the final result. They run
through the decoupled polling model (AGENTS.md/ARCH): each agent is booted at
node startup with its own native beaver queue, polls its own queue, and routes
by the token — there is no central engine and nothing is loaded dynamically at
submit time. All substrate is native beaver (LEG-048).

The ``summarize`` starting pattern is a static, pre-declared linear chain
``("summ", "assess")`` resolved at boot and registered with the manager. Submit
(A) to ``summarize`` (behind LEG-027 auth) deposits the root message into ``summ``,
``summ`` advances to ``assess``, and ``assess`` finalizes to ``client:{task_id}``.
The acceptance is that the tool receives the linguistic step's structured output.
"""

from __future__ import annotations

import logging

import httpx
import pytest
from beaver import AsyncBeaverDB
from lingo.mock import MockLLM
from pydantic import BaseModel

from legio.agents.linguistic_agent import LinguisticAgent
from legio.agents.tool_agent import ToolAgent
from legio.api import create_app
from legio.manager import register_starting_route, results_board
from legio.patterns import load_pattern_specs
from legio.patterns.sequences import starting_route
from legio.security import ClientTokenStore
from legio.tools import ToolRegistry

SUMMARIZE_YAML = """
name: summarize
kind: main
sequence:
  - name: summ
    linguistic: true
    prompt: "Summarize {input.text} and {input.lang}."
  - name: assess
    tool: true
    tool_type: assess
"""


class SummarizeOutput(BaseModel):
    title: str
    summary: str
    word_count: int = 0


class AssessInput(BaseModel):
    title: str
    summary: str


class AssessOutput(BaseModel):
    result: str


class FakeAssessTool:
    @property
    def input_schema(self) -> type[BaseModel]:
        return AssessInput

    @property
    def output_schema(self) -> type[BaseModel]:
        return AssessOutput

    def __call__(self, **kwargs: object) -> dict:
        return {"result": f"[{kwargs['title']}] {kwargs['summary']}"}


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_standing_agents(db: AsyncBeaverDB) -> tuple[LinguisticAgent, ToolAgent]:
    """Boot the two independent agents at node startup, each with its own queue."""
    lingo_client = MockLLM(
        responses=[SummarizeOutput(title="Foxes", summary="A note about foxes.", word_count=4)]
    )
    registry = ToolRegistry()
    registry.register("assess", FakeAssessTool(), AssessInput, AssessOutput)

    summ = LinguisticAgent(
        agent_id="summ",
        db=db,
        lingo_client=lingo_client,
        prompt_template="Summarize {input.text} and {input.lang}.",
        output_model=SummarizeOutput,
    )
    assess = ToolAgent(
        agent_id="assess",
        db=db,
        registry=registry,
        tool_type="assess",
    )
    return summ, assess


@pytest.mark.asyncio
async def test_summarize_flows_linguistic_to_tool_over_rest_and_auth(
    caplog: pytest.LogCaptureFixture, beaver_db: AsyncBeaverDB
) -> None:
    caplog.set_level(logging.INFO)

    specs = load_pattern_specs(SUMMARIZE_YAML)
    summarize = specs[0]
    route = starting_route(summarize)
    assert route == ("summ", "assess")
    register_starting_route("summarize", route)

    store = ClientTokenStore()
    store.register("client-a", token="tok-a")
    app = create_app(clients=store)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/submit",
            json={"agent": "summarize", "payload": {"text": "the quick fox", "lang": "en"}},
            headers=bearer("tok-a"),
        )
        assert resp.status_code == 200, resp.text
        task_id = resp.json()["task_id"]

        summ, assess = build_standing_agents(beaver_db)
        assert await summ.run() == 1
        assert await assess.run() == 1

        st = await ac.get(f"/status/{task_id}", headers=bearer("tok-a"))
        assert st.status_code == 200, st.text
        entry = st.json()
        assert entry["state"] == "completed"
        # The assess tool consumed the linguistic step's structured output and
        # the root result carries the full accumulated state (H3).
        assert entry["output"] == {
            "text": "the quick fox",
            "lang": "en",
            "title": "Foxes",
            "summary": "A note about foxes.",
            "word_count": 4,
            "result": "[Foxes] A note about foxes.",
        }
        assert entry["result_key"] == f"results:{task_id}"

        board = await results_board()
        assert await board.fetch(task_id) == {
            "output": {
                "text": "the quick fox",
                "lang": "en",
                "title": "Foxes",
                "summary": "A note about foxes.",
                "word_count": 4,
                "result": "[Foxes] A note about foxes.",
            }
        }

        log_text = caplog.text
        assert "manager submit" in log_text
        assert "linguistic call" in log_text
        assert "agent advance" in log_text
        assert "agent root result" in log_text
