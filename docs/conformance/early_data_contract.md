# Early-Data Contract

This file is generated from the runtime Phase 4 QUIC metadata and the canonical independent HTTP/3 release matrix.

## Public surface

- Flag: `--quic-early-data-policy`
- Config path: `quic.early_data_policy`
- Default policy: `deny`
- Value space: `allow, deny, require`

## Admission policy

- `deny`: Do not advertise early-data-capable session tickets and do not accept 0-RTT application data.
- `allow`: Advertise early-data-capable session tickets and accept 0-RTT only when QUIC/TLS ticket compatibility and the package replay gate permit it.
- `require`: Advertise early-data-capable session tickets and reject resumed requests with 425 Too Early when resumption succeeds but early data is not accepted.

## Replay and 425 behavior

- `gate`: The package replay gate claims each early-data ticket identity once and rejects replayed 0-RTT reuse.
- `allow_downgrade`: When early data is not accepted, resumed requests continue after handshake under the ordinary HTTP/3 path.
- `deny_downgrade`: 0-RTT is not advertised; resumed requests are processed only after handshake.
- `require_downgrade`: Resumed requests that downgrade out of 0-RTT receive 425 Too Early before the ASGI app is invoked.

## Multi-instance and load-balancer policy

- `single_instance`: Single-process replay gating is package-owned and local to the running server instance.
- `multi_instance`: Multi-instance deployments need shared anti-replay coordination to make allow/require honest across nodes.
- `load_balancer`: Without shared anti-replay coordination, the honest edge posture remains deny, which is the default and the strict-h3-edge requirement.

## Retry and app/runtime visibility

- `retry_scope`: Retry remains transport-owned token validation and is resolved before HTTP/3 request dispatch.
- `application_visibility`: ASGI applications do not receive direct Retry or 0-RTT transport-state fields; they observe only admitted requests or a package-generated 425 response.

## Preserved third-party evidence

| Scenario | Feature | Artifact dir |
|---|---|---|
| `http3-server-aioquic-client-post-retry` | `post-echo-retry` | `docs\review\conformance\releases\0.3.9\release-0.3.9\tigrcorn-independent-certification-release-matrix\http3-server-aioquic-client-post-retry` |
| `http3-server-aioquic-client-post-resumption` | `post-echo-resumption` | `docs\review\conformance\releases\0.3.9\release-0.3.9\tigrcorn-independent-certification-release-matrix\http3-server-aioquic-client-post-resumption` |
| `http3-server-aioquic-client-post-zero-rtt` | `post-echo-zero-rtt` | `docs\review\conformance\releases\0.3.9\release-0.3.9\tigrcorn-independent-certification-release-matrix\http3-server-aioquic-client-post-zero-rtt` |
| `http3-server-aioquic-client-post-migration` | `post-echo-migration` | `docs\review\conformance\releases\0.3.9\release-0.3.9\tigrcorn-independent-certification-release-matrix\http3-server-aioquic-client-post-migration` |
| `http3-server-aioquic-client-post-goaway-qpack` | `post-echo-goaway-qpack` | `docs\review\conformance\releases\0.3.9\release-0.3.9\tigrcorn-independent-certification-release-matrix\http3-server-aioquic-client-post-goaway-qpack` |
| `http3-server-aioquic-client-post-goaway-qpack` | `post-echo-goaway-qpack` | `docs\review\conformance\releases\0.3.9\release-0.3.9\tigrcorn-independent-certification-release-matrix\http3-server-aioquic-client-post-goaway-qpack` |
