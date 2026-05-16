# Metadata Encodings for Partial Messages

| Lifecycle Stage | Maturity      | Status | Latest Revision |
| --------------- | ------------- | ------ | --------------- |
| 1A              | Working Draft | Active | r0, 2026-05-16  |

See the [lifecycle document][lifecycle-spec] for context about the maturity level
and spec status.

[lifecycle-spec]: https://github.com/libp2p/specs/blob/master/00-framework-01-spec-lifecycle.md

## Overview

Per the [Partial Messages specification](./partial-messages.md), the `partsMetadata` field is used to communicate a node's state regarding available message parts. While the core protocol defines this field as application-defined opaque bytes, this document provides a set of recommended standard encodings. 

The goal of these recommendations is to encourage interoperability across different Gossipsub implementations (such as `py-libp2p`, `nim-libp2p`, `go-libp2p`, and `rust-libp2p`). While implementations are free to define their own custom encodings, they SHOULD prefer one of the standard approaches described here to ensure cross-implementation compatibility.

## Bitmask Encoding

Bitmask (or Bitmap) encoding represents the presence of message parts as a fixed-length sequence of bits. Each bit's position in the sequence maps directly to a part index.

### Technical Description
If a full message is divided into $N$ parts, the bitmask is $N$ bits long. A bit set to `1` at index $i$ indicates that the peer holds part $i$, while a `0` indicates the part is missing.

**Example (8 parts):**
Suppose a message has 8 parts (indexed 0-7). A peer holds parts 0, 1, 4, and 5.
- Binary representation: `11001100` (where index 0 is the most significant bit)
- Hexadecimal representation: `0xCC`

### Wire Format
The bitmask is encoded as a byte array (`bytes`). The length of the array is $\lceil N/8 \rceil$ bytes. Bits are packed into bytes in big-endian order (index 0 is the most significant bit of the first byte).

### Tradeoffs
- **Size:** Fixed at $N/8$ bytes. Very efficient for small to medium part counts.
- **Complexity:** Extremely low; uses standard bitwise operations.
- **Accuracy:** Perfect (no false positives or negatives).
- **Best Use Case:** Applications with a fixed, relatively small number of parts, such as Ethereum DAS columns (typically 32-64 parts).

## Range-based Encoding

Range-based encoding describes the parts held by a peer as a series of contiguous intervals of part indices.

### Technical Description
Instead of representing every individual part, the peer communicates the "start" and "end" (or "length") of blocks of parts it possesses.

**Example (100 parts):**
A peer has parts 0 through 45 and 80 through 95.
- Representation: `[[0, 45], [80, 95]]`

### Wire Format
The ranges are encoded as a sequence of pairs. Each pair consists of a `start_index` and a `length`. Both values MUST be encoded as [unsigned varints](https://github.com/multiformats/unsigned-varint) to minimize space.
- Format: `varint(start_1), varint(length_1), varint(start_2), varint(length_2), ...`

### Tradeoffs
- **Size:** Variable. Highly efficient for contiguous data; inefficient if the distribution of parts is highly fragmented (the "Swiss cheese" problem).
- **Complexity:** Low; requires simple comparison and iteration.
- **Accuracy:** Perfect.
- **Best Use Case:** Streaming applications or protocols where data is typically received in large, ordered chunks.

## Bloom Filter Encoding

A Bloom Filter is a space-efficient probabilistic data structure used to test whether a part index is a member of the set of parts a peer holds.

### Technical Description
A Bloom Filter uses a bit array of $m$ bits and $k$ different hash functions. To add a part index to the filter, the index is hashed $k$ times, and the bits at the resulting positions are set to `1`.

**Example:**
- Array size $m=8$ bits, hash functions $k=2$.
- Peer has parts "P1" and "P3".
- `hash1("P1") = 1`, `hash2("P1") = 4` -> Bits 1 and 4 set.
- `hash1("P3") = 4`, `hash2("P3") = 7` -> Bits 4 and 7 set.
- Encoded Filter: `01001001` (binary) or `0x49`.

### Tradeoffs
- **Size:** Constant and configurable regardless of the number of parts.
- **Complexity:** Medium; requires multiple hash function evaluations.
- **False Positives:** Possible. A receiver might incorrectly conclude a peer has a part it doesn't actually possess. False negatives are impossible.
- **Best Use Case:** Very large, sparse sets of parts where bitmasks or range lists would be prohibitively large.

## Encoding Selection Guide

| Message Parts Count | Part Distribution | Accuracy Requirement | Recommended Encoding |
| :--- | :--- | :--- | :--- |
| Small ( < 256 ) | Any | Strict | **Bitmask** |
| Large ( > 256 ) | Contiguous / Blocks | Strict | **Range-based** |
| Very Large / Infinite | Sparse / Random | Probabilistic | **Bloom Filter** |

## Interoperability Considerations

Gossipsub implementations MUST treat the `partsMetadata` field as opaque bytes and forward them directly to the application layer. The Gossipsub router itself does not need to understand the encoding.

When two implementations intend to interoperate using the Partial Messages extension, they MUST agree on the encoding scheme:
1. **Out-of-band Agreement:** Peer operators agree on the encoding before connection.
2. **Topic-level Convention:** The specification for a specific Gossipsub topic (e.g., a "Beacon Block" topic) SHOULD explicitly document the chosen encoding for `partsMetadata`.

Implementations SHOULD gracefully handle unexpected `partsMetadata` lengths or malformed data by ignoring the update or logging a warning, rather than crashing or terminating the connection.
