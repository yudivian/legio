"""Contract tests for LEG-030 — LinguisticAgent via lingo (over native beaver).

The LinguisticAgent is an ``AgentBase`` (LEG-023) that pops a work item from its
native beaver queue, resolves its prompt template against the message-carried
payload, calls lingo (an ``LLM``/``MockLLM`` fake) to get a structured pydantic
record validated against the pattern's declared ``output_model``, and deposits
an ``ExecutionResultMessage`` to the parent (or advances to the next step of
the route). The step's state rides in the messages (AGENT_LIFECYCLE §12.1):
there is no out-of-message staging board. Failures from lingo are never silent:
an error-carrying result is deposited instead. All substrate is native beaver
(LEG-048).
"""

from __future__ import annotations

import pytest
from beaver import AsyncBeaverDB
from lingo.mock import MockLLM
from pydantic import BaseModel

from legio.agents.linguistic_agent import LinguisticAgent
from legio.flow import ExecutionRequestMessage, ExecutionResultMessage
from legio.naming import queue_key


class SummarizeOutput(BaseModel):
    title: str
    summary: str
    word_count: int = 0


PROMPT = "Summarize {input.text} and {input.lang}."


async def pop_one(db: AsyncBeaverDB, agent_id: str) -> dict | None:
    try:
        item = await db.queue(queue_key(agent_id)).get(block=False)
    except IndexError:
        return None
    return item.data


def build_agent(*, db: AsyncBeaverDB, lingo_client, output_model, agent_id: str = "summ"):
    return LinguisticAgent(
        agent_id=agent_id,
        db=db,
        lingo_client=lingo_client,
        prompt_template=PROMPT,
        output_model=output_model,
    )


@pytest.mark.asyncio
async def test_linguistic_agent_returns_structured_output_through_lingo(
    beaver_db: AsyncBeaverDB,
) -> None:
    """The prompt is templated from the message-carried payload."""
    expected = SummarizeOutput(title="Hello", summary="A greeting", word_count=1)
    lingo_client = MockLLM(responses=[expected])
    task_id = "T-1"

    request = ExecutionRequestMessage(
        route_pattern_names=("main_a", "summ"),
        current_index=1,
        ultimate_return_agent_id="main_a",
        origin_node_id="main_a",
        task_id=task_id,
        payload={"input": {"text": "hello", "lang": "en"}},
    )
    await beaver_db.queue(queue_key("summ")).put(request.model_dump(mode="json"), priority=0.0)

    agent = build_agent(db=beaver_db, lingo_client=lingo_client, output_model=SummarizeOutput)

    handled = await agent.process_next()
    assert handled is True

    sent_messages = lingo_client.history[-1]
    assert sent_messages and sent_messages[0].content == ("Summarize hello and en.")

    result_item = await pop_one(beaver_db, "main_a")
    assert result_item is not None
    result = ExecutionResultMessage.model_validate(result_item)
    assert result.task_id == task_id
    assert result.output["summary"] == "A greeting"


@pytest.mark.asyncio
async def test_linguistic_agent_templates_input_from_request_payload(
    beaver_db: AsyncBeaverDB,
) -> None:
    expected = SummarizeOutput(title="Input", summary="s", word_count=0)
    lingo_client = MockLLM(responses=[expected])

    request = ExecutionRequestMessage(
        route_pattern_names=("main_a", "summ"),
        current_index=1,
        ultimate_return_agent_id="main_a",
        origin_node_id="main_a",
        task_id="T-input",
        payload={"input": {"text": "request payload", "lang": "en"}},
    )
    await beaver_db.queue(queue_key("summ")).put(request.model_dump(mode="json"), priority=0.0)

    agent = build_agent(db=beaver_db, lingo_client=lingo_client, output_model=SummarizeOutput)

    await agent.process_next()

    sent_messages = lingo_client.history[-1]
    assert sent_messages[0].content == "Summarize request payload and en."


@pytest.mark.asyncio
async def test_linguistic_agent_advances_when_not_last_step(
    beaver_db: AsyncBeaverDB,
) -> None:
    expected = SummarizeOutput(title="Mid", summary="middle step", word_count=2)
    lingo_client = MockLLM(responses=[expected])

    request = ExecutionRequestMessage(
        route_pattern_names=("summ", "emit"),
        current_index=0,
        ultimate_return_agent_id="client:T-c",
        origin_node_id="client",
        task_id="T-c",
        payload={"input": {"text": "x", "lang": "en"}},
    )
    await beaver_db.queue(queue_key("summ")).put(request.model_dump(mode="json"), priority=0.0)

    agent = build_agent(db=beaver_db, lingo_client=lingo_client, output_model=SummarizeOutput)

    await agent.process_next()

    advanced = await pop_one(beaver_db, "emit")
    assert advanced is not None
    advanced_msg = ExecutionRequestMessage.model_validate(advanced)
    assert advanced_msg.current_index == 1
    assert advanced_msg.route_pattern_names == ("summ", "emit")
    assert advanced_msg.payload == {
        "input": {
            "text": "x",
            "lang": "en",
            "title": "Mid",
            "summary": "middle step",
            "word_count": 2,
        }
    }


@pytest.mark.asyncio
async def test_linguistic_agent_failure_is_never_silent(beaver_db: AsyncBeaverDB) -> None:
    """A wrong-typed lingo response yields an error result, never silence."""
    lingo_client = MockLLM(responses=[{"not": "a model"}])

    request = ExecutionRequestMessage(
        route_pattern_names=("main_a", "summ"),
        current_index=1,
        ultimate_return_agent_id="main_a",
        origin_node_id="main_a",
        task_id="T-fail",
        payload={"input": {"text": "x", "lang": "en"}},
    )
    await beaver_db.queue(queue_key("summ")).put(request.model_dump(mode="json"), priority=0.0)

    agent = build_agent(db=beaver_db, lingo_client=lingo_client, output_model=SummarizeOutput)

    await agent.process_next()

    result_item = await pop_one(beaver_db, "main_a")
    assert result_item is not None
    result = ExecutionResultMessage.model_validate(result_item)
    assert result.task_id == "T-fail"
    assert "error" in result.output


@pytest.mark.asyncio
async def test_no_due_item_returns_false(beaver_db: AsyncBeaverDB) -> None:
    lingo_client = MockLLM(responses=[])
    agent = build_agent(db=beaver_db, lingo_client=lingo_client, output_model=SummarizeOutput)

    assert await agent.process_next() is False
