# gossipsub v1.4: Large Payload Optimizations

| Lifecycle Stage | Maturity      | Status | Latest Revision |
|-----------------|---------------|--------|-----------------|
| 1A              | Working Draft | Active | r0, 2026-05-16  |

Interest Group: [@marcopolo], [@vyzo], [@Nashatyrev], [@Menduist], [@jxs], [@cskiraly]

[@marcopolo]: https://github.com/marcopolo
[@vyzo]: https://github.com/vyzo
[@Nashatyrev]: https://github.com/Nashatyrev
[@Menduist]: https://github.com/Menduist
[@jxs]: https://github.com/jxs
[@cskiraly]: https://github.com/cskiraly

See the [lifecycle document][lifecycle-spec] for context about maturity level and spec status.

[lifecycle-spec]: https://github.com/libp2p/specs/blob/master/00-framework-01-spec-lifecycle.md

---

## Overview

Gossipsub v1.4 consolidates the experimental features introduced under the [v1.3 Extensions](./gossipsub-v1.3.md) mechanism into a stable, versioned protocol. The protocol ID for this version is `/meshsub/1.4.0`.

While v1.3 allowed for the dynamic negotiation of features, v1.4 defines a baseline set of optimizations specifically targeted at high-throughput and large-payload decentralized systems. This includes Ethereum's Data Availability Sampling (DAS) in the upcoming Fusaka fork, as well as distributed AI and high-volume event logging.

v1.4 nodes MUST still support the v1.3 Extensions control message to ensure backwards compatibility with v1.3-only peers during the network transition.

## Motivation

The baseline Gossipsub protocol was primarily optimized for small messages (e.g., blockchain transactions, consensus votes). Emerging decentralized systems require the reliable and efficient dissemination of large payloads, such as:
- Ethereum Data Availability Sampling (DAS) columns.
- Distributed AI model updates.
- Large-scale event logs and state sync snapshots.

The bundled features in v1.4—Partial Messages, Batch Publishing, IDONTWANT on First Publish, and Wait-For-Receipt (WFR) Gossip—address the limitations of the original mesh-based propagation for these use cases. They focus on reducing redundancy, minimizing time-to-last-part delivery, and optimizing path selection based on actual network latency.

