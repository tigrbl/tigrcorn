# QUIC transport / QUIC-TLS state and error matrix

## Connection-state transitions

| State | Trigger | Result |
| --- | --- | --- |
| new | start_handshake | establishing |
| new | receive_version_negotiation | version_negotiated_or_version_negotiation_failed |
| new | close | closing |
| version_negotiated | restart_initial | new_or_establishing |
| establishing | tls_finished | established |
| establishing | close | closing |
| established | peer_close | draining_or_closed |
| established | local_close | closing |
| established | idle_timeout_or_drain_complete | closed |
| closing | drain_complete | closed |
| draining | drain_complete | closed |
| closed | terminal | — |
| version_negotiation_failed | terminal | — |

## Transport error codes

| Error | Code |
| --- | --- |
| NO_ERROR | 0x00 |
| INTERNAL_ERROR | 0x01 |
| TRANSPORT_PARAMETER | 0x08 |
| PROTOCOL_VIOLATION | 0x0a |
| INVALID_TOKEN | 0x0b |
| APPLICATION_ERROR | 0x0c |
