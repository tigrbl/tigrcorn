from __future__ import annotations

from .imports import *
from .models import *
from .loaders import *

def evaluate_supply_chain_release_gate(
    source_root: str | Path,
    *,
    boundary: Mapping[str, Any] | None = None,
    bundle_root: str | Path | None = None,
    checked_files: list[str] | None = None,
    artifact_status: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    from tigrcorn_certification.supply_chain import validate_release_bundle

    source_root = Path(source_root)
    boundary = dict(boundary or {})
    supply_chain_config = boundary.get('supply_chain', {})
    if not isinstance(supply_chain_config, Mapping):
        supply_chain_config = {}
    root_value = bundle_root or supply_chain_config.get('bundle_root') or DEFAULT_SUPPLY_CHAIN_RELEASE_BUNDLE_ROOT
    artifact_root_value = supply_chain_config.get('certification_artifact_root')
    root = source_root / Path(root_value)
    artifact_root = source_root / Path(artifact_root_value) if artifact_root_value else None
    workspace_packages = tuple(str(item) for item in supply_chain_config.get('workspace_packages', ()))
    result = validate_release_bundle(
        root,
        workspace_packages=workspace_packages,
        certification_artifact_root=artifact_root,
    )
    if checked_files is not None:
        checked_files.extend(str(path) for path in result.get('checked_files', []))
    failures = [f'supply chain: {item}' for item in result.get('failures', [])]
    if artifact_status is not None:
        artifact_status['supply_chain'] = {
            'bundle_root': str(root),
            'failed': bool(failures),
            'package_count': int(result.get('package_count', 0)),
            'release_eligible': bool(result.get('release_eligible', False)),
            'sbom_present': bool(result.get('sbom_present', False)),
            'slsa_present': bool(result.get('slsa_present', False)),
        }
    return failures

__all__ = [name for name in globals() if not name.startswith('__')]

