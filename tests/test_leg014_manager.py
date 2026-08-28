"""Red contract tests for LEG-014 — Mini-manager & client pseudo-agent v1.

These tests pin the public contract for the mini-manager: async ``submit`` /
``status`` over the real (async, scope-based) ``legio.primitives.Board``, the
internal ``client:{task_id}`` pseudo-agent queue that receives the root result,
task ownership tagging (per LEG-017), root-token semantics (per LEG-011) and
clean / reaper-driven termination.

The modules imported here (``legio.manager``, ``legio.manager.client``,
``legio.flow``, ``legio.primitives``) do NOT all exist yet. This file is
intentionally red: it must fail because the production code is not implemented.
"""

from __future__ import annotations

import pytest

from legio.flow import FlowToken
from legio.manager import Reaper, TaskState, reset_manager, results_board, status, submit
from legio.manager.client import ClientPseudoAgent


@pytest.fixture(autouse=True)
def reset_substrate() -> None:
    reset_manager()


@pytest.mark.asyncio
async def test_submit_returns_task_id_and_tags_owner() -> None:
    task_id = await submit("client-a", "flow_alpha", {"raw": 1})
    assert isinstance(task_id, str)
    assert task_id

    entry = await status(task_id, "client-a")
    assert entry.task_id == task_id
    assert entry.owner == "client-a"
    assert entry.output is None


@pytest.mark.asyncio
async def test_root_result_lands_in_results_board_readable_via_status() -> None:
    task_id = await submit("client-a", "flow_alpha", {"raw": 1})

    result_board = await results_board()
    await result_board.set(task_id, {"output": {"raw": 1, "kind": "ok"}})

    entry = await status(task_id, "client-a")
    assert entry.output == {"raw": 1, "kind": "ok"}
    assert entry.result_key == f"results:{task_id}"
    assert entry.state is TaskState.COMPLETED


@pytest.mark.asyncio
async def test_status_is_scoped_to_the_owning_client() -> None:
    task_id = await submit("client-a", "flow_alpha", {"raw": 1})

    with pytest.raises(PermissionError):
        await status(task_id, "client-b")

    with pytest.raises(PermissionError):
        await status(task_id, None)


@pytest.mark.asyncio
async def test_submitted_task_holds_root_token_targeting_client_queue() -> None:
    task_id = await submit("client-a", "flow_alpha", {"raw": 1})

    entry = await status(task_id, "client-a")
    token = entry.token
    assert isinstance(token, FlowToken)
    assert token.root is True
    assert token.task_id == task_id
    assert token.ultimate_return_agent_id == f"client:{task_id}"


def test_client_pseudo_agent_names_its_own_queue() -> None:
    pseudo = ClientPseudoAgent(task_id="T-00")
    assert pseudo.agent_id == "client:T-00"


@pytest.mark.asyncio
async def test_termination_request_marks_state_client_terminated() -> None:
    task_id = await submit("client-a", "flow_alpha", {"raw": 1})

    ClientPseudoAgent(task_id=task_id).handle_termination_request()

    entry = await status(task_id, "client-a")
    assert entry.state is TaskState.CLIENT_TERMINATED


@pytest.mark.asyncio
async def test_termination_drains_client_pseudo_agent_queue() -> None:
    task_id = await submit("client-a", "flow_alpha", {"raw": 1})
    pseudo = ClientPseudoAgent(task_id=task_id)

    remaining = await pseudo.drain()
    assert remaining == []


@pytest.mark.asyncio
async def test_reaper_cancels_stuck_client_queues() -> None:
    task_id = await submit("client-a", "flow_alpha", {"raw": 1})

    reaper = Reaper()
    cancelled = await reaper.reap_clients()
    assert task_id in cancelled

    entry = await status(task_id, "client-a")
    assert entry.state is TaskState.CLIENT_TERMINATED
