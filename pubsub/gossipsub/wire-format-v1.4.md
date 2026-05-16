# Gossipsub v1.4: Wire Format Specification

| Document Type   | Wire Format Reference                                |
| --------------- | ---------------------------------------------------- |
| Specification   | gossipsub-v1.4 Large Message Propagation             |
| Status          | Working Draft                                        |
| Author          | [@NomzzNJS](https://github.com/NomzzNJS)             |
| Created         | 2026-05-16                                           |

---

## 1. Overview

This document provides the complete wire format specification for the Gossipsub
v1.4 Large Message Propagation extension. It defines all new Protobuf messages,
their binary encoding on the wire, field-level semantics, encoding constraints,
and interoperability requirements.

This is the normative reference for implementers building v1.4 support into any
libp2p gossipsub implementation.

### Relationship to Existing Wire Formats

Gossipsub v1.4 extends the existing wire format defined in:

- **v1.0** ([gossipsub-v1.0.md](gossipsub-v1.0.md)): Base `RPC`,
  `ControlMessage`, `ControlIHave`, `ControlIWant`, `ControlGraft`,
  `ControlPrune`
- **v1.2** ([gossipsub-v1.2.md](gossipsub-v1.2.md)): `ControlIDontWant`
  (field 5 in `ControlMessage`)
- **v1.3** ([gossipsub-v1.3.md](gossipsub-v1.3.md)): `ControlExtensions`
  (field 6 in `ControlMessage`), extension registration in
  `extensions.proto`

All v1.4 additions are **backward-compatible**. Older peers will skip unknown
fields per standard protobuf decoding rules.

---

## 2. Protobuf Schema

### 2.1 Complete v1.4 Protobuf Definition

The following protobuf definitions are added to
[`extensions/extensions.proto`](extensions/extensions.proto):

```protobuf
syntax = "proto2";

// =====================================================================
// Extension Registration (v1.3 framework)
// =====================================================================

message ControlExtensions {
    // Canonical extension: Partial Messages
    optional bool partialMessages = 10;

    // Canonical extension: Large Message Handling (v1.4)
    // When set to true, the peer supports fragmentation, staggering,
    // PREAMBLE, and IMRECEIVING mechanisms.
    // See: gossipsub-v1.4.md
    optional bool largeMessageHandling = 11;

    // Experimental extensions use field numbers >= 0x200000
    // (4+ byte varint encoding)
}

// =====================================================================
// Control Messages (added to existing ControlMessage)
// =====================================================================

message ControlMessage {
    // v1.0 control messages
    repeated ControlIHave ihave = 1;
    repeated ControlIWant iwant = 2;
    repeated ControlGraft graft = 3;
    repeated ControlPrune prune = 4;

    // v1.2 control message
    repeated ControlIDontWant idontwant = 5;

    // v1.3 extensions advertisement
    optional ControlExtensions extensions = 6;

    // v1.4 control messages — Large Message Handling
    repeated ControlPreamble preamble = 7;
    repeated ControlImReceiving imreceiving = 8;
}

// =====================================================================
// RPC Message (top-level, added to existing RPC)
// =====================================================================

message RPC {
    // ... existing fields (subscriptions=1, publish=2, control=3) ...

    // Canonical extension: Partial Messages
    optional PartialMessagesExtension partial = 10;

    // v1.4: Large message fragments
    // Fragments are placed at the RPC level (not inside ControlMessage)
    // because they carry application data payload, not control signaling.
    repeated LargeMessageFragment largeMessageFragments = 12;
}

// =====================================================================
// v1.4 New Message Types
// =====================================================================

// PREAMBLE: Sent before transmitting a large message.
// Announces the messageID, total size, and topic so that receivers can:
//   - Pre-allocate reassembly buffers
//   - Respond with IDONTWANT if they already have the message
//   - Send IMRECEIVING to suppress redundant sends from other peers
//
// A peer MUST send PREAMBLE to all mesh peers in the topic before
// beginning fragment transmission when message size > preamble_threshold.
message ControlPreamble {
    // The message ID of the message about to be transmitted.
    // This MUST be the same ID that would be computed by the standard
    // gossipsub message ID function for the full, unfragmented message.
    // Encoding: opaque bytes, typically 32 bytes (SHA-256 hash).
    optional bytes messageID = 1;

    // The total size of the full message payload in bytes.
    // This allows the receiver to pre-allocate a reassembly buffer
    // of the exact required size.
    // Encoding: unsigned 64-bit integer (varint on wire).
    optional uint64 messageSize = 2;

    // The topic ID this message belongs to.
    // Encoding: UTF-8 string.
    optional string topicID = 3;
}

// IMRECEIVING: Sent when a peer begins receiving a large message.
// This is triggered by receiving a PREAMBLE or the first fragment.
//
// Purpose: Provides *immediate* suppression of redundant sends,
// filling the gap left by IDONTWANT (which requires full reception).
//
// Semantics: Advisory only. A peer receiving IMRECEIVING SHOULD add
// the messageID to the sender's dont_send_message_ids set, but
// MAY still send the message. Sending after receiving IMRECEIVING
// MUST NOT be penalized.
message ControlImReceiving {
    // The message ID currently being received.
    // Encoding: opaque bytes, typically 32 bytes.
    optional bytes messageID = 1;
}

// LargeMessageFragment: Carries a single fragment of a large message
// that has been split for pipeline-parallel relay across the mesh.
//
// Fragments are transmitted as individual RPC messages, allowing
// intermediate peers to forward each fragment immediately upon receipt
// without waiting for full message reassembly.
//
// The receiver reassembles fragments by collecting all fragmentIndex
// values [0, totalFragments) for a given messageID.
message LargeMessageFragment {
    // The full message ID this fragment belongs to.
    // MUST match the messageID in any corresponding PREAMBLE.
    // Encoding: opaque bytes, typically 32 bytes.
    optional bytes messageID = 1;

    // 0-based index of this fragment within the sequence.
    // MUST satisfy: 0 <= fragmentIndex < totalFragments.
    // Encoding: unsigned 32-bit integer (varint on wire).
    optional uint32 fragmentIndex = 2;

    // Total number of fragments for this message.
    // MUST be consistent across all fragments of the same messageID.
    // Encoding: unsigned 32-bit integer (varint on wire).
    optional uint32 totalFragments = 3;

    // The fragment payload data.
    // For all fragments except possibly the last, the size MUST equal
    // the configured fragment_size parameter.
    // The last fragment MAY be smaller.
    // Encoding: opaque bytes, length-delimited.
    optional bytes fragmentData = 4;

    // The topic ID the original message belongs to.
    // MUST be consistent across all fragments of the same messageID.
    // Encoding: UTF-8 string.
    optional string topicID = 5;
}
```

---

## 3. Field Number Allocation

### 3.1 Allocation Table

| Parent Message | Field Name | Number | Wire Type | Varint Bytes | Rationale |
|----------------|-----------|--------|-----------|-------------|-----------|
| `ControlExtensions` | `largeMessageHandling` | 11 | 0 (varint) | 1 | Next canonical extension after `partialMessages` (10) |
| `ControlMessage` | `preamble` | 7 | 2 (length-delimited) | 1 | Next sequential after `extensions` (6) |
| `ControlMessage` | `imreceiving` | 8 | 2 (length-delimited) | 1 | Sequential after `preamble` (7) |
| `RPC` | `largeMessageFragments` | 12 | 2 (length-delimited) | 1 | Next available canonical slot after `partial` (10) |

### 3.2 Why Canonical Field Numbers

v1.4 uses **canonical** (small) field numbers rather than experimental (large)
field numbers because:

1. **Formal protocol version**: v1.4 is a versioned protocol extension, not
   an experiment. It follows the v1.2 precedent (IDONTWANT used field 5).
2. **Encoding efficiency**: Field numbers 1–15 encode in a single byte
   (1-byte varint tag). Field numbers ≥ 16 require 2+ bytes. All v1.4 fields
   fall in the 1-byte range, minimizing per-message overhead.
3. **Signaling maturity**: Using canonical field numbers signals to
   implementers that these fields are stable and will not change.

### 3.3 Reserved Field Number Ranges

| Range | Purpose | Used By |
|-------|---------|---------|
| 1–6 | Core gossipsub control messages | v1.0 (1–4), v1.2 (5), v1.3 (6) |
| 7–8 | v1.4 control messages | PREAMBLE (7), IMRECEIVING (8) |
| 9 | Reserved for future control messages | — |
| 10 | Canonical RPC extensions | Partial Messages |
| 11 | Canonical ControlExtensions | Large Message Handling |
| 12 | Canonical RPC extensions | Large Message Fragments |
| 13–15 | Reserved for future canonical extensions | — |
| ≥ 0x200000 | Experimental extensions | Test extensions |

---

## 4. Binary Encoding Details

### 4.1 Wire Type Reference

| Wire Type | ID | Protobuf Types Used in v1.4 |
|-----------|----|-----------------------------|
| Varint | 0 | `bool` (largeMessageHandling), `uint32` (fragmentIndex, totalFragments), `uint64` (messageSize) |
| Length-delimited | 2 | `bytes` (messageID, fragmentData), `string` (topicID), embedded messages (ControlPreamble, ControlImReceiving, LargeMessageFragment) |

### 4.2 Tag Encoding Formula

Each protobuf field is prefixed by a tag byte:

```
tag = (field_number << 3) | wire_type
```

#### v1.4 Tag Values

| Message Context | Field | field_number | wire_type | Tag (decimal) | Tag (hex) |
|-----------------|-------|-------------|-----------|---------------|-----------|
| ControlExtensions | largeMessageHandling | 11 | 0 | 88 | 0x58 |
| ControlMessage | preamble | 7 | 2 | 58 | 0x3A |
| ControlMessage | imreceiving | 8 | 2 | 66 | 0x42 |
| RPC | largeMessageFragments | 12 | 2 | 98 | 0x62 |
| ControlPreamble | messageID | 1 | 2 | 10 | 0x0A |
| ControlPreamble | messageSize | 2 | 0 | 16 | 0x10 |
| ControlPreamble | topicID | 3 | 2 | 26 | 0x1A |
| ControlImReceiving | messageID | 1 | 2 | 10 | 0x0A |
| LargeMessageFragment | messageID | 1 | 2 | 10 | 0x0A |
| LargeMessageFragment | fragmentIndex | 2 | 0 | 16 | 0x10 |
| LargeMessageFragment | totalFragments | 3 | 0 | 24 | 0x18 |
| LargeMessageFragment | fragmentData | 4 | 2 | 34 | 0x22 |
| LargeMessageFragment | topicID | 5 | 2 | 42 | 0x2A |

### 4.3 Encoding Example: ControlPreamble

For a PREAMBLE announcing a 512 KiB message on topic "blocks":

```
ControlPreamble {
  messageID:   <32 bytes: SHA-256 hash>
  messageSize: 524288 (512 × 1024)
  topicID:     "blocks"
}
```

**Byte-level encoding:**

```
Field 1 (messageID): tag=0x0A, length=0x20, data=<32 bytes>
  0A 20 [32 bytes of message ID]

Field 2 (messageSize): tag=0x10, value=524288 (varint)
  524288 in binary: 0000 0000 0000 1000 0000 0000 0000 0000
  Varint encoding (7-bit groups, little-endian, MSB continuation):
  10 80 80 20

Field 3 (topicID): tag=0x1A, length=0x06, data="blocks"
  1A 06 62 6C 6F 63 6B 73
```

**Total encoded size**: 1 + 1 + 32 + 1 + 4 + 1 + 1 + 6 = **47 bytes**

### 4.4 Encoding Example: LargeMessageFragment

For fragment #3 of 8 (64 KiB payload) on topic "blocks":

```
LargeMessageFragment {
  messageID:     <32 bytes>
  fragmentIndex: 3
  totalFragments: 8
  fragmentData:  <65536 bytes>
  topicID:       "blocks"
}
```

**Byte-level encoding:**

```
Field 1 (messageID): 0A 20 [32 bytes]           = 34 bytes
Field 2 (fragmentIndex): 10 03                   = 2 bytes
Field 3 (totalFragments): 18 08                  = 2 bytes
Field 4 (fragmentData): 22 [varint:65536] [data] = 4 + 65536 bytes
Field 5 (topicID): 2A 06 62 6C 6F 63 6B 73      = 8 bytes

Total: 34 + 2 + 2 + 65540 + 8 = 65,586 bytes
Fragment header overhead: 50 bytes (0.076% of payload)
```

### 4.5 Encoding Example: ControlImReceiving

```
ControlImReceiving {
  messageID: <32 bytes>
}

Byte-level: 0A 20 [32 bytes]
Total: 34 bytes
```

---

## 5. Message Size Analysis

### 5.1 Per-Message Overhead

| Message Type | Typical Encoded Size | When Sent | Frequency |
|-------------|---------------------|-----------|-----------|
| `ControlPreamble` | ~47 bytes | Before large message transmission | Once per large message per mesh peer |
| `ControlImReceiving` | ~34 bytes | Upon receiving PREAMBLE or first fragment | Once per large message to all mesh peers |
| `LargeMessageFragment` (header only) | ~50 bytes | Per fragment | `ceil(message_size / fragment_size)` times |
| `ControlExtensions.largeMessageHandling` | 2 bytes | First RPC on stream | Once per connection |

### 5.2 Total Protocol Overhead for a 1 MB Message

```
Parameters:
  message_size     = 1,048,576 bytes (1 MB)
  fragment_size    = 65,536 bytes (64 KiB)
  num_fragments    = ceil(1048576 / 65536) = 16
  mesh_degree      = 8

Overhead per peer:
  PREAMBLE:                1 × 47 bytes  =      47 bytes
  Fragment headers:       16 × 50 bytes  =     800 bytes
  Total overhead:                        =     847 bytes
  Overhead percentage:                   =   0.081%

Overhead across mesh:
  PREAMBLEs:              8 × 47 bytes   =     376 bytes
  IMRECEIVING (from peers): 8 × 34 bytes =     272 bytes
  All fragment headers:   16 × 8 × 50    =   6,400 bytes
  Total control overhead:                =   7,048 bytes
  vs. payload sent:       8 × 1,048,576  = 8,388,608 bytes (without suppression)
  Overhead ratio:                        =   0.084%
```

### 5.3 Comparison with Existing Control Messages

| Control Message | v1.x | Typical Size | Purpose |
|----------------|------|-------------|---------|
| ControlIHave | v1.0 | ~40–200 bytes | Gossip: "I have these message IDs" |
| ControlIWant | v1.0 | ~36–100 bytes | Request: "Send me these messages" |
| ControlGraft | v1.0 | ~10–30 bytes | Mesh: "Add me to your mesh" |
| ControlPrune | v1.0 | ~10–30 bytes | Mesh: "Remove me from your mesh" |
| ControlIDontWant | v1.2 | ~36–100 bytes | Suppress: "I already have this" |
| **ControlPreamble** | **v1.4** | **~47 bytes** | **Announce: "Large message incoming"** |
| **ControlImReceiving** | **v1.4** | **~34 bytes** | **Suppress: "I'm receiving this"** |

v1.4 control messages are comparable in size to existing control messages —
no disproportionate overhead.

---

## 6. RPC Framing and Multiplexing

### 6.1 How v1.4 Messages Fit in the RPC

A single gossipsub RPC can carry any combination of messages:

```
RPC {
  subscriptions: [...]        // Topic subscriptions
  publish: [...]              // Full messages (small, or for non-v1.4 peers)
  control: {                  // Control messages
    ihave: [...]              // v1.0
    iwant: [...]              // v1.0
    graft: [...]              // v1.0
    prune: [...]              // v1.0
    idontwant: [...]          // v1.2
    extensions: {...}         // v1.3
    preamble: [...]           // v1.4 — NEW
    imreceiving: [...]        // v1.4 — NEW
  }
  largeMessageFragments: [...] // v1.4 — NEW (at RPC level)
}
```

### 6.2 Why Fragments Are at RPC Level

`LargeMessageFragment` is placed in the `RPC` message (not inside
`ControlMessage`) because:

1. **Semantic correctness**: Fragments carry **application data** payload,
   not routing/control metadata. This matches the pattern of `publish[]`
   (data) vs. `ControlMessage` (routing).
2. **Processing priority**: Implementations can prioritize control message
   processing over fragment handling.
3. **Size management**: Keeping large fragment payloads out of the control
   message simplifies control message size limits and rate limiting.

### 6.3 Multiplexing Rules

| Scenario | What Goes in the RPC |
|----------|---------------------|
| First RPC on a new stream | `extensions` (with `largeMessageHandling=true`) + any pending control messages |
| Small message relay | `publish[]` with full message (standard gossipsub behavior) |
| Large message relay (first RPC) | `control.preamble[]` + `largeMessageFragments[]` (first batch of fragments) |
| Large message relay (subsequent RPCs) | `largeMessageFragments[]` (remaining fragments) |
| Suppression signal | `control.imreceiving[]` (can be piggybacked on any RPC) |
| Redundancy avoidance | `control.idontwant[]` (existing v1.2, unchanged) |

### 6.4 Control Message Piggybacking

Following the v1.0 piggybacking pattern, v1.4 control messages (`preamble`,
`imreceiving`) CAN be piggybacked on any RPC, not just dedicated control RPCs.
This reduces the total number of network round-trips.

Example: An `IMRECEIVING` message can be piggybacked on a regular publish RPC:

```
RPC {
  publish: [small_message_A, small_message_B]
  control: {
    imreceiving: [{ messageID: <large_msg_hash> }]
  }
}
```

---

## 7. Capability Advertisement

### 7.1 Extension Registration

v1.4 support is advertised using the v1.3 Extensions Control Message framework.
On the first RPC sent on a new stream, a v1.4 peer MUST include:

```protobuf
ControlMessage {
  extensions: ControlExtensions {
    largeMessageHandling: true
  }
}
```

### 7.2 Detection Algorithm

```
on_new_peer_stream(peer, first_rpc):
    if first_rpc.control.extensions.largeMessageHandling == true:
        peer.supports_v14 = true
    else:
        peer.supports_v14 = false

on_relay_large_message(message, peer):
    if peer.supports_v14:
        send_preamble(message, peer)
        send_fragments(message, peer)  // with staggering
    else:
        wait_for_full_reassembly()
        send_complete_message(message, peer)
```

### 7.3 Protocol ID

Peers supporting v1.4 SHOULD advertise protocol ID `/meshsub/1.4.0` in
addition to any previously supported protocol IDs.

---

## 8. Interoperability Constraints

### 8.1 MUST Requirements

| ID | Requirement |
|----|-------------|
| W-1 | `messageID` in `ControlPreamble`, `ControlImReceiving`, and `LargeMessageFragment` MUST use the same message ID computation function as standard gossipsub messages |
| W-2 | `totalFragments` MUST be consistent across all `LargeMessageFragment` messages for the same `messageID` |
| W-3 | `fragmentIndex` MUST be unique per `messageID` and in range `[0, totalFragments)` |
| W-4 | `topicID` MUST be consistent across all fragments and the PREAMBLE for the same `messageID` |
| W-5 | `fragmentData` size MUST NOT exceed the configured `fragment_size` parameter |
| W-6 | The last fragment's `fragmentData` MAY be smaller than `fragment_size` |
| W-7 | The concatenation of `fragmentData` from fragments `[0, totalFragments)` ordered by `fragmentIndex` MUST produce the exact original message bytes |
| W-8 | A peer MUST NOT send `LargeMessageFragment` messages to peers that do not support v1.4 (detected via `ControlExtensions`) |
| W-9 | A peer MUST send complete, unfragmented messages to peers that do not support v1.4 |

### 8.2 SHOULD Requirements

| ID | Requirement |
|----|-------------|
| W-10 | `ControlPreamble.messageSize` SHOULD accurately reflect the total message size in bytes |
| W-11 | `ControlPreamble` SHOULD be sent before any fragments for the same `messageID` |
| W-12 | Implementations SHOULD validate `totalFragments` against `messageSize` and `fragment_size` |
| W-13 | Implementations SHOULD reject fragments where `fragmentIndex >= totalFragments` |

### 8.3 Cross-Implementation Compatibility

For two implementations to interoperate on v1.4:

1. Both MUST use the same message ID computation function
2. Both MUST use compatible `fragment_size` values (or negotiate via
   application-level configuration)
3. Both MUST correctly encode/decode the protobuf messages defined above
4. Both MUST handle the capability advertisement via `ControlExtensions`

---

## 9. Test Vectors

The following test vectors can be used to validate protobuf encoding
implementations.

### 9.1 ControlPreamble Test Vector

**Input:**
```json
{
  "messageID": "0102030405060708091011121314151617181920212223242526272829303132",
  "messageSize": 524288,
  "topicID": "test-topic"
}
```

**Expected encoding (hex):**
```
0A 20 01020304 05060708 09101112 13141516
       17181920 21222324 25262728 29303132
10 8080 20
1A 0A 74657374 2D746F70 6963
```

**Breakdown:**
```
0A       = tag: field 1, wire type 2 (length-delimited)
20       = length: 32 bytes
[32 B]   = messageID bytes

10       = tag: field 2, wire type 0 (varint)
80 80 20 = varint encoding of 524288

1A       = tag: field 3, wire type 2 (length-delimited)
0A       = length: 10 bytes
[10 B]   = "test-topic" in UTF-8
```

### 9.2 ControlImReceiving Test Vector

**Input:**
```json
{
  "messageID": "0102030405060708091011121314151617181920212223242526272829303132"
}
```

**Expected encoding (hex):**
```
0A 20 01020304 05060708 09101112 13141516
       17181920 21222324 25262728 29303132
```

**Total size**: 34 bytes

### 9.3 LargeMessageFragment Test Vector

**Input:**
```json
{
  "messageID": "0102030405060708091011121314151617181920212223242526272829303132",
  "fragmentIndex": 0,
  "totalFragments": 8,
  "fragmentData": "<65536 bytes of 0xFF>",
  "topicID": "test-topic"
}
```

**Expected encoding (prefix, hex):**
```
0A 20 [32 bytes messageID]
10 00
18 08
22 808004 [65536 bytes of FF]
2A 0A 74657374 2D746F70 6963
```

**Breakdown:**
```
0A 20 [32B]  = messageID (34 bytes)
10 00        = fragmentIndex = 0 (2 bytes)
18 08        = totalFragments = 8 (2 bytes)
22 808004    = fragmentData: tag + length varint for 65536 (4 bytes header)
[65536 B]    = fragment payload
2A 0A [10B]  = topicID "test-topic" (12 bytes)
```

**Total size**: 34 + 2 + 2 + 65540 + 12 = **65,590 bytes**

---

## 10. Error Handling

### 10.1 Malformed Message Handling

| Error Condition | Action | Scoring |
|----------------|--------|---------|
| Missing `messageID` in any v1.4 message | Discard message, log warning | No penalty (could be version mismatch) |
| `fragmentIndex >= totalFragments` | Discard fragment | P₇ if repeated |
| Inconsistent `totalFragments` across fragments of same `messageID` | Discard all fragments for this `messageID` | P₄ on reassembly failure |
| `fragmentData` exceeds `fragment_size` | Discard fragment | P₇ if repeated |
| `messageSize` in PREAMBLE doesn't match reassembled size | Log warning | No penalty (advisory field) |
| Unknown fields in v1.4 messages | Ignore (standard protobuf behavior) | No penalty |

### 10.2 Backward Compatibility Handling

When a v1.4 peer communicates with a non-v1.4 peer:

```
if !peer.supports_v14:
    # Non-v1.4 peer will ignore unknown fields (protobuf behavior)
    # But we MUST NOT send fragments — they can't reassemble
    send_complete_message(full_message, peer)

    # We CAN still send PREAMBLE/IMRECEIVING in control messages
    # (they'll be ignored), but SHOULD NOT to avoid confusion
```

---

## 11. References

- Protocol Buffers Encoding: https://protobuf.dev/programming-guides/encoding/
- gossipsub v1.0 Wire Format: [gossipsub-v1.0.md](gossipsub-v1.0.md)
- gossipsub v1.2 IDONTWANT: [gossipsub-v1.2.md](gossipsub-v1.2.md)
- gossipsub v1.3 Extensions: [gossipsub-v1.3.md](gossipsub-v1.3.md)
- extensions.proto: [extensions/extensions.proto](extensions/extensions.proto)
