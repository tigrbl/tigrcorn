from __future__ import annotations

from tigrcorn.observability.metrics import OTEL_EXPORT_SCHEMA_VERSION, STATSD_EXPORT_MODES, STATSD_EXPORT_SCHEMA_VERSION

QLOG_EXPERIMENTAL_SCHEMA_VERSION = 'tigrcorn.qlog.experimental.v1'

METRICS_SCHEMA = {
    'families': {
        'transport': [
            'connections_opened',
            'connections_closed',
            'active_connections',
            'bytes_received',
            'bytes_sent',
            'quic_datagrams_received',
            'quic_datagrams_sent',
            'quic_sessions_opened',
            'quic_sessions_closed',
            'active_quic_sessions',
        ],
        'security': [
            'tls_handshakes_completed',
            'quic_retry_sent',
            'quic_early_data_attempted',
            'quic_early_data_accepted',
            'quic_early_data_rejected',
        ],
        'loss': [
            'quic_packets_lost',
            'quic_pto_expirations',
            'quic_path_challenges',
            'quic_path_responses',
            'quic_path_migrations',
        ],
        'http3': [
            'http3_requests_served',
            'http3_stream_resets',
            'http3_goaway_received',
            'http3_qpack_encoder_streams',
            'http3_qpack_decoder_streams',
        ],
    },
    'gauge_metrics': [
        'uptime_seconds',
        'active_connections',
        'active_websocket_connections',
        'active_quic_sessions',
    ],
    'notes': {
        'aggregation': 'Counters are monotonic totals; gauges report current in-process state.',
        'stability': 'Metric names are package-owned public operator surface claims and are generated into docs/conformance/metrics_schema.*.',
        'http3_scope': 'HTTP/3 metrics reflect the package-owned QUIC/HTTP/3 runtime only; they do not claim cross-vendor collector compatibility beyond the declared exporter adapters.',
    },
}

EXPORT_ADAPTERS = [
    {
        'id': 'statsd',
        'config_path': 'metrics.statsd_host',
        'flag': '--statsd-host',
        'schema_version': STATSD_EXPORT_SCHEMA_VERSION,
        'protocols': list(STATSD_EXPORT_MODES),
        'wire_format': 'StatsD line protocol over UDP; DogStatsD compatibility is the same line format without tags.',
        'accepted_values': ['host:port', 'statsd://host:port', 'dogstatsd://host:port'],
        'startup_behavior': 'Exporter starts after server startup and performs an immediate best-effort flush.',
        'failure_behavior': 'Send failures are bounded, counted, and do not abort server startup or shutdown.',
    },
    {
        'id': 'otlp_http_json',
        'config_path': 'metrics.otel_endpoint',
        'flag': '--otel-endpoint',
        'schema_version': OTEL_EXPORT_SCHEMA_VERSION,
        'protocols': ['http', 'https'],
        'wire_format': 'Package-owned OTLP-style JSON envelope over HTTP POST.',
        'accepted_values': ['http://collector/v1/telemetry', 'https://collector/v1/telemetry'],
        'startup_behavior': 'Exporter starts after server startup and emits metrics/spans in periodic batches.',
        'failure_behavior': 'POST failures are bounded, counted, and preserve buffered spans for retry on the next cycle.',
    },
]

QLOG_EXPERIMENTAL_SURFACE = {
    'schema_version': QLOG_EXPERIMENTAL_SCHEMA_VERSION,
    'stability': 'experimental',
    'compatibility': 'best_effort_internal_artifact_only',
    'producer': 'tigrcorn.compat.interop_runner.generate_observer_qlog',
    'redaction_rules': {
        'network_endpoints': 'remote endpoint addresses are redacted from qlog output',
        'connection_ids': 'dcid/scid values are redacted in emitted packet summaries',
        'payload_bytes': 'raw packet payload bytes are not copied into qlog output',
    },
    'versioning': {
        'qlog_version': '0.3',
        'package_schema': QLOG_EXPERIMENTAL_SCHEMA_VERSION,
        'upgrade_rule': 'schema_version changes when redaction fields, event envelopes, or emitted packet summary fields change incompatibly',
    },
    'markers': {
        'experimental_marker': 'trace.common_fields.tigrcorn_qlog.experimental',
        'redaction_marker': 'trace.common_fields.tigrcorn_qlog.redaction',
    },
}


def observability_surface() -> dict[str, object]:
    return {
        'contract_version': 1,
        'metrics_schema': METRICS_SCHEMA,
        'export_adapters': EXPORT_ADAPTERS,
        'qlog': QLOG_EXPERIMENTAL_SURFACE,
    }


__all__ = [
    'EXPORT_ADAPTERS',
    'METRICS_SCHEMA',
    'QLOG_EXPERIMENTAL_SCHEMA_VERSION',
    'QLOG_EXPERIMENTAL_SURFACE',
    'observability_surface',
]
