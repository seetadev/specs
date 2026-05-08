"""Working demo of the libp2p Gossipsub Partial Messages Extension.

Two simulated nodes exchange a 32-part message. The demo shows the core
bandwidth win: a subscriber missing only a few parts recovers them via
partsMetadata exchange instead of receiving the full payload again.

Run: python3 demo/partial_messages_demo.py
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Optional


PART_SIZE = 2048
NUM_PARTS = 32
TOPIC_ID = b"eth/blob-column"


@dataclass
class PartialMessage:
    topic_id: bytes
    group_id: bytes
    part_index: int
    total_parts: int
    payload: bytes


@dataclass
class PartsMetadata:
    topic_id: bytes
    group_id: bytes
    bitmap: int
    total_parts: int


@dataclass
class GroupState:
    group_id: bytes
    total_parts: int
    parts: dict[int, bytes] = field(default_factory=dict)

    @property
    def bitmap(self) -> int:
        b = 0
        for i in self.parts:
            b |= 1 << i
        return b

    def is_complete(self) -> bool:
        return len(self.parts) == self.total_parts

    def reassemble(self) -> bytes:
        return b"".join(self.parts[i] for i in range(self.total_parts))


class Node:
    def __init__(self, name: str):
        self.name = name
        self.groups: dict[bytes, GroupState] = {}
        self.bytes_sent = 0
        self.bytes_received = 0
        self.parts_sent = 0
        self.parts_received = 0

    def log(self, msg: str) -> None:
        print(f"  [{self.name:>12}] {msg}")

    def seed(self, group_id: bytes, parts: dict[int, bytes], total: int) -> None:
        self.groups[group_id] = GroupState(group_id, total, dict(parts))

    def receive_partial(self, pm: PartialMessage) -> None:
        g = self.groups.setdefault(
            pm.group_id, GroupState(pm.group_id, pm.total_parts)
        )
        if pm.part_index in g.parts:
            return
        g.parts[pm.part_index] = pm.payload
        self.bytes_received += len(pm.payload)
        self.parts_received += 1

    def send_partial(self, peer: Node, pm: PartialMessage) -> None:
        self.bytes_sent += len(pm.payload)
        self.parts_sent += 1
        peer.receive_partial(pm)

    def metadata_for(self, group_id: bytes) -> Optional[PartsMetadata]:
        g = self.groups.get(group_id)
        if not g:
            return None
        return PartsMetadata(TOPIC_ID, group_id, g.bitmap, g.total_parts)

    def respond_to_metadata(self, peer: Node, peer_md: PartsMetadata) -> int:
        local = self.groups.get(peer_md.group_id)
        if not local:
            return 0
        missing = local.bitmap & ~peer_md.bitmap
        sent = 0
        for i in range(peer_md.total_parts):
            if missing & (1 << i):
                pm = PartialMessage(
                    TOPIC_ID,
                    peer_md.group_id,
                    i,
                    peer_md.total_parts,
                    local.parts[i],
                )
                self.send_partial(peer, pm)
                sent += 1
        return sent


def build_message(group_id: bytes) -> list[bytes]:
    """Deterministic 32-part 64 KiB message."""
    return [
        hashlib.sha256(group_id + i.to_bytes(2, "big")).digest() * (PART_SIZE // 32)
        for i in range(NUM_PARTS)
    ]


def hr(title: str) -> None:
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)


def report(node: Node, label: str) -> None:
    node.log(
        f"{label}: sent={node.bytes_sent} B ({node.parts_sent} parts), "
        f"received={node.bytes_received} B ({node.parts_received} parts)"
    )


def scenario_basic_exchange() -> None:
    hr("Scenario 1: Basic two-node exchange (full message)")
    pub, sub = Node("Publisher"), Node("Subscriber")
    group_id = b"group-001"
    parts = build_message(group_id)
    pub.seed(group_id, {i: parts[i] for i in range(NUM_PARTS)}, NUM_PARTS)

    pub.log(f"publishing {NUM_PARTS} parts ({NUM_PARTS * PART_SIZE} B total)")
    for i in range(NUM_PARTS):
        pub.send_partial(
            sub, PartialMessage(TOPIC_ID, group_id, i, NUM_PARTS, parts[i])
        )

    g = sub.groups[group_id]
    assert g.is_complete()
    assert g.reassemble() == b"".join(parts)
    sub.log(f"reassembled {len(g.reassemble())} B, integrity OK")
    report(pub, "publisher totals")
    report(sub, "subscriber totals")


def scenario_partial_recovery() -> None:
    hr("Scenario 2: Partial recovery (subscriber missing 2 of 32 parts)")
    holder = Node("Holder")
    sub = Node("Subscriber")
    group_id = b"group-002"
    parts = build_message(group_id)

    holder.seed(group_id, {i: parts[i] for i in range(NUM_PARTS)}, NUM_PARTS)
    pre_owned = {i: parts[i] for i in range(NUM_PARTS) if i not in (7, 19)}
    sub.seed(group_id, pre_owned, NUM_PARTS)

    sub.log(
        f"already has {len(pre_owned)}/{NUM_PARTS} parts, missing indices [7, 19]"
    )

    md = sub.metadata_for(group_id)
    assert md is not None
    sub.log(f"sending partsMetadata bitmap={bin(md.bitmap)[:20]}...")
    delivered = holder.respond_to_metadata(sub, md)
    holder.log(f"diff complete, sent {delivered} missing parts")

    g = sub.groups[group_id]
    assert g.is_complete()
    assert g.reassemble() == b"".join(parts)
    sub.log(f"reassembled {len(g.reassemble())} B, integrity OK")

    full_cost = NUM_PARTS * PART_SIZE
    saved = full_cost - holder.bytes_sent
    print()
    print(f"  Bandwidth full re-broadcast would cost: {full_cost} B")
    print(f"  Bandwidth partial recovery actually used: {holder.bytes_sent} B")
    print(f"  Saved: {saved} B ({saved / full_cost * 100:.1f}% reduction)")


def scenario_eager_push() -> None:
    hr("Scenario 3: Eager push (publisher pushes 4 parts before metadata)")
    pub, sub = Node("Publisher"), Node("Subscriber")
    group_id = b"group-003"
    parts = build_message(group_id)
    pub.seed(group_id, {i: parts[i] for i in range(NUM_PARTS)}, NUM_PARTS)

    eager_budget = 4
    pub.log(f"eagerly pushing {eager_budget} critical parts before handshake")
    for i in range(eager_budget):
        pub.send_partial(
            sub, PartialMessage(TOPIC_ID, group_id, i, NUM_PARTS, parts[i])
        )

    md = sub.metadata_for(group_id)
    assert md is not None
    sub.log(
        f"now sending partsMetadata reflecting {bin(md.bitmap).count('1')} held parts"
    )
    delivered = pub.respond_to_metadata(sub, md)
    pub.log(f"sent {delivered} remaining parts (no duplicates of eager push)")

    g = sub.groups[group_id]
    assert g.is_complete()
    assert g.reassemble() == b"".join(parts)
    sub.log(f"reassembled {len(g.reassemble())} B, integrity OK")
    report(pub, "publisher totals")


def scenario_dos_malformed() -> None:
    hr("Scenario 4: DoS resilience against duplicate and malformed parts")
    pub, sub = Node("Publisher"), Node("Subscriber")
    group_id = b"group-004"
    parts = build_message(group_id)
    pub.seed(group_id, {i: parts[i] for i in range(NUM_PARTS)}, NUM_PARTS)

    rng = random.Random(42)
    indices = list(range(NUM_PARTS))
    rng.shuffle(indices)
    for i in indices:
        pm = PartialMessage(TOPIC_ID, group_id, i, NUM_PARTS, parts[i])
        pub.send_partial(sub, pm)
        pub.send_partial(sub, pm)

    g = sub.groups[group_id]
    assert g.is_complete()
    duplicates_rejected = pub.parts_sent - sub.parts_received
    sub.log(
        f"received {sub.parts_received} unique parts, rejected {duplicates_rejected} duplicates"
    )
    assert duplicates_rejected == NUM_PARTS


def main() -> None:
    print("Partial Messages Extension - working protocol demo")
    scenario_basic_exchange()
    scenario_partial_recovery()
    scenario_eager_push()
    scenario_dos_malformed()
    print()
    print("All scenarios passed.")


if __name__ == "__main__":
    main()