References:
- [Batch Publishing ethresear.ch post](https://ethresear.ch/t/improving-das-performance-with-gossipsub-batch-publishing/21713)
- [WFR Gossip ethresear.ch post](https://ethresear.ch/t/the-paths-of-least-resistance-introducing-wfr-gossip/22671/3)

## Protocol ID

The protocol ID for this version is `/meshsub/1.4.0`.

Nodes advertising `/meshsub/1.4.0` MUST support the core functionality defined in v1.0 through v1.2, as well as the Extensions mechanism defined in v1.3. For backwards compatibility, v1.4 nodes MUST support responding to `/meshsub/1.3.0` streams.

## Bundled Features

### 4.1 Partial Messages

The Partial Messages extension allows nodes to transmit only the required parts of a message rather than the full message. This is critical for systems like PeerDAS where nodes only custody or require a subset of a larger data block.

- **SubOpts Changes**:
    - `requestsPartial`: When set to `true`, it signals to the receiver that the sender prefers partial messages and will provide `partsMetadata`.
    - `supportsSendingPartial`: Signals that the node is capable of responding to partial message requests.
- **PartialMessagesExtension Message**:
    - `topicID`: The identifier for the topic.
    - `groupID`: An identifier for a group of parts (e.g., a block ID).
    - `partialMessage`: The application-defined encoded message parts.
    - `partsMetadata`: An application-defined representation (e.g., a bitmap) of the parts a peer has or wants.
- **Normative Requirements**:
    - A node MUST NOT send `partialMessage` data to a peer unless that peer has signaled `requestsPartial: true` for the topic.
    - Upon receiving `partsMetadata` from a peer, a node SHOULD respond with only the parts that the metadata indicates the peer is missing.
    - Partial Messages SHOULD replace the standard `IHAVE`/`IWANT` flow for large message topics. Instead of requesting a full message after an `IHAVE`, the node SHOULD exchange `partsMetadata` to retrieve only missing segments.
- Full technical details are specified in [partial-messages.md](./partial-messages.md).

### 4.2 Batch Publishing

Batch Publishing optimizes the dissemination of $N$ related messages (e.g., $N$ columns of a DA matrix) to $D$ mesh peers.

- **The Problem**: Sequential publishing ($N$ times $D$) leads to a "head-of-line blocking" effect where the first message consumes the node's uplink redundancy while the $N$-th message waits, delaying its initial entry into the network.
- **Interleaved Scheduling**: Instead of sending all copies of Message 1, then all copies of Message 2, the publisher sends the 1st copy of all $N$ messages to their respective target peers before sending the 2nd copy of any message.
- **Normative Requirements**:
    - Nodes implementing batch publishing MUST prioritize the initial injection of every unique message in the batch.
    - The scheduler SHOULD interleave deliveries to different mesh peers to ensure the "diffusion front" of the entire batch starts as simultaneously as possible.
- Reference: [Batch Publishing ethresear.ch post](https://ethresear.ch/t/improving-das-performance-with-gossipsub-batch-publishing/21713)

### 4.3 IDONTWANT on First Publish

This optimization addresses the "boomerang effect" where a publisher receives the same message back from its mesh peers immediately after its own initial publish.

- **Mechanism**: A node MUST send an `IDONTWANT` message for a given `messageID` to all its mesh peers immediately before it performs its own initial publish of that message.
- **Rationale**: This prevents mesh peers—who might have received the message from another path at nearly the same time—from wasting bandwidth by sending a duplicate back to the publisher.
- **Normative**: This pre-emptive use of `IDONTWANT` is required for v1.4 nodes on high-throughput topics to minimize redundant traffic. It extends the `IDONTWANT` behavior introduced in [v1.2](./gossipsub-v1.2.md).

### 4.4 Wait-For-Receipt (WFR) Gossip

Wait-For-Receipt (WFR) is a path-aware propagation suppression mechanism.

- **Mechanism**: Nodes track the arrival latency ($L_{in}$) of a message from a peer and compare it to the expected link latency ($L_{out}$) to their other mesh peers.
- **Suppression Logic**: If $L_{in} > L_{out} + \text{threshold}$, the node MAY suppress the eager push to that specific peer. This assumes the peer will receive the message via a faster, more direct path.
- **Normative Requirements**:
    - Nodes SHOULD maintain a moving average of peer latencies ($L_{out}$) to inform WFR decisions.
    - The suppression threshold MUST be configurable to avoid accidental network fragmentation.
- Reference: [WFR Gossip ethresear.ch post](https://ethresear.ch/t/the-paths-of-least-resistance-introducing-wfr-gossip/22671/3)

## Interaction with Existing Mechanisms

- **Peer Scoring (v1.1)**: The $P_4$ (Invalid Messages) and $P_7$ (Behavioral Penalty) counters are extended to include Partial Messages. Advertising parts that are not held (via `partsMetadata`) or sending invalid part data MUST result in scoring penalties.
- **RED (red.md)**: The [Random Early Drop](./red.md) circuit breaker remains active to protect the validation queue. Implementations should account for the fact that partial messages may require individual part validation.
- **IDONTWANT Limits (v1.2)**: The `max_idontwant_messages` limit MUST be respected to prevent `IDONTWANT` floods from becoming a DoS vector.
- **Extensions Control Message (v1.3)**: v1.4 nodes MUST continue to use the [v1.3 Extensions mechanism](./gossipsub-v1.3.md) to advertise support for Partial Messages and other features to ensure compatibility with v1.3 nodes that have not yet upgraded to the v1.4 protocol ID.

## Parameters

| Parameter | Description | Suggested Default |
|-----------|-------------|-------------------|
| `max_partial_group_ids` | Maximum number of group IDs tracked per peer for partial messages | 1024 |
| `max_partial_response_bytes` | Maximum total bytes allowed for partial message parts in a single RPC | 2 MiB |
| `wfr_latency_threshold` | The latency threshold for WFR suppression | 50ms |
| `batch_publish_fanout` | The maximum degree for initial batch injection (overrides D for batches) | 8 |

## Protobuf

The v1.4 Gossipsub RPC protobuf consolidates fields introduced in v1.2, v1.3, and the new v1.4 features.

```protobuf
syntax = "proto2";

message RPC {
  message SubOpts {
    optional bool subscribe = 1; // subscribe or unsubscribe
    optional string topicid = 2;

    // v1.4: Used with Partial Messages extension.
    optional bool requestsPartial = 3;
    optional bool supportsSendingPartial = 4;
  }

  repeated SubOpts subscriptions = 1;
  repeated Message publish = 2;
  optional ControlMessage control = 3;

  // v1.4: Canonical Extension for Partial Messages
  optional PartialMessagesExtension partial = 10;
}

message ControlMessage {
  repeated ControlIHave ihave = 1;
  repeated ControlIWant iwant = 2;
  repeated ControlGraft graft = 3;
  repeated ControlPrune prune = 4;
  
  // v1.2 addition
  repeated ControlIDontWant idontwant = 5;
  
  // v1.3 addition
  optional ControlExtensions extensions = 6;
}

message ControlExtensions {
  // v1.4: Support for Partial Messages
  optional bool partialMessages = 10;
}

message ControlIDontWant {
  repeated bytes messageIDs = 1;
}

message PartialMessagesExtension {
  optional bytes topicID = 1;
  optional bytes groupID = 2;

  // v1.4: Application-defined encoding of parts
  optional bytes partialMessage = 3;
  optional bytes partsMetadata = 4;
}
```

## References

- [gossipsub-v1.1.md](./gossipsub-v1.1.md)
- [gossipsub-v1.2.md](./gossipsub-v1.2.md)
- [gossipsub-v1.3.md](./gossipsub-v1.3.md)
- [partial-messages.md](./partial-messages.md)
- [red.md](./red.md)
- [Batch Publishing ethresear.ch post](https://ethresear.ch/t/improving-das-performance-with-gossipsub-batch-publishing/21713)
- [WFR Gossip ethresear.ch post](https://ethresear.ch/t/the-paths-of-least-resistance-introducing-wfr-gossip/22671/3)
- [Ethereum consensus-specs PR 4558](https://github.com/ethereum/consensus-specs/pull/4558)
- [implementation-status.md](./implementation-status.md)
