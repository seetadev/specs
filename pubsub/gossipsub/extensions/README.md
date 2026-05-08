# GossipSub Extensions Framework

GossipSub v1.3 introduced a generic **Extensions Control Message** mechanism
that allows implementations to negotiate and enable optional protocol features
at connection time without breaking compatibility with peers that don't support
them.

This document explains how the extensions framework works and serves as a
registry of both canonical and experimental extensions.

## How Extensions Work

### 1. Capability Advertisement

When two peers establish a GossipSub stream, the **first RPC message** sent in
each direction MUST include a `ControlExtensions` message inside the existing
`ControlMessage` container if the sending peer supports any extensions:

```protobuf
message ControlExtensions {
    // Canonical extensions (field numbers < 0x200000)
    optional bool topicObservation = 1;

    // Experimental extensions (field numbers > 0x200000)
    optional bool testExtension = 6492434;
    optional bool largeMessageSegmentation = 6492435;
}
```

This handshake follows the GossipSub v1.3 spec rules:

1. Extensions MUST be sent in the **first control message** on a fresh stream.
2. Extensions MUST NOT be sent **more than once** per peer.
3. Duplicate extensions messages are a protocol violation and SHOULD be reported
   as misbehaviour.

### 2. Protocol Activation

Once both peers have exchanged extensions, an extension is considered **active**
if and only if **both** peers set its capability flag to `true`. Extension-
specific behaviour (e.g., sending segmented messages, sending observation
requests) MUST NOT begin before mutual activation.

### 3. Field Number Allocation

Field numbers in `ControlExtensions` and on the `RPC` message are split into
two ranges:

| Range | Purpose | Example |
|-------|---------|---------|
| 1 – 2,097,151 | Canonical extensions — small wire overhead (1-2 bytes) | `topicObservation = 1` |
| > 2,097,152 (0x200000) | Experimental extensions — 4+ byte encoding | `testExtension = 6492434` |

Experimental field numbers are allocated on a first-come, first-served basis.
There is no central registry — implementers choose an unused number in the
experimental range. To avoid collisions, check existing PRs and extensions
before picking a number.

## Registered Extensions

### Canonical

| # | Extension | Field | Status | Spec |
|---|-----------|-------|--------|------|
| 10 | Partial Messages | `RPC.partial = 10` | Draft | [PR #685](https://github.com/libp2p/specs/pull/685) |

### Experimental

| # | Field Number | Extension | Field Name | Status | Spec |
|---|--------------|-----------|------------|--------|------|
| 1 | 6492434 | Test Extension | `RPC.testExtension` | Draft | [test-extension.md](experimental/test-extension.md) |
| 2 | 6492435 | Large Message Segmentation | `RPC.largeMessageSegmentation` | Draft | [PR #2](https://github.com/seetadev/specs/pull/2) |

### How to Register a New Experimental Extension

1. Pick an unused field number > `0x200000` (2,097,152).
2. Add a `bool` field to `ControlExtensions` and a message field to `RPC` in
   `extensions.proto`.
3. Write an extension specification document in
   `extensions/experimental/<name>.md` following the
   [test-extension.md](experimental/test-extension.md) template.
4. Open a PR to this repository.

## Extension Lifecycle

Experimental extensions follow the libp2p spec lifecycle:

```
Experimental (1A) → Working Draft (1B) → Candidate Recommendation (2A) → Recommendation (2B)
```

An extension may progress from Experimental to Working Draft once at least two
independent implementations exist and basic interoperability has been
demonstrated.

## Relationship to GossipSub Versions

| Version | Key Feature | Relationship to Extensions |
|---------|-------------|---------------------------|
| v1.0 | Baseline mesh + gossip | No extension mechanism |
| v1.1 | Peer scoring, PX | No extension mechanism |
| v1.2 | IDONTWANT, adaptive gossip | No extension mechanism |
| v1.3 | **Extensions Control Message** | Framework foundation |
| v1.4 | Large message handling (proposed) | Built as an extension on v1.3 |

Extensions are designed to be independent of the wire protocol version. A v1.3
peer can negotiate any extension with another v1.3 peer without requiring a new
protocol ID.
