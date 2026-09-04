"""Contract tests for LEG-043 — Composite examples (R-4, domain-free).

Two in-repo examples that prove the R-4 engine end-to-end over REST
(LEG-025/LEG-027), as a client would drive them:

- ``extract_and_summarize`` — a **sequence** (linguistic → tool): a linguistic
  step produces structured output via lingo (``output_schema`` → compiled pydantic
  model passed to ``lingo.create``; ``input_schema`` governs the prompt template),
  then a tool step consumes it.
- ``distribute_summary`` — a **parallel root**: the submit delivers to the
  parallel's own class (a dumb delivery point — it never resolves the DAG), the
  ParallelAgent fans out to its branches and joins them on all-complete.

Both run on real beaver through the decoupled polling model: each agent is
booted at node startup with its own queue, polls it, and routes by the token.
No central engine; nothing is loaded dynamically at submit time.
"""

from __future__ import annotations

import logging

import httpx
import pytest
from beaver import AsyncBeaverDB
from lingo.mock import MockLLM
from pydantic import BaseModel

from legio.agents.linguistic_agent import LinguisticAgent
from legio.agents.parallel_agent import ParallelAgent
from legio.agents.tool_agent import ToolAgent
from legio.api import create_app
from legio.naming import result_queue_key
from legio.patterns import load_patterns
from legio.security import ClientTokenStore
from legio.tools import AvailableToolsRegistry

EXTRACT_AND_SUMMARIZE_YAML = """
name: extract_and_summarize
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
  - name: extract
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
      output_as: extract
      output_type: json
      output_schema:
        type: object
        properties:
          title: {type: string}
          summary: {type: string}
          word_count: {type: integer}
    prompt: "Extract the key points of {text} in {lang}."
  - name: assess
    type: atomic
    kind: tool
    input:
      input_as: extract
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
      title: "{extract.title}"
      summary: "{extract.summary}"
"""

DISTRIBUTE_SUMMARY_YAML = """
name: distribute_summary
type: composite
kind: parallel
main: true
input:
  input_as: payload
  input_type: json
  input_schema:
    type: object
    properties:
      text: {type: string}
output:
  output_as: result
  output_type: json
  output_schema:
    type: object
    properties:
      summ: {type: string}
      cata: {type: string}
parallel:
  - name: summ
    type: atomic
    kind: linguistic
    input:
      input_as: text
      input_type: json
      input_schema:
        type: object
        properties:
          text: {type: string}
    output:
      output_as: summ
      output_type: json
      output_schema:
        type: object
        properties:
          summ: {type: string}
    prompt: "Summarize: {text}"
  - name: cata
    type: atomic
    kind: linguistic
    input:
      input_as: text
      input_type: json
      input_schema:
        type: object
        properties:
          text: {type: string}
    output:
      output_as: cata
      output_type: json
      output_schema:
        type: object
        properties:
          cata: {type: string}
    prompt: "Categorize: {text}"
"""


class ExtractOutput(BaseModel):
    title: str
    summary: str
    word_count: int = 0


class SummOutput(BaseModel):
    summ: str = ""


class CataOutput(BaseModel):
    cata: str = ""


def fake_assess(title: str, summary: str) -> dict:
    """Domain-free fake tool: plain callable, signature is its contract."""
    return {"result": f"[{title}] {summary}"}


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_tool_registry() -> AvailableToolsRegistry:
    registry = AvailableToolsRegistry()
    registry.declare(
        "assess",
        implementation="tests.test_leg043_examples_composites.fake_assess",
        policy={"timeout": 30, "retries": 0},
    )
    return registry


def build_sequence_agents(db: AsyncBeaverDB) -> tuple[LinguisticAgent, ToolAgent]:
    lingo_client = MockLLM(
        responses=[ExtractOutput(title="Foxes", summary="A note about foxes.", word_count=4)]
    )
    registry = build_tool_registry()
    extract = LinguisticAgent(
        agent_id="extract",
        db=db,
        lingo_client=lingo_client,
        prompt_template="Extract the key points of {text} in {lang}.",
        output_model=ExtractOutput,
        input_as="payload",
        output_as="extract",
    )
    assess = ToolAgent(
        agent_id="assess",
        db=db,
        available_tools=registry,
        tool_name="assess",
        parameters={"title": "{title}", "summary": "{summary}"},
        input_as="extract",
        output_as="result",
    )
    return extract, assess


