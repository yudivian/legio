"""`legio.naming` — identifiers and persisted names (LEG-016, LEG-048).

Every identifier (node, agent, tool, task) has a validating contract. The
``client:`` family is reserved for root returns and cannot be used for regular
agents.

The only persisted namespace legio names directly is the per-agent queue:
``legio:queue:<agent_id>`` (LEG-048). Boards are beaver dictionaries addressed
by their scope name directly (``db.dict(scope)``), so they need no extra key
namespace. Everything else is beaver's native naming.
"""

from __future__ import annotations

import logging
import re

from legio.errors import InvalidNameError

logger = logging.getLogger(__name__)

QUEUE_NAMESPACE = "legio:queue:"


def queue_key(agent_id: str) -> str:
    """Full namespaced beaver queue name for an agent (LEG-048)."""
    return f"{QUEUE_NAMESPACE}{agent_id}"


_NODE_RE = re.compile(r"^[^@]+@[^@]+$")
_AGENT_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
_TOOL_RE = re.compile(r"^[a-z][a-z0-9_.]*$")
_TASK_RE = re.compile(r"^[^:]+:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

_RESERVED_AGENT_PREFIX = "client:"


def _guard(valid: bool, name: str) -> None:
    if not valid:
        logger.warning("invalid identifier %r rejected", name)
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
    """Whether the agent id belongs to the reserved ``client:`` family."""
    return agent_id.startswith(_RESERVED_AGENT_PREFIX)


__all__ = [
    "QUEUE_NAMESPACE",
    "is_reserved_agent",
    "queue_key",
    "validate_agent_id",
    "validate_node_id",
    "validate_task_id",
    "validate_tool_id",
]
