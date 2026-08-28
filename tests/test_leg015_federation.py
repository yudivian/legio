"""Red contract tests for LEG-015 — Federation contract v1.

These tests define the public contract for symmetric node federation: the
capacity-derived catalog with versioned agent interfaces, work-item deposit with
interface conformance, idempotency by task id (dedup on the acceptor side) and
the write-before-ack outbox (at-least-once, read-then-ack).

The module imported here (``legio.fed``) does NOT exist yet. This file is
intentionally red: it must fail because the production code is not implemented.
"""

from __future__ import annotations

import pytest
from legio.fed import (
    AgentInterface,
    Catalog,
    Federation,
    InterfaceMismatchError,
    UnknownPeerError,
    WorkItem,
    WorkItemReceipt,
    catalog,
    outbox_ack,
    outbox_poll,
    submit_work_item,
)


async def test_catalog_derived_from_capacity_lists_versioned_interfaces() -> None:
    node = Federation(node_id="node-a", peers=["node-b"])
    node.register_capacity(
        agent="flow_alpha", interface=AgentInterface(capability="flow_alpha", schema_version=1)
    )
    node.register_capacity(
        agent="flow_beta", interface=AgentInterface(capability="flow_beta", schema_version=2)
    )

    cat = await catalog(node)
    assert isinstance(cat, Catalog)
    assert set(cat.agents) == {"flow_alpha", "flow_beta"}
    assert cat.agents["flow_alpha"].capability == "flow_alpha"
    assert cat.agents["flow_alpha"].schema_version == 1
    assert cat.agents["flow_beta"].schema_version == 2


async def test_schema_version_mismatch_rejects_work_item() -> None:
    author = Federation(node_id="node-a", peers=["node-b"])
    author.register_peer_catalog(
        "node-b", [AgentInterface(capability="flow_alpha", schema_version=1)]
    )

    with pytest.raises(InterfaceMismatchError):
        await submit_work_item(
            author,
            peer_id="node-b",
            agent="flow_alpha",
            interface=AgentInterface(capability="flow_alpha", schema_version=2),
            payload={"raw": 1},
            task_id="W-1",
        )


async def test_work_item_to_unlisted_peer_is_rejected() -> None:
    author = Federation(node_id="node-a", peers=["node-b"])

    with pytest.raises(UnknownPeerError):
        await submit_work_item(
            author,
            peer_id="node-c",
            agent="flow_alpha",
            interface=AgentInterface(capability="flow_alpha", schema_version=1),
            payload={"raw": 1},
            task_id="W-2",
        )


async def test_work_item_deposited_into_acceptor_queue() -> None:
    acceptor = Federation(node_id="node-b", peers=["node-a"])
    acceptor.register_capacity(
        agent="flow_alpha", interface=AgentInterface(capability="flow_alpha", schema_version=1)
    )

    author = Federation(node_id="node-a", peers=["node-b"])
    author.register_peer_catalog(
        "node-b", [AgentInterface(capability="flow_alpha", schema_version=1)]
    )

    receipt = await submit_work_item(
        author,
        peer_id="node-b",
        agent="flow_alpha",
        interface=AgentInterface(capability="flow_alpha", schema_version=1),
        payload={"raw": 1},
        task_id="W-3",
    )
    assert isinstance(receipt, WorkItemReceipt)
    assert receipt.id == "W-3"
    assert receipt.deposited is True
    assert receipt.deduplicated is False

    items = list(acceptor.queue("flow_alpha"))
    assert len(items) == 1
    assert items[0].id == "W-3"
    assert items[0].payload == {"raw": 1}


async def test_duplicate_work_item_same_id_is_not_deposited_twice() -> None:
    acceptor = Federation(node_id="node-b", peers=["node-a"])
    acceptor.register_capacity(
        agent="flow_alpha", interface=AgentInterface(capability="flow_alpha", schema_version=1)
    )

    author = Federation(node_id="node-a", peers=["node-b"])
    author.register_peer_catalog(
        "node-b", [AgentInterface(capability="flow_alpha", schema_version=1)]
    )

    first = await submit_work_item(
        author,
        peer_id="node-b",
        agent="flow_alpha",
        interface=AgentInterface(capability="flow_alpha", schema_version=1),
        payload={"raw": 1},
        task_id="W-4",
    )
    second = await submit_work_item(
        author,
        peer_id="node-b",
        agent="flow_alpha",
        interface=AgentInterface(capability="flow_alpha", schema_version=1),
        payload={"raw": 2},
        task_id="W-4",
    )

    assert first.deposited is True
    assert second.deposited is False
    assert second.deduplicated is True

    items = list(acceptor.queue("flow_alpha"))
    assert len(items) == 1
    assert items[0].id == "W-4"
    assert items[0].payload == {"raw": 1}


async def test_outbox_read_does_not_consume_before_ack() -> None:
    author = Federation(node_id="node-a", peers=["node-b"])
    author.outbox.deposit(WorkItem(id="W-5", agent="flow_alpha", payload={"raw": 1}))

    first = await outbox_poll(author)
    second = await outbox_poll(author)
    assert [item.id for item in first] == ["W-5"]
    assert first == second


async def test_outbox_read_then_ack_leaves_outbox_empty() -> None:
    author = Federation(node_id="node-a", peers=["node-b"])
    author.outbox.deposit(WorkItem(id="W-6", agent="flow_alpha", payload={"raw": 1}))

    batch = await outbox_poll(author)
    assert [item.id for item in batch] == ["W-6"]

    await outbox_ack(author, "W-6")

    remainder = await outbox_poll(author)
    assert remainder == []
