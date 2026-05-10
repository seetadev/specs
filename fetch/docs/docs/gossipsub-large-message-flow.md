# Gossipsub 1.4 Large Message Propagation

## Overview

This document describes the proposed large-message
propagation mechanism for Gossipsub 1.4.

Large payloads are segmented into smaller chunks
before propagation through the gossip mesh.

---

# Segmentation Flow

```text
Publisher
   │
Large Message
   │
Segmentation Layer
   │
┌───────────────┐
│ Segment 1     │
│ Segment 2     │
│ Segment 3     │
└───────────────┘
   │
Gossipsub Mesh
   │
Receiving Peers
   │
Reassembly Layer
   │
Reconstructed Message
```

---

# Segment Metadata

Each segment contains:

| Field | Description |
|---|---|
| message_id | Unique identifier for original message |
| segment_index | Current segment number |
| total_segments | Total number of segments |
| checksum | Integrity verification |
| payload | Segment data |

---

# Reconstruction

Receiving peers reconstruct the message after all
segments are received.

Reconstruction includes:

- ordered reassembly
- integrity verification
- duplicate filtering
- missing segment recovery

---

# Security Considerations

Potential concerns include:

- malicious segment flooding
- incomplete message spam
- memory exhaustion attacks
- invalid checksum propagation

Integrity verification should occur before reassembly.
