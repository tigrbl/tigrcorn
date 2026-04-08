from __future__ import annotations

FAIL_STATE_REGISTRY = [
    {
        'surface': 'proxy',
        'risk': 'untrusted forwarded header spoofing',
        'default_action': 'strip_and_continue',
        'runtime_contract': 'Untrusted Forwarded and X-Forwarded-* data is ignored and the connection continues using the transport-observed peer and scheme.',
        'observable_outcomes': ['proxy view stays on transport peer', 'request proceeds without forwarded override'],
    },
    {
        'surface': 'early_data',
        'risk': 'replayed resumed request without admitted 0-RTT',
        'default_action': 'reject_response',
        'runtime_contract': 'When early-data policy is require and resumption succeeds without admitted early data, the package sends 425 Too Early before ASGI dispatch.',
        'observable_outcomes': ['425 Too Early', 'no ASGI app dispatch'],
    },
    {
        'surface': 'quic',
        'risk': 'invalid token, prohibited migration, or transport-integrity failure',
        'default_action': 'close_connection',
        'runtime_contract': 'QUIC transport failures produce Retry, CONNECTION_CLOSE, or transport-level close events instead of partially admitted application state.',
        'observable_outcomes': ['retry event', 'close event', 'pending close datagram'],
    },
    {
        'surface': 'origin',
        'risk': 'path traversal or invalid ASGI pathsend',
        'default_action': 'reject_or_abort',
        'runtime_contract': 'Traversal attempts return 404 from the package-owned origin surface, while invalid http.response.pathsend inputs raise ASGIProtocolError.',
        'observable_outcomes': ['404 Not Found', 'ASGIProtocolError'],
    },
    {
        'surface': 'connect_relay',
        'risk': 'open relay or disallowed CONNECT target',
        'default_action': 'reject_response',
        'runtime_contract': 'Denied or allowlist-mismatched CONNECT requests terminate with 403 connect denied and do not dispatch to the ASGI app.',
        'observable_outcomes': ['403 connect denied', 'stream end / response completion'],
    },
    {
        'surface': 'tls_x509',
        'risk': 'revoked, stale, or unreachable revocation state under strict validation',
        'default_action': 'abort_validation',
        'runtime_contract': 'Strict X.509 revocation failures abort validation with ProtocolError rather than soft-admitting the peer.',
        'observable_outcomes': ['ProtocolError', 'preserved OCSP validation artifacts'],
    },
    {
        'surface': 'mixed_topology',
        'risk': 'evidence-tier drift or blocked scenario metadata in mixed and same-stack matrices',
        'default_action': 'gate_reject',
        'runtime_contract': 'Promotion and release-gate evaluators fail closed when matrix metadata is blocked, pending, or outside the declared evidence tier.',
        'observable_outcomes': ['release gate failure', 'promotion target failure'],
    },
]


