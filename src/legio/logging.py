"""`legio.logging` — logging configuration helper.

legio is a library: every module provisions its own ``logging.getLogger(__name__)``
logger (prefix ``legio.*``) and never configures the root logger or installs
handlers itself — consumers own the logging config. This helper lets a consumer
(or a test runner) opt in to structured verbosity in a single call without
touching the root logger unless requested.
"""

from __future__ import annotations

import logging

_LOGGER_PREFIX = "legio."
_DEFAULT_ROOT = False
_DEFAULT_LEVEL = logging.INFO


def configure(
    level: int | str = _DEFAULT_LEVEL,
    *,
    root: bool = _DEFAULT_ROOT,
    format_string: str | None = None,
) -> None:
    """Configure legio loggers.

    By default only sets the level on the ``legio.*`` logger tree; it creates a
    ``StreamHandler`` only when needed so events are visible. If ``root`` is
    true, it also sets the level on the root logger (for convenience in
    scripts/tests); otherwise the consumer's existing config is preserved.
    """
    fmt = format_string or ("%(asctime)s %(levelname)-8s %(name)s %(message)s")
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt))

    # Promote the whole legio.* tree to be handled by our handler.
    package_logger = logging.getLogger(_LOGGER_PREFIX.rstrip("."))
    package_logger.handlers.clear()
    package_logger.addHandler(handler)
    package_logger.setLevel(level)
    package_logger.propagate = False

    if root:
        logging.getLogger().setLevel(level)


def get_legio_logger(name: str) -> logging.Logger:
    """Return a spacer logger nested under the ``legio.*`` tree."""
    return logging.getLogger(f"{_LOGGER_PREFIX}{name}")


__all__ = ["configure", "get_legio_logger"]
