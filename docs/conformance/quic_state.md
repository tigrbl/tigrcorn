# QUIC State Evidence

This file is generated from the canonical independent HTTP/3 release matrix and the Phase 4 QUIC state-claim metadata.

| Claim | Title | Scenario | Evidence tier | Notes |
|---|---|---|---|---|
| `TC-STATE-QUIC-RETRY` | QUIC Retry | `http3-server-aioquic-client-post-retry` | `independent_certification` | Retry is preserved through a third-party aioquic HTTP/3 request/response scenario with Retry observed. |
| `TC-STATE-QUIC-RESUMPTION` | QUIC Resumption | `http3-server-aioquic-client-post-resumption` | `independent_certification` | Resumption is preserved through a third-party aioquic HTTP/3 scenario using QUIC-TLS session tickets. |
| `TC-STATE-QUIC-0RTT` | QUIC 0-RTT | `http3-server-aioquic-client-post-zero-rtt` | `independent_certification` | 0-RTT state is preserved through a third-party aioquic HTTP/3 scenario with early data requested and observed. |
| `TC-STATE-QUIC-MIGRATION` | QUIC Migration | `http3-server-aioquic-client-post-migration` | `independent_certification` | Connection migration state is preserved through a third-party aioquic HTTP/3 migration scenario. |
| `TC-STATE-QUIC-GOAWAY` | HTTP/3 GOAWAY | `http3-server-aioquic-client-post-goaway-qpack` | `independent_certification` | GOAWAY semantics are preserved through the third-party aioquic post-goaway scenario. |
| `TC-STATE-QUIC-QPACK` | HTTP/3 QPACK Pressure | `http3-server-aioquic-client-post-goaway-qpack` | `independent_certification` | QPACK encoder/decoder stream pressure is preserved through the third-party aioquic GOAWAY/QPACK scenario. |
