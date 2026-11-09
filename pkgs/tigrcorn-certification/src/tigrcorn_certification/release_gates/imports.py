from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..interop_runner import InteropScenario, load_external_matrix

DEFAULT_BOUNDARY_PATH = Path('docs/review/conformance/certification_boundary.json')
DEFAULT_CORPUS_PATH = Path('docs/review/conformance/corpus.json')
DEFAULT_INDEPENDENT_MATRIX_PATH = Path('docs/review/conformance/external_matrix.release.json')
DEFAULT_SAME_STACK_MATRIX_PATH = Path('docs/review/conformance/external_matrix.same_stack_replay.json')
DEFAULT_STRICT_TARGET_BOUNDARY_PATH = Path('docs/review/conformance/certification_boundary.strict_target.json')
DEFAULT_PROMOTION_TARGET_PATH = Path('docs/review/conformance/promotion_gate.target.json')
DEFAULT_TLS_WRAPPER_PATH = Path('src/tigrcorn/security/tls.py')
DEFAULT_CLAIMS_REGISTRY_PATH = Path('docs/review/conformance/claims_registry.json')
DEFAULT_CONTRACT_REGISTRY_PATH = Path('docs/review/conformance/contract_registry.json')
DEFAULT_LEGACY_UNITTEST_INVENTORY_PATH = Path('LEGACY_UNITTEST_INVENTORY.json')
DEFAULT_SSOT_REGISTRY_PATH = Path('.ssot/registry.json')
DEFAULT_CERTIFICATION_ARTIFACT_ROOT = Path('certification-artifacts')
DEFAULT_SUPPLY_CHAIN_RELEASE_BUNDLE_ROOT = Path('release-evidence/supply-chain')
VALID_EVIDENCE_TIERS = ('local_conformance', 'same_stack_replay', 'independent_certification')
EVIDENCE_TIER_ORDER = {name: index for index, name in enumerate(VALID_EVIDENCE_TIERS, start=1)}

__all__ = [name for name in globals() if not name.startswith('__')]

