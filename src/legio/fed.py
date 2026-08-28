"""`legio.fed` — symmetric node federation (LEG-015).

A ``Federation`` is both an author and an acceptor. The catalog is derived from
registered capacity and carries versioned agent interfaces; a work item is only
deposited when the author's view of the peer's interface matches, and is
deduplicated on the acceptor side by task id. Delivery is at-least-once: the
author's outbox is written before ack and read/acked explicitly.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field


class FederationError(Exception):
    """Base class for federation errors."""


class UnknownPeerError(FederationError):
    """The target peer is not a known peer of the author."""


class InterfaceMismatchError(FederationError):
    """The submitted interface does not match the peer's advertised catalog."""


@dataclass
class AgentInterface:
    """A versioned agent capability advertised by a node."""

    capability: str
    schema_version: int


@dataclass
class WorkItem:
    """A unit of remote work handed to an acceptor peer."""

    id: str
    agent: str
    payload: dict


@dataclass
class WorkItemReceipt:
    """The outcome of depositing a work item onto a peer."""

    id: str
    deposited: bool
    deduplicated: bool = False


@dataclass
class Catalog:
    """The advertised capacity of a node: agent -> interface."""

    agents: dict[str, AgentInterface] = field(default_factory=dict)


class Outbox:
    """The author-side at-least-once delivery record (write-before-ack)."""

    def __init__(self) -> None:
        self._items: list[WorkItem] = []

    def deposit(self, item: WorkItem) -> None:
        self._items.append(item)

    def snapshot(self) -> list[WorkItem]:
        return list(self._items)

    def ack(self, item_id: str) -> None:
        self._items = [item for item in self._items if item.id != item_id]


_NODES: dict[str, Federation] = {}


class Federation:
    """A symmetric node that authors work to and accepts work from peers."""

    def __init__(
        self,
        node_id: str,
        peers: Iterable[str] | None = None,
        *,
        register: bool = True,
    ) -> None:
        self.node_id = node_id
        self.peers = list(peers) if peers is not None else []
        self._capacities: dict[str, AgentInterface] = {}
        self._peer_catalogs: dict[str, dict[str, AgentInterface]] = {}
        self._queues: dict[str, list[WorkItem]] = {}
        self._seen: set[str] = set()
        self.outbox = Outbox()
        if register:
            _NODES[node_id] = self

    def register_capacity(self, agent: str, interface: AgentInterface) -> None:
        self._capacities[agent] = interface

    def register_peer_catalog(self, peer_id: str, interfaces: Iterable[AgentInterface]) -> None:
        self._peer_catalogs[peer_id] = {i.capability: i for i in interfaces}

    def queue(self, agent: str) -> list[WorkItem]:
        """Snapshot of the acceptor queue for ``agent``."""
        return list(self._queues.get(agent, []))

    def _accept_work(self, item: WorkItem) -> bool:
        if item.id in self._seen:
            return False
        self._seen.add(item.id)
        self._queues.setdefault(item.agent, []).append(item)
        return True


async def catalog(node: Federation) -> Catalog:
    """Derive the node's catalog from its registered capacity."""
    return Catalog(agents=dict(node._capacities))


async def submit_work_item(
    author: Federation,
    *,
    peer_id: str,
    agent: str,
    interface: AgentInterface,
    payload: dict,
    task_id: str,
) -> WorkItemReceipt:
    """Deposit a work item onto a peer, validating interface and deduping."""
    if peer_id not in author.peers:
        raise UnknownPeerError(f"peer {peer_id!r} is not known to {author.node_id!r}")

    peer_catalog = author._peer_catalogs.get(peer_id)
    if peer_catalog is not None:
        advertised = peer_catalog.get(agent)
        if advertised is None or advertised.schema_version != interface.schema_version:
            raise InterfaceMismatchError(
                f"interface for {agent!r} does not match peer {peer_id!r} catalog"
            )

    acceptor = _NODES.get(peer_id)
    if acceptor is None:
        return WorkItemReceipt(id=task_id, deposited=False)

    deposited = acceptor._accept_work(WorkItem(id=task_id, agent=agent, payload=payload))
    return WorkItemReceipt(id=task_id, deposited=deposited, deduplicated=not deposited)


async def outbox_poll(node: Federation) -> list[WorkItem]:
    """Read the author outbox without consuming (at-least-once)."""
    return node.outbox.snapshot()


async def outbox_ack(node: Federation, work_item_id: str) -> None:
    """Acknowledge a delivered outbox item, removing it."""
    node.outbox.ack(work_item_id)


__all__ = [
    "AgentInterface",
    "Catalog",
    "Federation",
    "FederationError",
    "InterfaceMismatchError",
    "Outbox",
    "UnknownPeerError",
    "WorkItem",
    "WorkItemReceipt",
    "catalog",
    "outbox_ack",
    "outbox_poll",
    "submit_work_item",
]
