# Gossipsub v1.4: Message Segmentation Mechanisms

| Document Type   | Segmentation Reference                               |
| --------------- | ---------------------------------------------------- |
| Specification   | gossipsub-v1.4 Large Message Propagation             |
| Status          | Working Draft                                        |
| Author          | [@NomzzNJS](https://github.com/NomzzNJS)             |
| Created         | 2026-05-16                                           |

---

## 1. Overview

This document specifies the message segmentation (fragmentation) and
reassembly mechanisms for the Gossipsub v1.4 Large Message Propagation
extension. It provides formal algorithms, edge case handling, state machine
definitions, and implementation guidance for splitting large messages into
fragments and reconstructing them at the receiver.

---

## 2. Fragmentation Algorithm

### 2.1 When to Fragment

A message MUST be fragmented when its serialized payload size exceeds the
configured `fragmentation_threshold` parameter:

```
SHOULD_FRAGMENT(message) → bool:
    return serialized_size(message.data) > fragmentation_threshold
```

**Default**: `fragmentation_threshold = 65536` bytes (64 KiB)

Messages at or below the threshold are transmitted as standard gossipsub
publish messages — no fragmentation is applied.

### 2.2 Fragment Generation

Given a message `M` with payload of `S` bytes:

```
FRAGMENT(M, fragment_size) → Fragment[]:
    if S <= fragmentation_threshold:
        return TRANSMIT_NORMAL(M)

    message_id = compute_message_id(M)
    num_fragments = ceil(S / fragment_size)
    fragments = []

    for i in range(0, num_fragments):
        start = i * fragment_size
        end = min(start + fragment_size, S)
        fragment_data = M.data[start:end]

        fragments.append(LargeMessageFragment {
            messageID:      message_id,
            fragmentIndex:  i,
            totalFragments: num_fragments,
            fragmentData:   fragment_data,
            topicID:        M.topic
        })

    return fragments
```

### 2.3 Fragment Properties

For a message of `S` bytes with `fragment_size = F`:

```
num_fragments     = ceil(S / F)
full_fragment_size = F                    (fragments 0 to num_fragments - 2)
last_fragment_size = S - (num_fragments - 1) × F   (fragment num_fragments - 1)
```

**Invariants** (MUST hold for all fragments):

| Property | Constraint |
|----------|-----------|
| `fragmentIndex` | `0 <= fragmentIndex < totalFragments` |
| `totalFragments` | `totalFragments == ceil(S / fragment_size)` |
| `fragmentData.length` | `== fragment_size` for all except last fragment |
| `fragmentData.length` (last) | `1 <= length <= fragment_size` |
| `messageID` | Identical across all fragments of the same message |
| `topicID` | Identical across all fragments of the same message |

### 2.4 Size Examples

| Message Size | Fragment Size | Fragments | Last Fragment Size |
|-------------|--------------|-----------|-------------------|
| 128 KiB | 64 KiB | 2 | 64 KiB |
| 200 KiB | 64 KiB | 4 | 8 KiB |
| 256 KiB | 64 KiB | 4 | 64 KiB |
| 512 KiB | 64 KiB | 8 | 64 KiB |
| 1 MB | 64 KiB | 16 | 64 KiB |
| 1 MB + 1 B | 64 KiB | 17 | 1 B |
| 100 KiB | 64 KiB | 2 | 36 KiB |

---

## 3. Reassembly Algorithm

### 3.1 Reassembly Buffer

Each peer maintains a reassembly buffer map:

```
Type ReassemblyBuffer:
    fragments:        Map<uint32, bytes>   // fragmentIndex → fragmentData
    total_fragments:  uint32               // expected total count
    topic_id:         string               // for validation
    received_bytes:   uint64               // running total of received data
    created_at:       Timestamp            // for timeout tracking
    source_peer:      PeerID               // the peer that sent the fragments
```

The reassembly buffer map is keyed by `(source_peer, messageID)`:

```
reassembly_buffers: Map<(PeerID, bytes), ReassemblyBuffer>
```

### 3.2 Fragment Reception Algorithm

```
ON_RECEIVE_FRAGMENT(sender, fragment):
    key = (sender, fragment.messageID)

    // Rate limit: check per-peer buffer count
    if count_buffers_for_peer(sender) >= max_pending_fragments:
        DROP(fragment)
        return

    // Check global memory limit
    if total_reassembly_memory() >= global_reassembly_limit:
        DROP(fragment)
        return

    if key not in reassembly_buffers:
        // Create new buffer
        reassembly_buffers[key] = ReassemblyBuffer {
            fragments:       {},
            total_fragments: fragment.totalFragments,
            topic_id:        fragment.topicID,
            received_bytes:  0,
            created_at:      now(),
            source_peer:     sender
        }

        // Send IMRECEIVING to mesh peers (first fragment triggers this)
        SEND_IMRECEIVING(fragment.messageID, fragment.topicID)

    buffer = reassembly_buffers[key]

    // Validate consistency
    if fragment.totalFragments != buffer.total_fragments:
        DISCARD_BUFFER(key)
        PENALIZE(sender, P4)  // inconsistent totalFragments
        return

    if fragment.topicID != buffer.topic_id:
        DISCARD_BUFFER(key)
        PENALIZE(sender, P4)  // inconsistent topicID
        return

    if fragment.fragmentIndex >= buffer.total_fragments:
        DROP(fragment)  // out of range
        return

    if fragment.fragmentIndex in buffer.fragments:
        DROP(fragment)  // duplicate fragment
        return

    // Store fragment
    buffer.fragments[fragment.fragmentIndex] = fragment.fragmentData
    buffer.received_bytes += len(fragment.fragmentData)

    // Forward fragment to v1.4 mesh peers (pipeline parallel relay)
    FORWARD_FRAGMENT(fragment)

    // Check if reassembly is complete
    if len(buffer.fragments) == buffer.total_fragments:
        REASSEMBLE(key)
```

### 3.3 Reassembly Completion

```
REASSEMBLE(key):
    buffer = reassembly_buffers[key]

    // Reconstruct message by concatenating fragments in order
    payload = bytes()
    for i in range(0, buffer.total_fragments):
        payload.append(buffer.fragments[i])

    // Compute message ID and validate
    reconstructed_id = compute_message_id(payload, buffer.topic_id)

    if reconstructed_id != key.messageID:
        PENALIZE(buffer.source_peer, P4)  // invalid message
        DISCARD_BUFFER(key)
        return

    // Application-level validation
    validation_result = VALIDATE(payload, buffer.topic_id)

    if validation_result == REJECT:
        PENALIZE(buffer.source_peer, P4)
        DISCARD_BUFFER(key)
        return

    // Success: deliver to application and add to mcache
    DELIVER(payload, buffer.topic_id)
    mcache.put(reconstructed_id, payload)

    // Send IDONTWANT to suppress further sends
    SEND_IDONTWANT(reconstructed_id)

    DISCARD_BUFFER(key)
```

---

## 4. Reassembly State Machine

### 4.1 States

```
┌─────────┐    First fragment     ┌────────────┐
│  IDLE   │──── or PREAMBLE ─────▶│ RECEIVING  │
└─────────┘                       └─────┬──┬───┘
                                        │  │
                              ┌─────────┘  └──────────┐
                              │                        │
                              ▼                        ▼
                       ┌────────────┐          ┌─────────────┐
                       │  COMPLETE  │          │   TIMEOUT   │
                       │            │          │             │
                       │ Reassemble │          │ Discard all │
                       │ Validate   │          │ fragments   │
                       │ Deliver    │          │             │
                       └──────┬─────┘          └──────┬──────┘
                              │                        │
                              ▼                        ▼
                       ┌────────────┐          ┌─────────────┐
                       │  VALID     │          │  DISCARDED  │
                       │            │          │             │
                       │ → mcache   │          │ → penalty   │
                       │ → deliver  │          │   (maybe)   │
                       │ → IDONTWANT│          │             │
                       └────────────┘          └─────────────┘
```

### 4.2 State Transitions

| From | To | Trigger | Action |
|------|----|---------|--------|
| IDLE | RECEIVING | First fragment or PREAMBLE received | Create buffer, send IMRECEIVING |
| RECEIVING | RECEIVING | Additional fragment received | Store fragment, forward to v1.4 peers |
| RECEIVING | COMPLETE | All `totalFragments` fragments received | Begin reassembly |
| RECEIVING | TIMEOUT | `fragment_timeout` elapsed | Discard buffer |
| COMPLETE | VALID | Message passes validation | Deliver, add to mcache, send IDONTWANT |
| COMPLETE | DISCARDED | Message fails validation | Apply P₄ penalty to sender |
| TIMEOUT | DISCARDED | — | Optionally apply P₇ if sender pattern is suspicious |

---

## 5. Fragment Forwarding (Pipeline Parallel Relay)

### 5.1 The Core Optimization

The key latency improvement in v1.4 comes from forwarding fragments
*before* full reassembly. This transforms the propagation model:

```
Without fragmentation (store-and-forward):
  Hop 1: |████████████████████| 1.0s
  Hop 2:                      |████████████████████| 1.0s
  Hop 3:                                            |████████████████████| 1.0s
  Total: 3.0s

With fragmentation (pipeline parallel):
  Hop 1: |████|████|████|████| 1.0s
  Hop 2:      |████|████|████|████| 1.0s
  Hop 3:           |████|████|████|████| 1.0s
  Total: 1.75s (42% faster for 3 hops, 4 fragments)
```

### 5.2 Forwarding Decision Matrix

| Received From | Forward To | Condition | Action |
|--------------|-----------|-----------|--------|
| Any peer | v1.4 peer in mesh | Always | Forward individual fragment immediately |
| Any peer | Non-v1.4 peer in mesh | After full reassembly only | Send complete message |
| Any peer | Peer with IDONTWANT for this messageID | Never | Skip (suppressed) |
| Any peer | Peer with IMRECEIVING for this messageID | Never | Skip (suppressed) |

### 5.3 Forwarding Algorithm

```
FORWARD_FRAGMENT(fragment):
    peers = mesh[fragment.topicID]

    for peer in peers:
        if fragment.messageID in peer.dont_send_message_ids:
            continue  // Suppressed by IDONTWANT or IMRECEIVING

        if peer.supports_v14:
            // Pipeline relay: forward immediately
            SEND(peer, RPC { largeMessageFragments: [fragment] })
        else:
            // Non-v1.4 peer: queue for post-reassembly delivery
            queue_for_complete_delivery(peer, fragment.messageID)
```

---

## 6. Staggered Transmission

### 6.1 Overview

Staggering sends fragments (or complete messages) to mesh peers
**sequentially** with delays between each, rather than simultaneously.

### 6.2 Algorithm

```
STAGGERED_SEND(message_or_fragments, topic):
    if message_size < stagger_threshold:
        // Small messages: send to all peers simultaneously
        SEND_TO_ALL(mesh[topic], message_or_fragments)
        return

    peers = mesh[topic]
    SORT(peers, by=heuristic)  // score, latency, or random

    // Send PREAMBLE to ALL peers first (not staggered)
    if message_size > preamble_threshold:
        for peer in peers:
            SEND_PREAMBLE(peer, message_id, message_size, topic)

    // Stagger the actual data transmission
    for peer in peers:
        if message_id in peer.dont_send_message_ids:
            continue  // Already suppressed by IDONTWANT or IMRECEIVING

        if peer.supports_v14:
            SEND_FRAGMENTS(peer, fragments)
        else:
            SEND_COMPLETE(peer, full_message)

        WAIT(stagger_interval)  // Default: 200ms
```

### 6.3 Peer Ordering Heuristics

| Heuristic | Description | When to Use |
|-----------|-------------|-------------|
| **Score-based** | Highest-scoring peers first | Default — ensures best peers get data soonest |
| **Latency-based** | Lowest-latency peers first | When minimizing propagation depth matters |
| **Random** | Random permutation each time | When peer scores are not available |
| **Round-robin** | Rotate starting peer each message | Ensures fair bandwidth distribution |

### 6.4 Interaction with IDONTWANT

```
Timeline (staggered, 3 peers, 200ms interval):

  t=0ms     Send to Peer A
  t=200ms   Send to Peer B
              ← Peer A sends IDONTWANT (received full msg at ~100ms)
              ← Peer B suppressed if IDONTWANT arrived
  t=400ms   Send to Peer C
              ← Peer C almost certainly suppressed
```

Without staggering, all three sends happen at t=0, and IDONTWANT arrives
too late to prevent any duplicates.

---

## 7. PREAMBLE and IMRECEIVING Coordination

### 7.1 Complete Coordination Flow

```
SENDER_RELAY(message, topic):
    // Phase 1: Announce
    if message_size > preamble_threshold:
        for peer in mesh[topic]:
            SEND(peer, ControlPreamble {
                messageID: message_id,
                messageSize: message_size,
                topicID: topic
            })

    // Phase 2: Fragment and stagger
    fragments = FRAGMENT(message, fragment_size)
    STAGGERED_SEND(fragments, topic)


RECEIVER_ON_PREAMBLE(sender, preamble):
    // Record incoming message
    receiving_messages.add(preamble.messageID)

    // If already have: send IDONTWANT
    if preamble.messageID in seen_cache:
        SEND(sender, ControlIDontWant {
            messageIDs: [preamble.messageID]
        })
        return

    // If already receiving from another peer: send IMRECEIVING
    if preamble.messageID in reassembly_buffers:
        BROADCAST_IMRECEIVING(preamble.messageID, preamble.topicID)
        return

    // New message: pre-allocate buffer, broadcast IMRECEIVING
    PRE_ALLOCATE_BUFFER(preamble.messageID, preamble.messageSize)
    BROADCAST_IMRECEIVING(preamble.messageID, preamble.topicID)


RECEIVER_ON_IMRECEIVING(sender, imreceiving):
    // Add to suppression set (same set used by IDONTWANT)
    sender.dont_send_message_ids.add(imreceiving.messageID)
```

---

## 8. Resource Management

### 8.1 Memory Limits

| Resource | Limit Parameter | Default | Rationale |
|----------|----------------|---------|-----------|
| Reassembly buffers per peer | `max_pending_fragments` | 16 | Prevents single-peer memory exhaustion |
| Total reassembly memory | `global_reassembly_limit` | 256 MB | Bounds total node memory usage |
| Fragment timeout | `fragment_timeout` | 30 seconds | Prevents indefinite buffer retention |

### 8.2 Cleanup Algorithm (Heartbeat)

```
HEARTBEAT_CLEANUP():
    now = current_time()

    for (key, buffer) in reassembly_buffers:
        if now - buffer.created_at > fragment_timeout:
            // Timeout: discard incomplete reassembly
            LOG("Fragment timeout for message", key.messageID,
                "from", key.source_peer,
                "received", len(buffer.fragments), "/", buffer.total_fragments)
            DISCARD_BUFFER(key)

    // Prune expired IMRECEIVING entries from dont_send_message_ids
    for peer in connected_peers:
        PRUNE_EXPIRED_ENTRIES(peer.dont_send_message_ids)
```

### 8.3 Memory Calculation

```
worst_case_per_peer = max_pending_fragments × max_message_size
                    = 16 × 1 MB = 16 MB

worst_case_total    = num_mesh_peers × worst_case_per_peer
                    = 50 × 16 MB = 800 MB (theoretical max, unrealistic)

practical_total     = global_reassembly_limit = 256 MB (enforced cap)
```

---

## 9. Edge Cases

### 9.1 Single-Fragment Messages

If a message exceeds `fragmentation_threshold` but is smaller than
`fragmentation_threshold + fragment_size`, it produces exactly one fragment:

```
Message size: 70,000 bytes
Fragment size: 65,536 bytes
Threshold: 65,536 bytes

Result: 2 fragments (ceil(70000 / 65536) = 2)
  Fragment 0: 65,536 bytes
  Fragment 1: 4,464 bytes
```

### 9.2 Out-of-Order Fragment Delivery

Fragments MAY arrive in any order. The reassembly buffer handles this by
storing fragments by `fragmentIndex`, not by arrival order:

```
Arrival order: [3, 1, 7, 0, 2, 5, 4, 6]
Buffer state after each arrival:
  After frag 3: {3: data}
  After frag 1: {1: data, 3: data}
  After frag 7: {1: data, 3: data, 7: data}
  ...
  After frag 6: {0: data, 1: data, 2: data, 3: data,
                  4: data, 5: data, 6: data, 7: data}
  → COMPLETE: reassemble in index order [0,1,2,3,4,5,6,7]
```

### 9.3 Duplicate Fragment Handling

Duplicate fragments (same `messageID` and `fragmentIndex` from same sender)
MUST be silently dropped:

```
if fragment.fragmentIndex in buffer.fragments:
    DROP(fragment)  // Already have this fragment
    return
```

### 9.4 Partial Timeout Recovery

If a reassembly times out with some fragments received, the peer can
potentially recover the message via standard IHAVE/IWANT gossip:

```
ON_TIMEOUT(key):
    DISCARD_BUFFER(key)
    // The message may arrive later via IHAVE/IWANT gossip from other peers
    // (standard gossipsub recovery mechanism, unchanged)
```

---

## 10. References

- gossipsub v1.0: [gossipsub-v1.0.md](gossipsub-v1.0.md) — Base protocol
- gossipsub v1.1: [gossipsub-v1.1.md](gossipsub-v1.1.md) — Peer scoring (P₄, P₇)
- gossipsub v1.2: [gossipsub-v1.2.md](gossipsub-v1.2.md) — IDONTWANT
- gossipsub v1.3: [gossipsub-v1.3.md](gossipsub-v1.3.md) — Extensions framework
- Wire Format Specification: [wire-format-v1.4.md](wire-format-v1.4.md)
- arXiv:2504.10365 — Staggering and Fragmentation for Improved Large
  Message Handling in libp2p GossipSub
- arXiv:2505.17337 — PREAMBLE and IMRECEIVING for Improved Large
  Message Handling in libp2p GossipSub