NEGATIVE_CORPORA = {
    'proxy': [
        {
            'id': 'untrusted-forwarded-headers-ignored',
            'expected_action': 'strip_and_continue',
            'expected_outcome': 'proxy view remains transport-derived',
            'tests': ['tests/test_phase3_policy_surface.py::Phase3PolicySurfaceTests::test_untrusted_proxy_headers_are_ignored'],
            'preserved_artifacts': [],
        }
    ],
    'early_data': [
        {
            'id': 'required-early-data-downgrade',
            'expected_action': 'reject_response',
            'expected_outcome': '425 Too Early before ASGI dispatch',
            'tests': ['tests/test_phase4_quic_surface.py::Phase4QuicSurfaceTests::test_http3_handler_require_policy_triggers_too_early_on_resumed_downgrade'],
            'preserved_artifacts': [],
        }
    ],
    'quic': [
        {
            'id': 'retry-required-before-admission',
            'expected_action': 'close_or_retry_transport_owned',
            'expected_outcome': 'server emits Retry before initial admission when require_retry is enabled',
            'tests': ['tests/test_quic_transport_runtime_completion.py::QuicTransportRuntimeCompletionTests::test_retry_roundtrip_and_new_token_runtime_validation'],
            'preserved_artifacts': ['docs/review/conformance/external_matrix.release.json'],
        },
        {
            'id': 'disable-active-migration-rejects-rebinding',
            'expected_action': 'close_connection',
            'expected_outcome': 'transport closes when peer changes address despite disable_active_migration',
            'tests': ['tests/test_quic_transport_runtime_completion.py::QuicTransportRuntimeCompletionTests::test_disable_active_migration_rejects_rebinding_and_preferred_address_is_reported'],
            'preserved_artifacts': ['docs/review/conformance/external_matrix.release.json'],
        },
    ],
    'origin': [
        {
            'id': 'encoded-parent-segment',
            'expected_action': 'reject_response',
            'expected_outcome': '404 Not Found',
            'tests': ['tests/test_phase5_origin_contract.py::Phase5OriginContractTests::test_parent_segments_and_backslash_segments_are_denied'],
            'preserved_artifacts': ['docs/conformance/origin_negatives.json'],
        },
        {
            'id': 'pathsend-relative-path',
            'expected_action': 'abort_asgi_protocol',
            'expected_outcome': 'ASGIProtocolError',
            'tests': ['tests/test_phase5_origin_contract.py::Phase5OriginContractTests::test_pathsend_rejects_relative_and_missing_paths'],
            'preserved_artifacts': ['docs/conformance/origin_negatives.json'],
        },
    ],
    'connect_relay': [
        {
            'id': 'http2-connect-policy-deny',
            'expected_action': 'reject_response',
            'expected_outcome': '403 connect denied and end stream',
            'tests': ['tests/test_phase9d1_connect_relay_local_negatives.py::ConnectRelayPhase9D1LocalNegativeTests::test_http2_connect_policy_deny_and_allowlist_rejection_end_stream'],
            'preserved_artifacts': ['docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-connect-relay-local-negative-artifacts'],
        },
        {
            'id': 'http3-connect-allowlist-rejection',
            'expected_action': 'reject_response',
            'expected_outcome': '403 connect denied and end stream',
            'tests': ['tests/test_phase9d1_connect_relay_local_negatives.py::ConnectRelayPhase9D1LocalNegativeTests::test_http3_connect_policy_deny_and_allowlist_rejection_end_stream'],
            'preserved_artifacts': ['docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-connect-relay-local-negative-artifacts'],
        },
    ],
    'tls_x509': [
        {
            'id': 'revoked-leaf-rejected',
            'expected_action': 'abort_validation',
            'expected_outcome': 'ProtocolError for revoked leaf when CRL is present',
            'tests': ['tests/test_x509_webpki_validation.py::test_rejects_revoked_leaf_when_crl_is_present'],
            'preserved_artifacts': ['docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-ocsp-local-validation-artifacts'],
        },
        {
            'id': 'stale-ocsp-require-fails',
            'expected_action': 'abort_validation',
            'expected_outcome': 'ProtocolError for stale OCSP response in require mode',
            'tests': ['tests/test_x509_webpki_validation.py::test_require_mode_rejects_stale_ocsp_response'],
            'preserved_artifacts': ['docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-ocsp-local-validation-artifacts'],
        },
    ],
    'mixed_topology': [
        {
            'id': 'blocked-matrix-metadata-fails-closed',
            'expected_action': 'gate_reject',
            'expected_outcome': 'release gates fail when same-stack or independent matrix metadata is blocked or pending',
            'tests': ['tests/test_release_gates.py::ReleaseGateEvaluationTests::test_release_gates_fail_closed_when_matrix_metadata_is_blocked'],
            'preserved_artifacts': ['docs/review/conformance/release_gate_status.current.json'],
        },
        {
            'id': 'same-stack-tier-drift-fails-closed',
            'expected_action': 'gate_reject',
            'expected_outcome': 'release gates fail when same-stack matrix contains a scenario outside same_stack_replay',
            'tests': ['tests/test_release_gates.py::ReleaseGateEvaluationTests::test_release_gates_reject_same_stack_matrix_with_wrong_tier'],
            'preserved_artifacts': ['docs/review/conformance/release_gate_status.current.json'],
        },
    ],
}


NEGATIVE_BUNDLE_METADATA = {
    'bundle_kind': 'expected_negative_outcomes',
    'preservation_rule': 'Generated bundles are package-owned current-tree expected outcomes; release-root preserved bundles remain authoritative historical evidence where referenced.',
    'surfaces': list(NEGATIVE_CORPORA),
}


__all__ = ['FAIL_STATE_REGISTRY', 'NEGATIVE_BUNDLE_METADATA', 'NEGATIVE_CORPORA']
