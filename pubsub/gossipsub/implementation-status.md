# Implementation status of Gossipsub versions and Extensions

This doc provides an overview of the implementation status of Gossipsub
versions and Extensions across all major libp2p implementations.

Legend: ✅ = complete, 🏗 = in progress, 🔄 = spec draft / PR open, ❔ = not started

## Gossipsub Versions

|               | [v1.0] | [v1.1] | [v1.2] | [v1.3-alpha]                                                    |
| ------------- | :----: | :----: | :----: | --------------------------------------------------------------- |
| [Go libp2p]   | ✅     | ✅     | ✅     | [Open PR](https://github.com/libp2p/go-libp2p-pubsub/pull/630)  |
| [Rust libp2p] | ✅     | ✅     | ✅     | [In Progress](https://github.com/libp2p/rust-libp2p/pull/5878)  |
| [JS libp2p]   | ✅     | ✅     | ✅     | ❔                                                              |
| [Nim libp2p]  | ✅     | ✅     | ✅     | ❔                                                              |
| [Java libp2p] | ✅     | ✅     | ✅     | ❔                                                              |
| [py-libp2p]   | ✅     | ✅     | ✅     | ✅                                                              |

> **Note on py-libp2p v1.3:** py-libp2p ships with full v1.3 Extensions Control
> Message support, including both the `ControlExtensions` handshake protocol and
> the Topic Observation extension. See
> [PR libp2p/py-libp2p#1323](https://github.com/libp2p/py-libp2p/pull/1323) for
> the Large Message Segmentation reference implementation.

## Gossipsub Extensions

|               | [Partial Messages]                                        | [Test Extension] | [Large Message Segmentation]                           |
| ------------- | --------------------------------------------------------- | ---------------- | ------------------------------------------------------ |
| [Go libp2p]   | [PR](https://github.com/libp2p/go-libp2p-pubsub/pull/631) | ✅               | ❔                                                     |
| [Rust libp2p] | ❔                                                        | ❔               | ❔                                                     |
| [JS libp2p]   | ❔                                                        | ❔               | ❔                                                     |
| [Nim libp2p]  | ❔                                                        | ❔               | 🔄 [Spec Draft](https://github.com/seetadev/specs/pull/2) |
| [Java libp2p] | ❔                                                        | ❔               | ❔                                                     |
| [py-libp2p]   | ❔                                                        | ❔               | 🔄 [PR libp2p/py-libp2p#1323](https://github.com/libp2p/py-libp2p/pull/1323) |

> Extensions are negotiated at connection time via the GossipSub v1.3
> `ControlExtensions` handshake. See
> [extensions/README.md](extensions/README.md) for a guide to the extensions
> framework.

## Gossipsub Implementation Improvements

|               | [Batch Publishing]                                                       | [IDONTWANT on First Publish]                              | [WFR Gossip]                                              |
| ------------- | ------------------------------------------------------------------------ | --------------------------------------------------------- | --------------------------------------------------------- |
| [Go libp2p]   | [✅](https://pkg.go.dev/github.com/libp2p/go-libp2p-pubsub#MessageBatch) | [✅](https://github.com/libp2p/go-libp2p-pubsub/pull/612) | [PR](https://github.com/libp2p/go-libp2p-pubsub/pull/632) |
| [Rust libp2p] | ❔                                                                       | [✅](https://github.com/libp2p/rust-libp2p/pull/5773)     | ❔                                                         |
| [JS libp2p]   | ❔                                                                       | ❔                                                        | ❔                                                         |
| [Nim libp2p]  | ❔                                                                       | ❔                                                        | ❔                                                         |
| [Java libp2p] | ❔                                                                       | ❔                                                        | ❔                                                         |
| [py-libp2p]   | ❔                                                                       | ✅                                                        | ❔                                                         |

## Reference links

| Key | Implementation | Repository |
| --- | -------------- | ---------- |
| [Go libp2p] | Golang | <https://github.com/libp2p/go-libp2p-pubsub> |
| [Rust libp2p] | Rust | <https://github.com/libp2p/rust-libp2p/tree/master/protocols/gossipsub> |
| [JS libp2p] | JavaScript | <https://github.com/ChainSafe/js-libp2p-gossipsub> |
| [Nim libp2p] | Nim | <https://github.com/vacp2p/nim-libp2p/tree/master/libp2p/protocols/pubsub/gossipsub> |
| [Java libp2p] | Java / Kotlin | <https://github.com/libp2p/jvm-libp2p/tree/develop/libp2p/src/test/kotlin/io/libp2p/pubsub/gossip> |
| [py-libp2p] | Python | <https://github.com/libp2p/py-libp2p/tree/master/libp2p/pubsub> |

| Key | Spec / Proposal |
| --- | --------------- |
| [v1.0] | <https://github.com/libp2p/specs/blob/master/pubsub/gossipsub/gossipsub-v1.0.md> |
| [v1.1] | <https://github.com/libp2p/specs/blob/master/pubsub/gossipsub/gossipsub-v1.1.md> |
| [v1.2] | <https://github.com/libp2p/specs/blob/master/pubsub/gossipsub/gossipsub-v1.2.md> |
| [v1.3-alpha] | <https://github.com/libp2p/specs/issues/687> |
| [Partial Messages] | <https://github.com/libp2p/specs/pull/685> |
| [Test Extension] | <https://github.com/seetadev/specs/blob/master/pubsub/gossipsub/extensions/experimental/test-extension.md> |
| [Large Message Segmentation] | <https://github.com/seetadev/specs/pull/2> |
| [Batch Publishing] | <https://ethresear.ch/t/improving-das-performance-with-gossipsub-batch-publishing/21713> |
| [IDONTWANT on first Publish] | <https://github.com/libp2p/go-libp2p-pubsub/issues/610> |
| [WFR Gossip] | <https://ethresear.ch/t/the-paths-of-least-resistance-introducing-wfr-gossip/22671/3> |
