"""`legio.patterns.template` — dotted-path template resolution (H2).

Resolves ``{input.payload.text}``-style dotted references against the
composite-scoped board plus a set of system variables (e.g. ``{current_date}``).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][\w.]*)\}")


def resolve_template(
    template: str, scoped_board: Mapping[str, Any], system_vars: Mapping[str, Any]
) -> str:
    """Replace every ``{dotted.path}`` placeholder with its resolved value."""

    def _lookup(path: str) -> str:
        if path in system_vars:
            return str(system_vars[path])
        value: Any = scoped_board
        for part in path.split("."):
            if isinstance(value, Mapping):
                value = value.get(part)
            else:
                value = None
        return "" if value is None else str(value)

    return _PLACEHOLDER.sub(lambda m: _lookup(m.group(1)), template)


__all__ = ["resolve_template"]
