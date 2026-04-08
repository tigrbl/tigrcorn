# Negative Corpora

This file is generated from the package-owned Phase 7 negative-certification metadata.

## proxy

| Case | Expected action | Expected outcome | Tests | Preserved artifacts |
|---|---|---|---|---|
| `untrusted-forwarded-headers-ignored` | `strip_and_continue` | proxy view remains transport-derived | `tests/test_phase3_policy_surface.py::Phase3PolicySurfaceTests::test_untrusted_proxy_headers_are_ignored` |  |

## early_data

| Case | Expected action | Expected outcome | Tests | Preserved artifacts |
|---|---|---|---|---|
| `required-early-data-downgrade` | `reject_response` | 425 Too Early before ASGI dispatch | `tests/test_phase4_quic_surface.py::Phase4QuicSurfaceTests::test_http3_handler_require_policy_triggers_too_early_on_resumed_downgrade` |  |

## quic

| Case | Expected action | Expected outcome | Tests | Preserved artifacts |
|---|---|---|---|---|
| `retry-required-before-admission` | `close_or_retry_transport_owned` | server emits Retry before initial admission when require_retry is enabled | `tests/test_quic_transport_runtime_completion.py::QuicTransportRuntimeCompletionTests::test_retry_roundtrip_and_new_token_runtime_validation` | `docs/review/conformance/external_matrix.release.json` |
| `disable-active-migration-rejects-rebinding` | `close_connection` | transport closes when peer changes address despite disable_active_migration | `tests/test_quic_transport_runtime_completion.py::QuicTransportRuntimeCompletionTests::test_disable_active_migration_rejects_rebinding_and_preferred_address_is_reported` | `docs/review/conformance/external_matrix.release.json` |

## origin

| Case | Expected action | Expected outcome | Tests | Preserved artifacts |
|---|---|---|---|---|
| `encoded-parent-segment` | `reject_response` | 404 Not Found | `tests/test_phase5_origin_contract.py::Phase5OriginContractTests::test_parent_segments_and_backslash_segments_are_denied` | `docs/conformance/origin_negatives.json` |
| `pathsend-relative-path` | `abort_asgi_protocol` | ASGIProtocolError | `tests/test_phase5_origin_contract.py::Phase5OriginContractTests::test_pathsend_rejects_relative_and_missing_paths` | `docs/conformance/origin_negatives.json` |

## connect_relay

| Case | Expected action | Expected outcome | Tests | Preserved artifacts |
|---|---|---|---|---|
| `http2-connect-policy-deny` | `reject_response` | 403 connect denied and end stream | `tests/test_phase9d1_connect_relay_local_negatives.py::ConnectRelayPhase9D1LocalNegativeTests::test_http2_connect_policy_deny_and_allowlist_rejection_end_stream` | `docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-connect-relay-local-negative-artifacts` |
| `http3-connect-allowlist-rejection` | `reject_response` | 403 connect denied and end stream | `tests/test_phase9d1_connect_relay_local_negatives.py::ConnectRelayPhase9D1LocalNegativeTests::test_http3_connect_policy_deny_and_allowlist_rejection_end_stream` | `docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-connect-relay-local-negative-artifacts` |

## tls_x509

| Case | Expected action | Expected outcome | Tests | Preserved artifacts |
|---|---|---|---|---|
| `revoked-leaf-rejected` | `abort_validation` | ProtocolError for revoked leaf when CRL is present | `tests/test_x509_webpki_validation.py::test_rejects_revoked_leaf_when_crl_is_present` | `docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-ocsp-local-validation-artifacts` |
| `stale-ocsp-require-fails` | `abort_validation` | ProtocolError for stale OCSP response in require mode | `tests/test_x509_webpki_validation.py::test_require_mode_rejects_stale_ocsp_response` | `docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-ocsp-local-validation-artifacts` |

## mixed_topology

| Case | Expected action | Expected outcome | Tests | Preserved artifacts |
|---|---|---|---|---|
| `blocked-matrix-metadata-fails-closed` | `gate_reject` | release gates fail when same-stack or independent matrix metadata is blocked or pending | `tests/test_release_gates.py::ReleaseGateEvaluationTests::test_release_gates_fail_closed_when_matrix_metadata_is_blocked` | `docs/review/conformance/release_gate_status.current.json` |
| `same-stack-tier-drift-fails-closed` | `gate_reject` | release gates fail when same-stack matrix contains a scenario outside same_stack_replay | `tests/test_release_gates.py::ReleaseGateEvaluationTests::test_release_gates_reject_same_stack_matrix_with_wrong_tier` | `docs/review/conformance/release_gate_status.current.json` |

