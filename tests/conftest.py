"""Shared test fixtures over native beaver (LEG-048).

Every test that needs the substrate binds ``legio.manager`` to a fresh local
beaver SQLite database (a temp file) and shares that single ``AsyncBeaverDB``
connection with agents and the worker — the same decoupling a multi-process
deployment gets by opening the same file. No invented substrate layer exists.
"""

from __future__ import annotations

import logging
import os
import tempfile

import pytest
from beaver import AsyncBeaverDB

from legio import manager

logger = logging.getLogger("legio.tests.conftest")


@pytest.fixture
async def beaver_db() -> AsyncBeaverDB:
    """Bind the manager to a fresh temp beaver db; yield the shared connection."""
    d = tempfile.mkdtemp()
    path = os.path.join(d, "test.db")
    await manager.reset_manager(path)
    db = await manager.db()
    try:
        yield db
    finally:
        await manager.close_manager()
        try:
            await db.close()
        except Exception:
            logger.warning("beaver teardown close failed", exc_info=True)
