from __future__ import annotations

from copy import deepcopy
from typing import Any


HARDENING_SUITE_CATALOG: dict[str, dict[str, Any]] = {
    "http1": {
        "owner_package": "tigrcorn-protocols",
        "package_tests": ["tests/test_http1_hardening_pass.py"],
        "cross_cutting_tests": ["tests/test_adversarial_protocol_hardening_suites.py"],
        "feature_ids": ["feat:adversarial-protocol-hardening-suites"],
        "spec_ids": ["spc:2080"],
        "cases": ["slowloris", "malformed_chunking", "request_smuggling", "oversized_headers", "premature_eof"],
    },
    "http2": {
        "owner_package": "tigrcorn-protocols",
        "package_tests": ["tests/test_http2_state_machine_completion.py"],
        "cross_cutting_tests": ["tests/test_adversarial_protocol_hardening_suites.py"],
        "feature_ids": ["feat:adversarial-protocol-hardening-suites"],
        "spec_ids": ["spc:2080"],
        "cases": ["rapid_reset", "continuation_flood", "stream_exhaustion", "settings_churn", "flow_control_deadlock"],
    },
    "http3_quic": {
        "owner_package": "tigrcorn-transports",
        "package_tests": ["tests/test_quic_operational_security_certification.py", "tests/test_quic_impairment_policy.py"],
        "cross_cutting_tests": ["tests/test_quic_operational_security_integration.py", "tests/test_quic_recovery_live_runtime_integration.py"],
        "feature_ids": ["feat:quic-operational-security-certification", "feat:adversarial-protocol-hardening-suites"],
        "spec_ids": ["spc:2060", "spc:2080"],
        "cases": ["packet_loss", "packet_reordering", "packet_duplication", "controlled_delay", "reliable_stream_recovery", "datagram_abandonment", "amplification_limit", "connection_migration", "cid_rotation"],
    },
    "websocket": {
        "owner_package": "tigrcorn-protocols",
        "package_tests": ["tests/test_server_websocket.py"],
        "cross_cutting_tests": ["tests/test_adversarial_protocol_hardening_suites.py"],
        "feature_ids": ["feat:adversarial-protocol-hardening-suites"],
        "spec_ids": ["spc:2080"],
        "cases": ["fragmented_control_frames", "masking_rules", "close_races", "compression_bombs"],
    },
    "webtransport": {
        "owner_package": "tigrcorn-protocols",
        "package_tests": ["tests/test_webtransport_resource_governance.py"],
        "cross_cutting_tests": ["tests/test_webtransport_resource_governance_integration.py"],
        "feature_ids": ["feat:webtransport-resource-governance", "feat:adversarial-protocol-hardening-suites"],
        "spec_ids": ["spc:2061", "spc:2080"],
        "cases": ["session_budget", "stream_budget", "datagram_budget", "drain", "reset_stop_sending"],
    },
    "static": {
        "owner_package": "tigrcorn-static",
        "package_tests": ["tests/test_static_delivery_security_certification.py"],
        "cross_cutting_tests": ["tests/test_certification_command_namespace.py"],
        "feature_ids": ["feat:static-delivery-security-certification", "feat:adversarial-protocol-hardening-suites"],
        "spec_ids": ["spc:2062", "spc:2080"],
        "cases": ["traversal", "sidecar_mismatch", "range_amplification", "content_type_ambiguity"],
    },
    "observability": {
        "owner_package": "tigrcorn-observability",
        "package_tests": ["tests/test_protocol_aware_observability.py"],
        "cross_cutting_tests": ["tests/test_protocol_aware_observability_integration.py"],
        "feature_ids": ["feat:protocol-aware-observability"],
        "spec_ids": ["spc:2064"],
        "cases": ["metric_names", "event_names", "cardinality_limits"],
    },
    "certification": {
        "owner_package": "tigrcorn-certification",
        "package_tests": ["tests/test_certification_command_namespace.py"],
        "cross_cutting_tests": ["tests/test_adversarial_protocol_hardening_suites.py"],
        "feature_ids": ["feat:certification-command-namespace"],
        "spec_ids": ["spc:2079"],
        "cases": ["command_dispatch", "artifact_shape", "leaf_import_boundary", "fail_closed"],
    },
}


def export_hardening_suite_catalog() -> dict[str, Any]:
    return {
        "catalog": deepcopy(HARDENING_SUITE_CATALOG),
        "schema_version": 1,
    }


def validate_hardening_suite_catalog(catalog: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    selected = catalog or HARDENING_SUITE_CATALOG
    failures: list[str] = []
    for suite_id, suite in sorted(selected.items()):
        owner = suite.get("owner_package")
        if not isinstance(owner, str) or not owner.startswith("tigrcorn-"):
            failures.append(f"{suite_id}: owner_package must be a tigrcorn distribution")
        for field in ("package_tests", "cross_cutting_tests", "feature_ids", "spec_ids", "cases"):
            values = suite.get(field)
            if not isinstance(values, list) or not values:
                failures.append(f"{suite_id}: {field} must be a non-empty list")
        for test_path in suite.get("package_tests", []) + suite.get("cross_cutting_tests", []):
            if not isinstance(test_path, str) or not test_path.startswith("tests/"):
                failures.append(f"{suite_id}: test path must be under tests/: {test_path!r}")
    return {"failures": failures, "passed": not failures, "suite_count": len(selected)}


__all__ = [
    "HARDENING_SUITE_CATALOG",
    "export_hardening_suite_catalog",
    "validate_hardening_suite_catalog",
]
