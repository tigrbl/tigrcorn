from __future__ import annotations

from .imports import *
from .helpers import *

def generate_observer_qlog(
    *,
    packet_trace_path: str | Path,
    qlog_path: str | Path,
    title: str,
    protocol: str,
    ip_family: str,
    negotiation: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    trace_path = Path(packet_trace_path)
    records: list[dict[str, Any]] = []
    if trace_path.exists():
        for line in trace_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    if not records:
        _write_json(
            Path(qlog_path),
            {
                'qlog_version': QLOG_VERSION,
                'schema_version': QLOG_EXPERIMENTAL_SCHEMA_VERSION,
                'traces': [],
            },
        )
        return
    base_time = float(records[0]['timestamp'])
    events: list[list[Any]] = [
        [
            0.0,
            'connectivity',
            'connection_started',
            {
                'ip_version': 'ipv6' if ip_family == 'ipv6' else 'ipv4',
                'protocol': protocol,
                'server': {'host': 'redacted', 'port': 'redacted'},
            },
        ]
    ]
    if negotiation:
        events.append([0.0, 'transport', 'parameters_set', dict(negotiation)])
    for record in records:
        payload = bytes.fromhex(record['payload_hex'])
        packets = [_describe_quic_packet(chunk) for chunk in _split_observed_packets(payload)]
        packets = [item for item in packets if item is not None]
        if not packets:
            packets = [{'packet_type': 'unknown', 'length': len(payload)}]
        else:
            packets = [_redact_qlog_packet(item) for item in packets]
        events.append([
            round((float(record['timestamp']) - base_time) * 1000.0, 3),
            'transport',
            'packet_received' if record['direction'] == 'client_to_server' else 'packet_sent',
            {
                'direction': record['direction'],
                'length': record['length'],
                'packets': packets,
            },
        ])
    if error:
        events.append([round((float(records[-1]['timestamp']) - base_time) * 1000.0, 3), 'transport', 'connection_closed', {'error': error}])
    _write_json(
        Path(qlog_path),
        {
            'qlog_version': QLOG_VERSION,
            'schema_version': QLOG_EXPERIMENTAL_SCHEMA_VERSION,
            'traces': [
                {
                    'vantage_point': {'type': 'network', 'name': 'tigrcorn-interop-runner'},
                    'title': title,
                    'common_fields': {
                        'protocol_type': 'QUIC',
                        'tigrcorn_qlog': {
                            'experimental': True,
                            'schema_version': QLOG_EXPERIMENTAL_SCHEMA_VERSION,
                            'redaction': {
                                'network_endpoints': 'redacted',
                                'connection_ids': 'redacted',
                                'payload_bytes': 'omitted',
                            },
                        },
                    },
                    'events': events,
                }
            ],
        },
    )
def _split_observed_packets(payload: bytes) -> list[bytes]:
    try:
        return split_coalesced_packets(payload, destination_connection_id_length=8)
    except Exception:
        return [payload]



def _describe_quic_packet(payload: bytes) -> dict[str, Any] | None:
    try:
        packet = decode_packet(payload, destination_connection_id_length=8)
    except Exception:
        return None
    description: dict[str, Any] = {'length': len(payload)}
    if isinstance(packet, QuicLongHeaderPacket):
        description['packet_type'] = packet.packet_type.name.lower()
        description['version'] = packet.version
        description['dcid'] = packet.destination_connection_id.hex()
        description['scid'] = packet.source_connection_id.hex()
        description['packet_number'] = int.from_bytes(packet.packet_number, 'big')
    elif isinstance(packet, QuicRetryPacket):
        description['packet_type'] = 'retry'
        description['version'] = packet.version
        description['dcid'] = packet.destination_connection_id.hex()
        description['scid'] = packet.source_connection_id.hex()
    elif isinstance(packet, QuicVersionNegotiationPacket):
        description['packet_type'] = 'version_negotiation'
        description['versions'] = list(packet.supported_versions)
        description['dcid'] = packet.destination_connection_id.hex()
        description['scid'] = packet.source_connection_id.hex()
    elif isinstance(packet, QuicShortHeaderPacket):
        description['packet_type'] = '1rtt'
        description['dcid'] = packet.destination_connection_id.hex()
        description['packet_number'] = int.from_bytes(packet.packet_number, 'big')
        description['key_phase'] = packet.key_phase
    else:
        return None
    return description


def _redact_qlog_packet(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(payload)
    for key in ('dcid', 'scid'):
        if key in redacted:
            redacted[key] = 'redacted'
    return redacted

__all__ = [name for name in globals() if not name.startswith('__')]
