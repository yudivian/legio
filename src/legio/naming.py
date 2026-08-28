"""`legio.naming` — identifier validation (LEG-016).

Every identifier (node, agent, tool, task) has a validating contract. The
``client:`` pseudo-agent family is reserved and cannot be used for regular
agents.
"""

from __future__ import annotations

import re

from legio.errors import InvalidNameError

_NODE_RE = re.compile(r"^[^@]+@[^@]+$")
_AGENT_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
_TOOL_RE = re.compile(r"^[a-z][a-z0-9_.]*$")
_TASK_RE = re.compile(r"^[^:]+:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

_RESERVED_AGENT_PREFIX = "client:"


def _guard(valid: bool, name: str) -> None:
    if not valid:
        raise InvalidNameError(f"invalid identifier {name!r}")


def validate_node_id(node_id: str) -> None:
    """A node id is ``<name>@<host>`` with exactly one ``@``."""
    _guard(bool(node_id) and _NODE_RE.match(node_id) is not None, node_id)


def validate_agent_id(agent_id: str) -> None:
    """An agent id is lowercase ``[a-z][a-z0-9_-]*`` and never reserved."""
    _guard(
        bool(agent_id)
        and _AGENT_RE.match(agent_id) is not None
        and not is_reserved_agent(agent_id),
        agent_id,
    )


def validate_tool_id(tool_id: str) -> None:
    """A tool id is consumer-namespaced lowercase ``[a-z][a-z0-9_.]*``."""
    _guard(bool(tool_id) and _TOOL_RE.match(tool_id) is not None, tool_id)


def validate_task_id(task_id: str) -> None:
    """A task id is ``<origin>:<uuid>``."""
    _guard(bool(task_id) and _TASK_RE.match(task_id) is not None, task_id)


def is_reserved_agent(agent_id: str) -> bool:
    """Whether the agent id belongs to the reserved pseudo-agent family."""
    return agent_id.startswith(_RESERVED_AGENT_PREFIX)


__all__ = [
    "is_reserved_agent",
    "validate_agent_id",
    "validate_node_id",
    "validate_task_id",
    "validate_tool_id",
]