def build_parallel_agents(db: AsyncBeaverDB) -> tuple[ParallelAgent, LinguisticAgent, LinguisticAgent]:
    par = ParallelAgent(
        agent_id="distribute_summary",
        db=db,
        branches=[("summ", "text"), ("cata", "text")],
        input_as="payload",
        output_as="result",
    )
    summ = LinguisticAgent(
        agent_id="summ",
        db=db,
        lingo_client=MockLLM(responses=[SummOutput(summ="a summary")]),
        prompt_template="Summarize: {text}",
        output_model=SummOutput,
        input_as="text",
        output_as="summ",
    )
    cata = LinguisticAgent(
        agent_id="cata",
        db=db,
        lingo_client=MockLLM(responses=[CataOutput(cata="a category")]),
        prompt_template="Categorize: {text}",
        output_model=CataOutput,
        input_as="text",
        output_as="cata",
    )
    return par, summ, cata


@pytest.mark.asyncio
async def test_extract_and_summarize_sequence_over_rest(
    caplog: pytest.LogCaptureFixture, beaver_db: AsyncBeaverDB
) -> None:
    caplog.set_level(logging.INFO)
    extract, assess = build_sequence_agents(beaver_db)
    pattern_catalog = load_patterns(EXTRACT_AND_SUMMARIZE_YAML)

    store = ClientTokenStore()
    store.register("client-a", token="tok-a")
    app = create_app(clients=store, pattern_catalog=pattern_catalog)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/submit",
            json={
                "client_id": "client-a",
                "agent": "extract_and_summarize",
                "payload": {"text": "The quick brown fox.", "lang": "en"},
            },
            headers=bearer("tok-a"),
        )
        assert resp.status_code == 200, resp.text
        task_id = resp.json()["task_id"]

        await extract.run()
        await assess.run()

        status_resp = await ac.get(f"/status/{task_id}", headers=bearer("tok-a"))
        assert status_resp.status_code == 200, status_resp.text
        entry = status_resp.json()
        assert entry["state"] == "completed"
        assert entry["result_key"] == result_queue_key(task_id)
        assert entry["output"]["result"]["result"] == "[Foxes] A note about foxes."


@pytest.mark.asyncio
async def test_distribute_summary_parallel_root_over_rest(
    caplog: pytest.LogCaptureFixture, beaver_db: AsyncBeaverDB
) -> None:
    caplog.set_level(logging.INFO)
    par, summ, cata = build_parallel_agents(beaver_db)
    pattern_catalog = load_patterns(DISTRIBUTE_SUMMARY_YAML)

    store = ClientTokenStore()
    store.register("client-a", token="tok-a")
    app = create_app(clients=store, pattern_catalog=pattern_catalog)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/submit",
            json={
                "client_id": "client-a",
                "agent": "distribute_summary",
                "payload": {"text": "The quick brown fox."},
            },
            headers=bearer("tok-a"),
        )
        assert resp.status_code == 200, resp.text
        task_id = resp.json()["task_id"]

        # The submit delivered to the parallel's own class (dumb delivery point).
        await par.run()
        # Run both branches to a standstill, repeatedly interleaving so the
        # parallel can collect returns from its gathering queue.
        for _ in range(3):
            await summ.run()
            await cata.run()
            await par.run()

        status_resp = await ac.get(f"/status/{task_id}", headers=bearer("tok-a"))
        assert status_resp.status_code == 200, status_resp.text
        entry = status_resp.json()
        assert entry["state"] == "completed"
        assert entry["result_key"] == result_queue_key(task_id)
        # the joined branches are gathered under the parallel's output_as "result"
        assert entry["output"]["result"]["summ"]["summ"] == "a summary"
        assert entry["output"]["result"]["cata"]["cata"] == "a category"
