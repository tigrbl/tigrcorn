# QUIC congestion-control extension test plan

This artifact records planned, not-yet-passing tests for the versioned QUIC
congestion-controller extension surface. The SSOT test rows are intentionally
`planned`; this document is design evidence, not implementation or conformance
evidence.

## Contract and discovery

- Validate API-v1 event, decision, limit, snapshot, and failure shapes.
- Reject incompatible API versions, duplicate provider identities, invalid
  options, and invalid provider output.
- Prove lazy provider import and fresh-wheel entry-point discovery.

## Transport integration

- Keep RFC 9002 loss recovery transport-owned.
- Isolate controller state per path and govern migration, reload, and teardown.
- Compose controller limits with pacing, FIFO admission, flow control,
  anti-amplification, and confirmed socket emission.

## Default-provider compatibility

- Replay golden Reno traces, randomized differential traces, and persistent
  congestion cases against the current behavior.
- Enforce the package dependency DAG and independent distribution boundary.

## Operations and certification

- Validate capability, describe, redaction, and bounded metric-cardinality
  contracts.
- Run loss/jitter, bandwidth/RTT, application-limited, fairness, control-latency,
  multi-client WebTransport soak, and third-party HTTP/3 interoperability
  matrices for every supported provider.

The tests must be changed from `planned` only when their executable assertions
and corresponding result artifacts exist. Passing scaffolds do not constitute
provider certification.
