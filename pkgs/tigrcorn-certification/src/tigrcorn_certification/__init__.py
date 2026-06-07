from __future__ import annotations

PACKAGE_BOUNDARY = "certification"

__all__ = [
    "PACKAGE_BOUNDARY",
    "evaluate_release_gates",
    "assert_release_ready",
    "ReleaseGateError",
    "ReleaseGateReport",
    "certification_explicit_surface_catalog",
    "certification_explicit_surface_ids",
    "validate_explicit_surface_manifest",
    "evaluate_contract_registry_release_gate",
    "evaluate_certification_artifact_release_gate",
    "evaluate_supply_chain_release_gate",
    "CertificationArtifact",
    "CertificationArtifactError",
    "CertificationBundle",
    "build_artifact",
    "build_bundle",
    "build_manifest",
    "canonical_json",
    "output_directory_contract",
    "reject_nondeterministic_fields",
    "replay_diff",
    "sign_manifest",
    "verify_release_evidence",
    "verify_output_tree",
    "write_bundle",
    "write_certification_artifacts",
    "PackageRecord",
    "SupplyChainEvidenceError",
    "dependency_drift_report",
    "generated_certification_artifact_links",
    "has_slsa_provenance",
    "has_spdx_or_cyclonedx",
    "package_list",
    "package_record",
    "release_train_evidence",
    "supply_chain_manifest",
    "validate_release_bundle",
    "validate_certification_artifact_linkage",
    "validate_package_manifest_integrity",
    "validate_release_evidence",
    "write_supply_chain_release_bundle",
]


def __getattr__(name: str):
    if name in {
        "evaluate_release_gates",
        "assert_release_ready",
        "ReleaseGateError",
        "ReleaseGateReport",
        "evaluate_contract_registry_release_gate",
        "evaluate_certification_artifact_release_gate",
        "evaluate_supply_chain_release_gate",
    }:
        from .release_gates import (
            ReleaseGateError,
            ReleaseGateReport,
            assert_release_ready,
            evaluate_certification_artifact_release_gate,
            evaluate_contract_registry_release_gate,
            evaluate_release_gates,
            evaluate_supply_chain_release_gate,
        )

        mapping = {
            "evaluate_release_gates": evaluate_release_gates,
            "evaluate_certification_artifact_release_gate": evaluate_certification_artifact_release_gate,
            "evaluate_contract_registry_release_gate": evaluate_contract_registry_release_gate,
            "evaluate_supply_chain_release_gate": evaluate_supply_chain_release_gate,
            "assert_release_ready": assert_release_ready,
            "ReleaseGateError": ReleaseGateError,
            "ReleaseGateReport": ReleaseGateReport,
        }
        return mapping[name]
    if name in {
        "certification_explicit_surface_catalog",
        "certification_explicit_surface_ids",
        "validate_explicit_surface_manifest",
    }:
        from .explicit_surfaces import (
            certification_explicit_surface_catalog,
            certification_explicit_surface_ids,
            validate_explicit_surface_manifest,
        )

        mapping = {
            "certification_explicit_surface_catalog": certification_explicit_surface_catalog,
            "certification_explicit_surface_ids": certification_explicit_surface_ids,
            "validate_explicit_surface_manifest": validate_explicit_surface_manifest,
        }
        return mapping[name]
    if name in {
        "CertificationArtifact",
        "CertificationArtifactError",
        "CertificationBundle",
        "build_artifact",
        "build_bundle",
        "build_manifest",
        "canonical_json",
        "output_directory_contract",
        "reject_nondeterministic_fields",
        "replay_diff",
        "sign_manifest",
        "verify_release_evidence",
        "verify_output_tree",
        "write_bundle",
        "write_certification_artifacts",
    }:
        from .artifacts import (
            CertificationArtifact,
            CertificationArtifactError,
            CertificationBundle,
            build_artifact,
            build_bundle,
            build_manifest,
            canonical_json,
            output_directory_contract,
            reject_nondeterministic_fields,
            replay_diff,
            sign_manifest,
            verify_release_evidence,
            verify_output_tree,
            write_bundle,
            write_certification_artifacts,
        )

        mapping = {
            "CertificationArtifact": CertificationArtifact,
            "CertificationArtifactError": CertificationArtifactError,
            "CertificationBundle": CertificationBundle,
            "build_artifact": build_artifact,
            "build_bundle": build_bundle,
            "build_manifest": build_manifest,
            "canonical_json": canonical_json,
            "output_directory_contract": output_directory_contract,
            "reject_nondeterministic_fields": reject_nondeterministic_fields,
            "replay_diff": replay_diff,
            "sign_manifest": sign_manifest,
            "verify_release_evidence": verify_release_evidence,
            "verify_output_tree": verify_output_tree,
            "write_bundle": write_bundle,
            "write_certification_artifacts": write_certification_artifacts,
        }
        return mapping[name]
    if name in {
        "PackageRecord",
        "SupplyChainEvidenceError",
        "dependency_drift_report",
        "generated_certification_artifact_links",
        "has_slsa_provenance",
        "has_spdx_or_cyclonedx",
        "package_list",
        "package_record",
        "release_train_evidence",
        "supply_chain_manifest",
        "validate_certification_artifact_linkage",
        "validate_package_manifest_integrity",
        "validate_release_bundle",
        "validate_release_evidence",
        "write_supply_chain_release_bundle",
    }:
        from .supply_chain import (
            PackageRecord,
            SupplyChainEvidenceError,
            dependency_drift_report,
            generated_certification_artifact_links,
            has_slsa_provenance,
            has_spdx_or_cyclonedx,
            package_list,
            package_record,
            release_train_evidence,
            supply_chain_manifest,
            validate_certification_artifact_linkage,
            validate_package_manifest_integrity,
            validate_release_bundle,
            validate_release_evidence,
            write_supply_chain_release_bundle,
        )

        mapping = {
            "PackageRecord": PackageRecord,
            "SupplyChainEvidenceError": SupplyChainEvidenceError,
            "dependency_drift_report": dependency_drift_report,
            "generated_certification_artifact_links": generated_certification_artifact_links,
            "has_slsa_provenance": has_slsa_provenance,
            "has_spdx_or_cyclonedx": has_spdx_or_cyclonedx,
            "package_list": package_list,
            "package_record": package_record,
            "release_train_evidence": release_train_evidence,
            "supply_chain_manifest": supply_chain_manifest,
            "validate_certification_artifact_linkage": validate_certification_artifact_linkage,
            "validate_package_manifest_integrity": validate_package_manifest_integrity,
            "validate_release_bundle": validate_release_bundle,
            "validate_release_evidence": validate_release_evidence,
            "write_supply_chain_release_bundle": write_supply_chain_release_bundle,
        }
        return mapping[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
