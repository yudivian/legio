"""Contract tests for LEG-011 — FlowToken & messages (Schema 2).

These tests define the public contract for the immutable FlowToken and the two
message types (``ExecutionRequestMessage``, ``ExecutionResultMessage``),
including ``schema_version``, finality-derived-from-position, root handling and
the Schema 2 token fields (``level_route``, ``current_index``,
``end_of_level_queue``, ``level``, ``launcher_class``, single ``payload``
container, no ``next_queue``/``ultimate_return_agent_id``/``origin_node_id``).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from legio.flow import (
    SCHEMA_VERSION,
    ExecutionRequestMessage,
    ExecutionResultMessage,
    FlowToken,
)
from legio.flow.messages import MessageType


def test_round_trip_preserves_all_fields() -> None:
    token = FlowToken(
        level_route=("main_a", "summ"),
        current_index=0,
        end_of_level_queue="result:T-1",
        level=1,
        launcher_class="main_a",
        root=True,
        task_id="T-1",
    )
    round_tripped = FlowToken.model_validate_json(token.model_dump_json())
    assert round_tripped == token
    assert round_tripped.level_route == token.level_route
    assert round_tripped.current_index == token.current_index
    assert round_tripped.end_of_level_queue == token.end_of_level_queue
    assert round_tripped.level == token.level
    assert round_tripped.launcher_class == token.launcher_class
    assert round_tripped.root == token.root
    assert round_tripped.task_id == token.task_id


def test_request_message_round_trip() -> None:
    request = ExecutionRequestMessage(
        level_route=("main_a",),
        current_index=0,
        end_of_level_queue="result:T-1",
        task_id="T-1",
        payload={"field": "value"},
    )
    round_tripped = ExecutionRequestMessage.model_validate_json(request.model_dump_json())
    assert round_tripped == request


def test_result_message_round_trip() -> None:
    result = ExecutionResultMessage(
        level_route=("main_a", "summ"),
        current_index=1,
        end_of_level_queue="main_a",
        task_id="T-1",
        payload={"summary": "text"},
    )
    round_tripped = ExecutionResultMessage.model_validate_json(result.model_dump_json())
    assert round_tripped == result


def test_models_carry_schema_version() -> None:
    assert ExecutionRequestMessage().schema_version == SCHEMA_VERSION
    assert ExecutionResultMessage().schema_version == SCHEMA_VERSION
    assert FlowToken().schema_version == SCHEMA_VERSION


def test_major_version_mismatch_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ExecutionRequestMessage(schema_version=int(SCHEMA_VERSION) + 10)

    with pytest.raises(ValidationError):
        ExecutionResultMessage(schema_version=0)

    with pytest.raises(ValidationError):
        FlowToken(schema_version=int(SCHEMA_VERSION) + 99)


def test_finality_derived_from_position() -> None:
    token = FlowToken(
        level_route=("a", "b", "c"),
        current_index=1,
        end_of_level_queue="result:T-2",
        root=True,
        task_id="T-2",
    )
    assert token.is_final(len(token.level_route)) is False

    final_token = FlowToken(
        level_route=("a", "b", "c"),
        current_index=2,
        end_of_level_queue="result:T-2",
        root=True,
        task_id="T-2",
    )
    assert final_token.is_final(len(final_token.level_route)) is True


def test_finality_is_not_a_flag() -> None:
    token = FlowToken(
        level_route=("a", "b"),
        current_index=1,
        end_of_level_queue="result:T-3",
        root=True,
        task_id="T-3",
    )
    assert not hasattr(token, "is_final_step")
    assert not hasattr(token, "final")


def test_root_token_does_not_derive_its_return_target() -> None:
    """Schema 2 (addendum AL): the destination is the submit's end_of_level_queue.

    A root token does *not* invent a ``client:{task_id}`` return; the closer is
    set who creates the flow, never derived from ``task_id`` and never stored as
    an ``ultimate_return_agent_id``.
    """
    root = FlowToken(
        level_route=("main_a",),
        current_index=0,
        end_of_level_queue="result:T-4",
        root=True,
        task_id="T-4",
    )
    assert root.end_of_level_queue == "result:T-4"
    assert root.root is True
    assert not hasattr(root, "ultimate_return_agent_id")


def test_models_are_immutable() -> None:
    with pytest.raises(ValidationError):
        ExecutionResultMessage().payload = {"changed": True}

    with pytest.raises(AttributeError):
        FlowToken().level_route.append("extra")  # type: ignore[attr-defined]


def test_messages_discriminate_by_type() -> None:
    request = ExecutionRequestMessage()
    result = ExecutionResultMessage()
    assert request.message_type is MessageType.EXECUTION_REQUEST
    assert result.message_type is MessageType.EXECUTION_RESULT
    assert MessageType.EXECUTION_REQUEST.value == "execution_request"
    assert MessageType.EXECUTION_RESULT.value == "execution_result"
