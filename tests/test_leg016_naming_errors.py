"""Contract tests for LEG-016 — Naming & errors (v1).

These tests define the public contract for identifier validation and the typed
error taxonomy. The modules imported here (``legio.naming``, ``legio.errors``)
now exist and are implemented; the tests verify conformance.
"""

from __future__ import annotations

import pytest

from legio.errors import (
    InvalidNameError,
    LegioError,
    RecoverableError,
    UnrecoverableError,
    code,
    recoverable,
    retriable,
)
from legio.naming import (
    is_reserved_agent,
    validate_agent_id,
    validate_node_id,
    validate_task_id,
    validate_tool_id,
)

VALID_NODE = "node1@host1"
VALID_AGENT = "flow_a"
VALID_TOOL = "consumer.text_extractor"
VALID_TASK = "node1:3f2a5b99-7c11-4d2e-9f30-abcdef012345"


def test_valid_node_id_accepts_name_at_host() -> None:
    validate_node_id(VALID_NODE)


def test_invalid_node_id_raises() -> None:
    for bad in ("nospace", "@only", "name@@host", ""):
        with pytest.raises(InvalidNameError):
            validate_node_id(bad)


def test_valid_agent_id() -> None:
    validate_agent_id(VALID_AGENT)


def test_invalid_agent_id_raises() -> None:
    for bad in ("flow a", "", "Flow_A!", "with/slash"):
        with pytest.raises(InvalidNameError):
            validate_agent_id(bad)


def test_reserved_client_agent_id_is_rejected_for_regular_use() -> None:
    assert is_reserved_agent("client:some-task-id")
    with pytest.raises(InvalidNameError):
        validate_agent_id("client:some-task-id")


def test_valid_tool_id_is_consumer_namespaced() -> None:
    validate_tool_id(VALID_TOOL)


def test_invalid_tool_id_raises() -> None:
    for bad in ("", "spaces in tool", "!bad"):
        with pytest.raises(InvalidNameError):
            validate_tool_id(bad)


def test_task_id_format_requires_origin_and_uuid() -> None:
    validate_task_id(VALID_TASK)
    for bad in ("no-uuid", "node1:not-a-uuid", ""):
        with pytest.raises(InvalidNameError):
            validate_task_id(bad)


def test_legio_error_model_exposes_code() -> None:
    error = LegioError("boom")
    assert error.code == code("boom")
    assert isinstance(error.code, str)


def test_error_recoverable_flag() -> None:
    assert recoverable(RecoverableError("transient")) is True
    assert recoverable(UnrecoverableError("fatal")) is False


def test_error_retriable_flag() -> None:
    assert retriable(RecoverableError("transient")) is True
    assert retriable(UnrecoverableError("fatal")) is False


def test_invalid_name_error_is_typed() -> None:
    assert issubclass(InvalidNameError, LegioError)
    assert issubclass(RecoverableError, LegioError)
    assert issubclass(UnrecoverableError, LegioError)
