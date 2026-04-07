from __future__ import annotations

from typing import Any


EARLY_DATA_CONTRACT: dict[str, Any] = {
    'flag': '--quic-early-data-policy',
    'config_path': 'quic.early_data_policy',
    'default_policy': 'deny',
    'value_space': ['allow', 'deny', 'require'],
    'admission': {
        'deny': 'Do not advertise early-data-capable session tickets and do not accept 0-RTT application data.',
        'allow': 'Advertise early-data-capable session tickets and accept 0-RTT only when QUIC/TLS ticket compatibility and the package replay gate permit it.',
        'require': 'Advertise early-data-capable session tickets and reject resumed requests with 425 Too Early when resumption succeeds but early data is not accepted.',
    },
    'replay_policy': {
        'gate': 'The package replay gate claims each early-data ticket identity once and rejects replayed 0-RTT reuse.',
        'allow_downgrade': 'When early data is not accepted, resumed requests continue after handshake under the ordinary HTTP/3 path.',
        'deny_downgrade': '0-RTT is not advertised; resumed requests are processed only after handshake.',
        'require_downgrade': 'Resumed requests that downgrade out of 0-RTT receive 425 Too Early before the ASGI app is invoked.',
    },
    'topology': {
        'single_instance': 'Single-process replay gating is package-owned and local to the running server instance.',
        'multi_instance': 'Multi-instance deployments need shared anti-replay coordination to make allow/require honest across nodes.',
        'load_balancer': 'Without shared anti-replay coordination, the honest edge posture remains deny, which is the default and the strict-h3-edge requirement.',
    },
    'retry_zero_rtt_interaction': {
        'retry_scope': 'Retry remains transport-owned token validation and is resolved before HTTP/3 request dispatch.',
        'application_visibility': 'ASGI applications do not receive direct Retry or 0-RTT transport-state fields; they observe only admitted requests or a package-generated 425 response.',
    },
}


QUIC_STATE_CLAIMS: tuple[dict[str, Any], ...] = (
    {
        'claim_id': 'TC-STATE-QUIC-RETRY',
        'title': 'QUIC Retry',
        'feature': 'retry',
        'scenarios': ['http3-server-aioquic-client-post-retry'],
        'third_party_required': True,
        'protocols': ['QUIC', 'HTTP/3'],
        'notes': 'Retry is preserved through a third-party aioquic HTTP/3 request/response scenario with Retry observed.',
    },
    {
        'claim_id': 'TC-STATE-QUIC-RESUMPTION',
        'title': 'QUIC Resumption',
        'feature': 'resumption',
        'scenarios': ['http3-server-aioquic-client-post-resumption'],
        'third_party_required': True,
        'protocols': ['QUIC', 'HTTP/3'],
        'notes': 'Resumption is preserved through a third-party aioquic HTTP/3 scenario using QUIC-TLS session tickets.',
    },
    {
        'claim_id': 'TC-STATE-QUIC-0RTT',
        'title': 'QUIC 0-RTT',
        'feature': 'zero_rtt',
        'scenarios': ['http3-server-aioquic-client-post-zero-rtt'],
        'third_party_required': True,
        'protocols': ['QUIC', 'HTTP/3'],
        'notes': '0-RTT state is preserved through a third-party aioquic HTTP/3 scenario with early data requested and observed.',
    },
    {
        'claim_id': 'TC-STATE-QUIC-MIGRATION',
        'title': 'QUIC Migration',
        'feature': 'migration',
        'scenarios': ['http3-server-aioquic-client-post-migration'],
        'third_party_required': True,
        'protocols': ['QUIC', 'HTTP/3'],
        'notes': 'Connection migration state is preserved through a third-party aioquic HTTP/3 migration scenario.',
    },
    {
        'claim_id': 'TC-STATE-QUIC-GOAWAY',
        'title': 'HTTP/3 GOAWAY',
        'feature': 'goaway',
        'scenarios': ['http3-server-aioquic-client-post-goaway-qpack'],
        'third_party_required': True,
        'protocols': ['HTTP/3'],
        'notes': 'GOAWAY semantics are preserved through the third-party aioquic post-goaway scenario.',
    },
    {
        'claim_id': 'TC-STATE-QUIC-QPACK',
        'title': 'HTTP/3 QPACK Pressure',
        'feature': 'qpack_blocking',
        'scenarios': ['http3-server-aioquic-client-post-goaway-qpack'],
        'third_party_required': True,
        'protocols': ['HTTP/3', 'QPACK'],
        'notes': 'QPACK encoder/decoder stream pressure is preserved through the third-party aioquic GOAWAY/QPACK scenario.',
    },
)


QUIC_FLAG_HELP: dict[str, str] = {
    '--quic-require-retry': 'Require a QUIC Retry before completing the initial handshake on UDP listeners',
    '--quic-max-datagram-size': 'Maximum QUIC UDP payload size advertised and accepted by package-owned QUIC listeners',
    '--quic-idle-timeout': 'QUIC idle timeout in seconds for package-owned UDP listeners',
    '--quic-early-data-policy': 'QUIC early-data policy: deny, allow, or require with 425 downgrade handling',
}


def quic_flag_help(flag: str, fallback: str | None = None) -> str | None:
    return QUIC_FLAG_HELP.get(flag, fallback)

