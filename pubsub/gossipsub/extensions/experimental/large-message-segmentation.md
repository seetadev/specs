# Large Message Segmentation Extension

| Lifecycle Stage | Maturity      | Status | Latest Revision |
| --------------- | ------------- | ------ | --------------- |
| 1A              | Working Draft | Active | r0, 2026-05-06  |

Authors: [@theUtkarshRaj]

Interest Group: [@seetadev], [@johannamoran]

[@theUtkarshRaj]: https://github.com/theUtkarshRaj
[@seetadev]: https://github.com/seetadev
[@johannamoran]: https://github.com/johannamoran

See the [lifecycle document][lifecycle-spec] for context about the maturity level
and spec status.

[lifecycle-spec]: https://github.com/libp2p/specs/blob/master/00-framework-01-spec-lifecycle.md

## Overview

This draft explores transparent segmentation of large payloads at the Gossipsub
layer so implementations can propagate data that may not fit practical message
size expectations in a single unit. This differs from the Partial Messages
extension: partial-messages optimizes for the case where a peer already holds
most of a message, while segmentation handles the case where no peer holds the
full payload yet and it must be chunked, propagated, and reassembled. The two
approaches are complementary, not competing, and future interoperability
testing between py-libp2p and nim-libp2p will help validate the boundary.

## Motivation

One motivation is emerging workloads where single logical payloads are often
large, such as distributed AI model updates, large event logs, and state
snapshots. One approach may be to segment these payloads for transport while
preserving existing pubsub topic behavior.

## Segment Structure

One approach may be to encode each segment with a compact envelope:

The `messageID` identifies which segments belong together across the mesh.
The `segmentIndex` communicates the ordering position for reassembly.
The `totalSegments` tells a receiver when a full set is present.
The `payload` carries the raw bytes for this segment.
The `checksum` enables integrity verification before or after reassembly.

## Reconstruction

Receivers buffer segments by `messageID` until all expected indexes are
available. Once all segments are present, implementations reassemble in index
order and pass the reconstructed message through existing validation flows.
Incomplete segment sets are discarded after a configurable window.

## Interaction with Peer Scoring

This draft explores scoring at the reconstructed message level rather than the
segment level. For the P3 question specifically, a delivery is counted only
when a complete message is successfully reassembled. Segments that arrive but
never form a complete set are not counted as successful deliveries. If the
delivery window expires before reconstruction completes, one approach may be to
treat that outcome as a missed delivery for scoring purposes.

## Open Questions

1. Should `messageID` be application-provided or protocol-generated?
2. What is the recommended maximum segment payload size, and should this be
   fixed in the spec or left to implementations?

## Protobuf

Refer to the protobuf registry at ./extensions/extensions.proto

```protobuf
syntax = "proto2";

message LargeMessageSegmentationExtension {
  optional bytes  messageID     = 1;
  optional uint32 segmentIndex  = 2;
  optional uint32 totalSegments = 3;
  optional bytes  payload       = 4;
  optional bytes  checksum      = 5;
}
```
