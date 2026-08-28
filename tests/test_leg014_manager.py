"""Red contract tests for LEG-014 — Mini-manager & client pseudo-agent v1.

These tests define the public contract for the mini-manager: ``submit`` /
``status`` over boards, the internal ``client:{task_id}`` pseudo-agent queue that
receives root results, task ownership tagging (per LEG-017), root-token
semantics (per LEG-011) and clean / reaper-driven termination.

The modules imported here (``legio.manager``, ``legio.manager.client``,
``legio.flow``, ``legio.primitives``) do NOT exist yet. This file is
intentionally red: it must fail because the production code is not implemented.
"""

from __future__ import annotations

import pytest
from legio.flow import FlowToken
from legio.manager import Reaper, TaskState, status, submit
from legio.manager.client import ClientPseudoAgent
from legio.primitives import Board


def test_submit_returns_task_id_and_tags_owner() -> None:
    task_id = submit("client-a", "flow_alpha", {"raw": 1})
    assert isinstance(task_id, str)
    assert task_id

    entry = status(task_id, "client-a")
    assert entry.task_id == task_id
    assert entry.owner == "client-a"


def test_root_result_lands_in_results_board_readable_via_status() -> None:
    task_id = submit("client-a", "flow_alpha", {"raw": 1})

    results_board = Board(f"results:{task_id}")
    results_board["output"] = {"raw": 1, "kind": "ok"}

    entry = status(task_id, "client-a")
    assert entry.output == {"raw": 1, "kind": "ok"}
    assert entry.result_key == f"results:{task_id}"


def test_status_is_scoped_to_the_owning_client() -> None:
    task_id = submit("client-a", "flow_alpha", {"raw": 1})

    with pytest.raises(PermissionError):
        status(task_id, "client-b")

    with pytest.raises(PermissionError):
        status(task_id, None)


def test_submitted_task_holds_root_token_targeting_client_queue() -> None:
    task_id = submit("client-a", "flow_alpha", {"raw": 1})

    entry = status(task_id, "client-a")
    token = entry.token
    assert isinstance(token, FlowToken)
    assert token.root is True
    assert token.task_id == task_id
    assert token.ultimate_return_agent_id == f"client:{task_id}"


def test_client_pseudo_agent_names_its_own_queue() -> None:
    pseudo = ClientPseudoAgent(task_id="T-00")
    assert pseudo.agent_id == "client:T-00"


def test_termination_request_marks_state_client_terminated() -> None:
    task_id = submit("client-a", "flow_alpha", {"raw": 1})

    ClientPseudoAgent(task_id=task_id).handle_termination_request()

    entry = status(task_id, "client-a")
    assert entry.state is TaskState.CLIENT_TERMINATED


def test_termination_drains_client_pseudo_agent_queue() -> None:
    task_id = submit("client-a", "flow_alpha", {"raw": 1})
    pseudo = ClientPseudoAgent(task_id=task_id)

    remaining = pseudo.drain()
    assert remaining == []


def test_reaper_cancels_stuck_client_queues() -> None:
    task_id = submit("client-a", "flow_alpha", {"raw": 1})

    reaper = Reaper()
    cancelled = reaper.reap_clients()
    assert task_id in cancelled

    entry = status(task_id, "client-a")
    assert entry.state is TaskState.CLIENT_TERMINATED
