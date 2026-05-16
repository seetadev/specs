# Security Considerations: Partial Messages Extension

| Lifecycle Stage | Maturity      | Status | Latest Revision |
| --------------- | ------------- | ------ | --------------- |
| 1A              | Working Draft | Active | r0, 2025-06-23  |

## Overview

The Partial Messages extension allows Gossipsub nodes to transmit and request fragments of a message rather than the full payload. While this significantly optimizes bandwidth—particularly in Data Availability (DA) contexts like Ethereum's Fusaka fork—it introduces new attack surfaces and state management challenges beyond standard Gossipsub.

This document identifies those threats and provides specific mitigation strategies. These strategies build upon and assume the presence of the robust security mechanisms defined in [gossipsub-v1.1.md](./gossipsub-v1.1.md) and [red.md](./red.md). Peer Scoring, Random Early Drop (RED), and control message caps remain the primary defense layers for the protocol.

## Existing Security Foundations

Implementations supporting the Partial Messages extension MUST maintain and integrate with existing Gossipsub security mechanisms:

- **Peer Scoring:** Continuous tracking of peer behavior, specifically leveraging `P4` (Invalid Messages) and `P7` (Behavioural Penalty).
- **Random Early Drop (RED):** Probabilistic dropping of messages before they reach the validation queue to prevent DoS via unvalidated spam.
- **Control Message Caps:** Maintaining existing limits on `IHAVE` advertisements and `IWANT` retransmission frequencies.
- **IDONTWANT Limits:** Adhering to [gossipsub-v1.2.md](./gossipsub-v1.2.md) limits to prevent control-plane flooding.
- **PRUNE Backoff:** Ensuring nodes cannot rapidly cycle mesh connections to bypass penalties.

## Threat Model

### 3.1 GroupID State Exhaustion

An attacker can flood a node with a high volume of unique `groupID`s, each associated with its own `partsMetadata`. If a node attempts to track the "missing parts" state for every unique `groupID` announced, it risks memory exhaustion.

**Mitigation:**
- Implement a strict limit on the number of active `groupID` states tracked per peer.
- Use a Least Recently Used (LRU) cache or a similar eviction strategy to manage `groupID` state memory.
- Defer state persistence to the application layer where possible.

### 3.2 Bandwidth Amplification

The asymmetric nature of `partsMetadata` (a small request) and `partialMessage` (a potentially large data response) can be exploited for bandwidth amplification. In Data Availability Sampling (DAS) contexts, this amplification factor can reach ~32x.

**Mitigation:**
- Implement a response budget for partial responses.
- Limit the total number of parts or total bytes sent in response to a single `partsMetadata` RPC.
- Enforce a rate limit on partial data sent per peer per heartbeat.
- Refer to prior art like QUIC's 3x amplification limit for unverified addresses.

### 3.3 Incomplete Group Buffering

An attacker may send a large majority of parts for a group but intentionally withhold the final parts required for reassembly. This "incomplete group" attack aims to tie up memory in the victim's reassembly buffers.

**Mitigation:**
- Implement application-level timeouts for group reassembly.
- The Gossipsub library SHOULD provide a mechanism for the application to signal when a group buffer should be purged.
- Forward partial state to the application to allow for application-specific cleanup logic.

### 3.4 Malicious Metadata Flooding

Peers may send frequent `partsMetadata` updates that do not reflect their actual state or are sent at an excessive frequency, wasting CPU cycles on diffing and bandwidth on redundant signaling.

**Mitigation:**
- Rate limit the acceptance and processing of `partsMetadata` updates from any single peer.
- Follow the "signaling bandwidth tradeoff" recommendations in the main spec: nodes SHOULD only send updates when state changes significantly or according to a throttled heartbeat.

### 3.5 Cache Probing

An attacker can send `partsMetadata` for a `groupID` they have not yet seen in the network to probe whether a victim node already has the data cached. This reveals private information about a node's cache state before data is globally announced.

**Mitigation:**
- Implement a "seen check": a node SHOULD only respond to a `partsMetadata` request if the associated `groupID` or message ID is already present in its `seen` cache or `mcache`.

### 3.6 Reassembly CPU Attack

Malformed or overlapping partial message parts may require expensive cryptographic verification (e.g., KZG proofs in DAS). An attacker can flood a node with complex, invalid parts to cause a CPU DoS.

**Mitigation:**
- Leverage the Random Early Drop (RED) circuit breaker to protect the validation queue.
- Prioritize validation of parts received from high-scoring peers.
- Strictly apply the `P7` (Behavioural Penalty) to peers that transmit parts that fail application-level validation.

## Application-Library Interface Security Requirements

Because the content of `partsMetadata` and `partialMessage` is application-defined, the Gossipsub library cannot natively validate their integrity or correctness.

**Security Requirements:**
- **P7 Signaling:** The interface MUST allow the application to signal a `Behavioural Penalty` back to the Gossipsub library. If the application determines a peer is sending useless or invalid partial data, the library MUST decrement the peer's score.
- **Integrity Verification:** Applications SHOULD use commitments or hashes (similar to BitTorrent piece hashes) to verify the integrity of parts before reassembly.
- **Validation Feedback:** The library MUST wait for application-level validation before forwarding partial messages or marking parts as "available" to other peers.

## Implementation Checklist

- [ ] **State Limits:** Is there an upper bound on `groupID` state entries?
- [ ] **Amplification Protection:** Is there a byte/part limit on responses to `partsMetadata`?
- [ ] **Seen Verification:** Does the node ignore `partsMetadata` for unknown `groupID`s?
- [ ] **Scoring Integration:** Does the application have a clear path to trigger `P7` penalties?
- [ ] **RED Integration:** Is the partial message validation path protected by the RED circuit breaker?
- [ ] **Rate Limiting:** Are `partsMetadata` updates throttled per peer?
- [ ] **Reassembly Timeouts:** Are there clear timeouts for discarding incomplete message groups?
