# Metrics Schema

This file is generated from the package-owned Phase 6 observability metadata.

## Transport counters

- `connections_opened`: `counter`
- `connections_closed`: `counter`
- `active_connections`: `gauge`
- `bytes_received`: `counter`
- `bytes_sent`: `counter`
- `quic_datagrams_received`: `counter`
- `quic_datagrams_sent`: `counter`
- `quic_sessions_opened`: `counter`
- `quic_sessions_closed`: `counter`
- `active_quic_sessions`: `gauge`

## Security counters

- `tls_handshakes_completed`: `counter`
- `quic_retry_sent`: `counter`
- `quic_early_data_attempted`: `counter`
- `quic_early_data_accepted`: `counter`
- `quic_early_data_rejected`: `counter`

## Loss counters

- `quic_packets_lost`: `counter`
- `quic_pto_expirations`: `counter`
- `quic_path_challenges`: `counter`
- `quic_path_responses`: `counter`
- `quic_path_migrations`: `counter`

## Http3 counters

- `http3_requests_served`: `counter`
- `http3_stream_resets`: `counter`
- `http3_goaway_received`: `counter`
- `http3_qpack_encoder_streams`: `counter`
- `http3_qpack_decoder_streams`: `counter`

## Notes

- `aggregation`: Counters are monotonic totals; gauges report current in-process state.
- `stability`: Metric names are package-owned public operator surface claims and are generated into docs/conformance/metrics_schema.*.
- `http3_scope`: HTTP/3 metrics reflect the package-owned QUIC/HTTP/3 runtime only; they do not claim cross-vendor collector compatibility beyond the declared exporter adapters.
