"""Contract tests for LEG-032 — Example: ``summarize`` (linguistic → tool).

The first R-3 domain-free example: a ``summarize`` flow composed of two
*independent, standing* atomic agents — a ``summ`` linguistic agent (driven by a
``MockLLM`` fake) that produces structured output, and an ``assess`` tool agent
that consumes that structured output and produces the final result. They run
through the decoupled polling model (AGENTS.md/ARCH): each agent is booted at
node startup with its own native beaver queue, polls its own queue, and routes
by the token — there is no central engine and nothing is loaded dynamically at
submit time. All substrate is native beaver.
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
from legio.naming import result_queue_key
from legio.patterns import load_patterns
from legio.security import ClientTokenStore
from legio.tools import AvailableToolsRegistry

SUMMARIZE_YAML = """
name: summarize
type: composite
kind: sequence
main: true
input:
  input_as: payload
  input_type: json
  input_schema:
    type: object
    properties:
      text: {type: string}
      lang: {type: string}
output:
  output_as: result
  output_type: json
  output_schema:
    type: object
    properties:
      result: {type: string}
sequence:
  - name: summ
    type: atomic
    kind: linguistic
    input:
      input_as: payload
      input_type: json
      input_schema:
        type: object
        properties:
          text: {type: string}
          lang: {type: string}
    output:
      output_as: summ
      output_type: json
      output_schema:
        type: object
        properties:
          title: {type: string}
          summary: {type: string}
          word_count: {type: integer}
    prompt: "Summarize {text} and {lang}."
  - name: assess
    type: atomic
    kind: tool
    input:
      input_as: summ
      input_type: json
      input_schema:
        type: object
        properties:
          title: {type: string}
          summary: {type: string}
    output:
      output_as: result
      output_type: json
      output_schema:
        type: object
        properties:
          result: {type: string}
    tool: assess
    parameters:
      title: "{summ.title}"
      summary: "{summ.summary}"
"""


class SummarizeOutput(BaseModel):
    title: str
    summary: str
    word_count: int = 0


class AssessOutput(BaseModel):
    result: str


def fake_assess(title: str, summary: str) -> dict:
    """Domain-free fake tool: plain callable, signature is its contract."""
    return {"result": f"[{title}] {summary}"}


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_standing_agents(db: AsyncBeaverDB) -> tuple[LinguisticAgent, ToolAgent]:
    """Boot the two independent agents at node startup, each with its own queue."""
    lingo_client = MockLLM(
        responses=[SummarizeOutput(title="Foxes", summary="A note about foxes.", word_count=4)]
    )
    registry = AvailableToolsRegistry()
    registry.declare(
        "assess",
        implementation="tests.test_leg032_example_summarize.fake_assess",
        policy={"timeout": 30, "retries": 0},
    )

    summ = LinguisticAgent(
        agent_id="summ",
        db=db,
        lingo_client=lingo_client,
        prompt_template="Summarize {text} and {lang}.",
        output_model=SummarizeOutput,
    )
    assess = ToolAgent(
        agent_id="assess",
        db=db,
        available_tools=registry,
        tool_name="assess",
        parameters={"title": "{title}", "summary": "{summary}"},
    )
    return summ, assess


@pytest.mark.asyncio
async def test_summarize_flows_linguistic_to_tool_over_rest_and_auth(
    caplog: pytest.LogCaptureFixture, beaver_db: AsyncBeaverDB
) -> None:
    caplog.set_level(logging.INFO)

    # Boot the standing agents
    summ, assess = build_standing_agents(beaver_db)

    # Load the pattern catalog
    pattern_catalog = load_patterns(SUMMARIZE_YAML)

    # Create the authenticated app with pattern catalog
    store = ClientTokenStore()
    store.register("client-a", token="tok-a")
    app = create_app(clients=store, pattern_catalog=pattern_catalog)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Submit to the summarize pattern
        resp = await ac.post(
            "/submit",
            json={"client_id": "client-a", "agent": "summarize", "payload": {"text": "The quick brown fox.", "lang": "en"}},
            headers=bearer("tok-a"),
        )
        assert resp.status_code == 200, resp.text
        task_id = resp.json()["task_id"]

        # Run both agents until they process the task
        await summ.run()
        await assess.run()

        # Check status
        status_resp = await ac.get(f"/status/{task_id}", headers=bearer("tok-a"))
        assert status_resp.status_code == 200, status_resp.text
        entry = status_resp.json()
        assert entry["state"] == "completed"
        assert entry["result_key"] == result_queue_key(task_id)

        # The tool should have received the linguistic output
        assert entry["output"]["result"] == "[Foxes] A note about foxes."

        log_text = caplog.text
        assert "manager submit" in log_text
        assert "agent run" in log_text
        assert "agent finish" in log_text