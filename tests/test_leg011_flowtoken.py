"""Red contract tests for LEG-011 — FlowToken & messages v1.

These tests define the public contract for the immutable FlowToken and the two
message types (``ExecutionRequestMessage``, ``ExecutionResultMessage``),
including ``schema_version``, finality-derived-from-position and root
handling.

The modules imported here (``legio.flow``, ``legio.flow.messages``) do NOT
exist yet. This file is intentionally red: it must fail because the production
code is not implemented.
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
        route_pattern_names=["main_a", "summ"],
        current_index=0,
        ultimate_return_agent_id="client:T-1",
        origin_node_id="node-1",
        root=True,
        task_id="T-1",
    )
    round_tripped = FlowToken.model_validate_json(token.model_dump_json())
    assert round_tripped == token
    assert round_tripped.route_pattern_names == token.route_pattern_names
    assert round_tripped.current_index == token.current_index
    assert round_tripped.ultimate_return_agent_id == token.ultimate_return_agent_id
    assert round_tripped.origin_node_id == token.origin_node_id
    assert round_tripped.root == token.root
    assert round_tripped.task_id == token.task_id


def test_request_message_round_trip() -> None:
    request = ExecutionRequestMessage(
        route_pattern_names=["main_a"],
        current_index=0,
        ultimate_return_agent_id="client:T-1",
        origin_node_id="node-1",
        task_id="T-1",
        payload={"field": "value"},
    )
    round_tripped = ExecutionRequestMessage.model_validate_json(request.model_dump_json())
    assert round_tripped == request


def test_result_message_round_trip() -> None:
    result = ExecutionResultMessage(
        route_pattern_names=["main_a", "summ"],
        current_index=1,
        ultimate_return_agent_id="main_a",
        origin_node_id="summ",
        task_id="T-1",
        output={"summary": "text"},
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
        route_pattern_names=["a", "b", "c"],
        current_index=1,
        ultimate_return_agent_id="client:T-2",
        origin_node_id="node-1",
        root=True,
        task_id="T-2",
    )
    assert token.is_final(len(token.route_pattern_names)) is False

    final_token = FlowToken(
        route_pattern_names=["a", "b", "c"],
        current_index=2,
        ultimate_return_agent_id="client:T-2",
        origin_node_id="node-1",
        root=True,
        task_id="T-2",
    )
    assert final_token.is_final(len(final_token.route_pattern_names)) is True


def test_finality_is_not_a_flag() -> None:
    token = FlowToken(
        route_pattern_names=["a", "b"],
        current_index=1,
        ultimate_return_agent_id="client:T-3",
        origin_node_id="node-1",
        root=True,
        task_id="T-3",
    )
    assert not hasattr(token, "is_final_step")
    assert not hasattr(token, "final")


def test_root_token_implies_client_return_target() -> None:
    root = FlowToken(
        route_pattern_names=["main_a"],
        current_index=0,
        ultimate_return_agent_id="auto-generated",
        origin_node_id="node-1",
        root=True,
        task_id="T-4",
    )
    assert root.ultimate_return_agent_id == "client:T-4"
    assert root.root is True


def test_models_are_immutable() -> None:
    with pytest.raises(ValidationError):
        ExecutionResultMessage().output = {"changed": True}

    with pytest.raises(AttributeError):
        FlowToken().route_pattern_names.append("extra")


def test_messages_discriminate_by_type() -> None:
    request = ExecutionRequestMessage()
    result = ExecutionResultMessage()
    assert request.message_type is MessageType.EXECUTION_REQUEST
    assert result.message_type is MessageType.EXECUTION_RESULT
    assert MessageType.EXECUTION_REQUEST.value == "execution_request"
    assert MessageType.EXECUTION_RESULT.value == "execution_result"
