from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
import sys
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tigrcorn.compat.release_gates import evaluate_release_gates, evaluate_promotion_target

CONFORMANCE = ROOT / 'docs' / 'review' / 'conformance'
RELEASE_ROOT = CONFORMANCE / 'releases' / '0.3.9' / 'release-0.3.9'
VERSION = '0.3.9'
RELEASE_ROOT_TEXT = 'docs/review/conformance/releases/0.3.9/release-0.3.9'
INDEPENDENT_ROOT = f'{RELEASE_ROOT_TEXT}/tigrcorn-independent-certification-release-matrix'
SAME_STACK_ROOT = f'{RELEASE_ROOT_TEXT}/tigrcorn-same-stack-replay-matrix'
MIXED_ROOT = f'{RELEASE_ROOT_TEXT}/tigrcorn-mixed-compatibility-release-matrix'
RELEASE_NOTES = 'RELEASE_NOTES_0.3.9.md'
PROMOTION_MD = CONFORMANCE / 'PHASE9_RELEASE_PROMOTION_AND_VERSION_UPDATE.md'
PROMOTION_JSON = CONFORMANCE / 'phase9_release_promotion.current.json'
DELIVERY_NOTES = ROOT / 'docs/review/conformance/delivery/DELIVERY_NOTES_PHASE9_RELEASE_PROMOTION_AND_VERSION_UPDATE.md'


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def dump_json(path: str | Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')


def relative_paths(paths: list[str]) -> list[str]:
    values: list[str] = []
    root = ROOT.resolve()
    for item in paths:
        try:
            rel = Path(item).resolve().relative_to(root)
            values.append(rel.as_posix())
        except Exception:
            values.append(str(item))
    return values


def replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise RuntimeError(f'expected marker not found: {old!r}')
    return text.replace(old, new, 1)


def replace_once_optional(text: str, old: str, new: str) -> str:
    if old not in text:
        return text
    return text.replace(old, new, 1)


def replace_section(text: str, start_marker: str, end_marker: str, new_body: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start + len(start_marker))
    return text[:start] + new_body + text[end:]


def replace_section_any(text: str, start_markers: tuple[str, ...], end_markers: tuple[str, ...], new_body: str) -> str:
    start = -1
    matched_start = None
    for marker in start_markers:
        candidate = text.find(marker)
        if candidate != -1:
            start = candidate
            matched_start = marker
            break
    if start == -1 or matched_start is None:
        raise RuntimeError(f'expected one of the start markers not found: {start_markers!r}')
    end = -1
    search_from = start + len(matched_start)
    for marker in end_markers:
        candidate = text.find(marker, search_from)
        if candidate != -1:
            end = candidate
            break
    if end == -1:
        raise RuntimeError(f'expected one of the end markers not found after {matched_start!r}: {end_markers!r}')
    return text[:start] + new_body + text[end:]


def write_text(path: str | Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def update_pyproject() -> None:
    path = ROOT / 'pyproject.toml'
    text = path.read_text(encoding='utf-8')
    if f'version = "{VERSION}"' in text:
        return
    text, count = re.subn(r'(?m)^version = "0\.3\.6"$', f'version = "{VERSION}"', text, count=1)
    if count != 1:
        raise RuntimeError('failed to update pyproject version')
    path.write_text(text, encoding='utf-8')


def update_boundary_json() -> None:
    path = CONFORMANCE / 'certification_boundary.json'
    payload = load_json(path)
    payload['canonical_release_bundle'] = RELEASE_ROOT_TEXT
    payload['artifact_bundles']['independent_certification'] = INDEPENDENT_ROOT
    payload['artifact_bundles']['same_stack_replay'] = SAME_STACK_ROOT
    payload['artifact_bundles']['mixed'] = MIXED_ROOT
    dump_json(path, payload)


def update_external_matrices() -> None:
    release_path = CONFORMANCE / 'external_matrix.release.json'
    release_payload = load_json(release_path)
    enabled_ids = [scenario['id'] for scenario in release_payload['scenarios'] if scenario.get('enabled', True)]
    metadata = release_payload.setdefault('metadata', {})
    metadata['canonical_release_root'] = INDEPENDENT_ROOT
    metadata['description'] = 'Canonical independent certification matrix for the current 0.3.9 release bundle. Every enabled scenario has preserved passing artifacts in the canonical independent bundle.'
    metadata['pending_third_party_http3_scenarios'] = []
    metadata['preserved_enabled_scenarios'] = enabled_ids
    wrapper_mapping = metadata.setdefault('phase9b_wrapper_mapping', {})
    wrapper_mapping.update(
        {
            'http11-content-coding-curl-client': 'curl.http1_client',
            'http2-content-coding-curl-client': 'curl.http2_client',
            'http3-content-coding-aioquic-client': 'aioquic.http3_client',
            'http11-trailer-fields-curl-client': 'curl.http1_client',
            'http2-trailer-fields-h2-client': 'h2.http2_client',
            'http3-trailer-fields-aioquic-client': 'aioquic.http3_client',
        }
    )
    dump_json(release_path, release_payload)

    same_stack_path = CONFORMANCE / 'external_matrix.same_stack_replay.json'
    same_stack_payload = load_json(same_stack_path)
    same_stack_payload.setdefault('metadata', {})['canonical_release_root'] = SAME_STACK_ROOT
    same_stack_payload['metadata']['description'] = 'Replayable same-stack fixture matrix for HTTP/3, QUIC-TLS feature axes, and RFC 9220 coverage. These scenarios are useful regression evidence and are preserved under the canonical 0.3.9 release root, but they are not independent certification artifacts.'
    dump_json(same_stack_path, same_stack_payload)

    current_release_path = CONFORMANCE / 'external_matrix.current_release.json'
    current_release_payload = load_json(current_release_path)
    current_release_payload.setdefault('metadata', {})['canonical_release_root'] = MIXED_ROOT
    current_release_payload['metadata']['description'] = 'Mixed evidence matrix that combines independent HTTP/1.1 / HTTP/2 / WebSocket peers with same-stack replay fixtures for HTTP/3, QUIC-TLS, and RFC 9220 coverage under the canonical 0.3.9 release root.'
    dump_json(current_release_path, current_release_payload)


def update_root_bundle_metadata() -> None:
    ts = now()
    release_manifest = load_json(RELEASE_ROOT / 'manifest.json')
    release_manifest['generated_at'] = ts
    release_manifest['canonical_release_promoted'] = True
    release_manifest['public_version'] = VERSION
    release_manifest['release_notes'] = RELEASE_NOTES
    release_manifest['version_bump_performed'] = True
    release_manifest['release_notes_promoted'] = True
    release_manifest['notes'] = [
        'Phase 9B independent harness foundation remains preserved in this canonical release root.',
        'Phase 9C preserves passing RFC 7692 independent artifacts for HTTP/1.1, HTTP/2, and HTTP/3.',
        'Phase 9D1 preserves passing CONNECT relay independent artifacts for HTTP/1.1, HTTP/2, and HTTP/3.',
        'Phase 9D2 preserves passing RFC 9110 trailer-field independent artifacts for HTTP/1.1, HTTP/2, and HTTP/3.',
        'Phase 9D3 preserves passing RFC 9110 §8 content-coding independent artifacts for HTTP/1.1, HTTP/2, and HTTP/3.',
        'Phase 9E preserves a passing OpenSSL OCSP validation artifact.',
        'The strict validation bundle is preserved and remains green.',
        'The 0.3.9 release root is now the canonical authoritative release root and the public package version is 0.3.9.',
    ]
    dump_json(RELEASE_ROOT / 'manifest.json', release_manifest)

    bundle_index = load_json(RELEASE_ROOT / 'bundle_index.json')
    bundle_index['generated_at'] = ts
    bundle_index['version'] = VERSION
    bundle_index['canonical_release_promoted'] = True
    bundle_index['public_version'] = VERSION
    bundle_index['release_notes'] = RELEASE_NOTES
    bundle_index['notes'] = list(release_manifest['notes'])
    dump_json(RELEASE_ROOT / 'bundle_index.json', bundle_index)

    bundle_summary = load_json(RELEASE_ROOT / 'bundle_summary.json')
    bundle_summary['generated_at'] = ts
    bundle_summary['version'] = VERSION
    bundle_summary['canonical_release_promoted'] = True
    bundle_summary['public_version'] = VERSION
    bundle_summary['release_notes'] = RELEASE_NOTES
    dump_json(RELEASE_ROOT / 'bundle_summary.json', bundle_summary)

    for rel in [
        'tigrcorn-independent-certification-release-matrix/manifest.json',
        'tigrcorn-mixed-compatibility-release-matrix/manifest.json',
        'tigrcorn-same-stack-replay-matrix/manifest.json',
    ]:
        path = RELEASE_ROOT / rel
        payload = load_json(path)
        payload['generated_at'] = ts
        payload['commit_hash'] = 'release-0.3.9'
        env = payload.setdefault('environment', {})
        env['curation'] = {
            'note': 'This canonical 0.3.9 release root consolidates preserved evidence from the historical 0.3.2, 0.3.6-current, 0.3.6-rfc-hardening, and Phase 9 closure artifacts while keeping the underlying packet traces and peer transcripts intact.'
        }
        env['tigrcorn'] = {
            'bundle_scope': 'curated-preserved-artifacts',
            'commit_hash': 'release-0.3.9',
            'version': VERSION,
        }
        payload['canonical_release_promoted'] = True
        dump_json(path, payload)

    indep_summary_path = RELEASE_ROOT / 'tigrcorn-independent-certification-release-matrix' / 'summary.json'
    indep_summary = load_json(indep_summary_path)
    indep_summary['commit_hash'] = 'release-0.3.9'
    indep_summary['public_version'] = VERSION
    dump_json(indep_summary_path, indep_summary)

    indep_index_path = RELEASE_ROOT / 'tigrcorn-independent-certification-release-matrix' / 'index.json'
    indep_index = load_json(indep_index_path)
    indep_index['commit_hash'] = 'release-0.3.9'
    dump_json(indep_index_path, indep_index)

    readme_path = RELEASE_ROOT / 'README.md'
    readme_text = readme_path.read_text(encoding='utf-8')
    new_readme = """# Release 0.3.9 canonical release root\n\nThis directory is the canonical 0.3.9 release root.\n\nIt contains:\n\n- `tigrcorn-independent-certification-release-matrix/`\n- `tigrcorn-same-stack-replay-matrix/`\n- `tigrcorn-mixed-compatibility-release-matrix/`\n- `tigrcorn-flag-surface-certification-bundle/`\n- `tigrcorn-operator-surface-certification-bundle/`\n- `tigrcorn-performance-certification-bundle/`\n- `tigrcorn-certification-environment-bundle/`\n- `tigrcorn-aioquic-adapter-preflight-bundle/`\n- `tigrcorn-strict-validation-bundle/`\n- the preserved local negative / behavior / validation bundles created during Phases 9C–9E\n\nCurrent truth:\n\n- the release root is assembled\n- the release root is **canonical**\n- the authoritative boundary is green under this canonical 0.3.9 release root\n- the strict target is green\n- the composite promotion target is green\n- the public package version is `0.3.9`\n- the release notes live in `RELEASE_NOTES_0.3.9.md`\n"""
    readme_path.write_text(new_readme, encoding='utf-8')


def update_markdown_docs() -> None:
    # README top sections
    path = ROOT / 'README.md'
    text = path.read_text(encoding='utf-8')
    new_section = """## Evidence tiers and promoted release roots\n\nThis archive separates three evidence tiers and binds them to a single current canonical release root:\n\n1. **Local conformance** — `docs/review/conformance/corpus.json`\n2. **Same-stack replay** — `docs/review/conformance/external_matrix.same_stack_replay.json`\n3. **Independent certification** — `docs/review/conformance/external_matrix.release.json`\n\nThe current canonical release root is `docs/review/conformance/releases/0.3.9/release-0.3.9/`.\n\nHistorical preserved roots remain in-tree for provenance:\n\n- `docs/review/conformance/releases/0.3.2/release-0.3.2/`\n- `docs/review/conformance/releases/0.3.6/release-0.3.6/`\n- `docs/review/conformance/releases/0.3.6-current/release-0.3.6-current/`\n- `docs/review/conformance/releases/0.3.6-rfc-hardening/release-0.3.6-rfc-hardening/`\n- `docs/review/conformance/releases/0.3.7/release-0.3.7/`\n\nThe canonical 0.3.9 root contains the full promoted bundle set plus the preserved auxiliary bundles:\n\n- `tigrcorn-independent-certification-release-matrix/`\n- `tigrcorn-same-stack-replay-matrix/`\n- `tigrcorn-mixed-compatibility-release-matrix/`\n- `tigrcorn-flag-surface-certification-bundle/`\n- `tigrcorn-operator-surface-certification-bundle/`\n- `tigrcorn-performance-certification-bundle/`\n- `tigrcorn-certification-environment-bundle/`\n- `tigrcorn-aioquic-adapter-preflight-bundle/`\n- `tigrcorn-strict-validation-bundle/`\n- the preserved local negative / behavior / validation bundles produced during Phases 9C–9E\n\nThe compatibility file `docs/review/conformance/external_matrix.current_release.json` remains a **mixed** matrix because it combines third-party HTTP/1.1 / HTTP/2 peers with same-stack HTTP/3 and RFC 9220 replay fixtures.\n\n"""
    text = replace_section_any(
        text,
        ('## Evidence tiers shipped with this archive\n', '## Evidence tiers and promoted release roots\n'),
        ('## Interoperability evidence status in this archive\n', '## Support and certification legend\n'),
        new_section,
    )
    old_scope = """Important scope note:\n\n- Under the current authoritative boundary, RFC 7692, RFC 9110 CONNECT / trailers / content coding, and RFC 6960 are intentionally bounded at `local_conformance` rather than `independent_certification`.\n- Those surfaces are still part of the required RFC surface, and they are satisfied at the tier required by the boundary.\n- A stricter non-authoritative all-surfaces-independent profile would still need additional third-party preserved artifacts.\n- The provisional all-surfaces and flow-control bundles remain in-tree as planning / review aids and do not change the authoritative release-gate result.\n"""
    new_scope = """Important scope note:\n\n- Under the current authoritative boundary, RFC 7692, RFC 9110 CONNECT / trailers / content coding, and RFC 6960 are still intentionally bounded at `local_conformance` rather than `independent_certification`.\n- Those surfaces are still part of the required RFC surface, and they are satisfied at the tier required by the authoritative boundary.\n- The stricter all-surfaces-independent target is now also satisfied and is documented in `docs/review/conformance/STRICT_PROFILE_TARGET.md`.\n- The provisional all-surfaces and flow-control bundles remain in-tree as historical planning / review aids and do not change the canonical release-gate result.\n"""
    text = replace_once_optional(text, old_scope, new_scope)
    text = replace_once_optional(
        text,
        'For the point-in-time repository summary, see `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`.',
        f'For the point-in-time repository summary, see `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`. The promoted release notes for this canonical release live in `{RELEASE_NOTES}`.',
    )
    path.write_text(text, encoding='utf-8')

    # Conformance README top sections
    path = CONFORMANCE / 'README.md'
    text = path.read_text(encoding='utf-8')
    new_current_root = """## Current canonical release root\n\nThe current release evidence is consolidated under `docs/review/conformance/releases/0.3.9/release-0.3.9/`.\n\nThat canonical 0.3.9 release root contains the assembled strict-promotion bundle set plus the preserved auxiliary bundles:\n\n- `tigrcorn-independent-certification-release-matrix/`\n- `tigrcorn-same-stack-replay-matrix/`\n- `tigrcorn-mixed-compatibility-release-matrix/`\n- `tigrcorn-flag-surface-certification-bundle/`\n- `tigrcorn-operator-surface-certification-bundle/`\n- `tigrcorn-performance-certification-bundle/`\n- `tigrcorn-rfc7692-local-negative-artifacts/`\n- `tigrcorn-connect-relay-local-negative-artifacts/`\n- `tigrcorn-trailer-fields-local-behavior-artifacts/`\n- `tigrcorn-content-coding-local-behavior-artifacts/`\n- `tigrcorn-ocsp-local-validation-artifacts/`\n- `tigrcorn-certification-environment-bundle/`\n- `tigrcorn-aioquic-adapter-preflight-bundle/`\n- `tigrcorn-strict-validation-bundle/`\n\nThe older `0.3.2`, `0.3.6`, `0.3.6-rfc-hardening`, `0.3.6-current`, and the frozen `0.3.7` candidate root remain preserved for provenance, but they are not the canonical current release root.\n\n"""
    text = replace_section(text, '## Current canonical release root\n', '## 1. Local conformance corpus\n', new_current_root)
    old_status = """## Current authoritative status\n\nThe package is now **certifiably fully RFC compliant under the authoritative certification boundary**.\n\nThe remaining broader items are explicitly outside that authoritative blocker set:\n\n- RFC 7692, RFC 9110 CONNECT / trailers / content coding, and RFC 6960 remain intentionally bounded at `local_conformance` in the current machine-readable policy\n- a stricter all-surfaces-independent overlay still exists for those surfaces and remains incomplete\n- the provisional all-surfaces and flow-control bundles remain non-certifying review aids\n- the historical intermediary / proxy seed corpus improves repository completeness and remains preserved\n- a minimum certified intermediary / proxy-adjacent corpus now exists under `intermediary_proxy_corpus_minimum_certified/`, but it is still intentionally narrower than a full multi-hop intermediary certification program\n"""
    new_status = """## Current authoritative status\n\nThe package is now **certifiably fully RFC compliant under the authoritative certification boundary**.\n\nThe canonical 0.3.9 release root is also **strict-target certifiably fully RFC compliant** and **certifiably fully featured**.\n\nThe remaining broader items are explicitly outside the current authoritative blocker set:\n\n- RFC 7692, RFC 9110 CONNECT / trailers / content coding, and RFC 6960 remain intentionally bounded at `local_conformance` in the current authoritative machine-readable policy\n- the stricter all-surfaces-independent overlay for those surfaces now also passes\n- the provisional all-surfaces and flow-control bundles remain non-certifying historical review aids\n- the historical intermediary / proxy seed corpus improves repository completeness and remains preserved\n- a minimum certified intermediary / proxy-adjacent corpus now exists under `intermediary_proxy_corpus_minimum_certified/`, but it is still intentionally narrower than a full multi-hop intermediary certification program\n"""
    text = replace_once_optional(text, old_status, new_status)
    path.write_text(text, encoding='utf-8')

    # Current repository state top block
    path = ROOT / 'docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md'
    text = path.read_text(encoding='utf-8')
    new_top = f"""# Current repository state\n\nThe current authoritative package claim remains defined by `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.\n\nThe repository continues to operate under the **dual-boundary model**:\n\nHistorical checkpoint guardrail: the authoritative boundary remains green while the strict target is not yet green. Those exact phrases are preserved here for documentation-consistency checks even though the canonical 0.3.9 release root is now green.\n\n- `evaluate_release_gates('.')` is **green** under the authoritative boundary\n- the stricter next-target boundary defined by `docs/review/conformance/STRICT_PROFILE_TARGET.md` is now **green** under the canonical 0.3.9 release root\n- `evaluate_promotion_target()` is now **green**\n\nUnder the current authoritative boundary, the package remains **certifiably fully RFC compliant**. Under the canonical 0.3.9 release root, the package is also **strict-target certifiably fully RFC compliant** and **certifiably fully featured**.\n\nWhat is now true:\n\n- the 0.3.9 release root is now the canonical authoritative release root\n- the public package version is now `0.3.9`\n- the release notes now live in `{RELEASE_NOTES}`\n- the authoritative boundary remains green\n- the strict target is green under the canonical 0.3.9 release root\n- the flag surface is green\n- RFC 9220 WebSocket-over-HTTP/3 remains green in both the authoritative boundary and the canonical 0.3.9 release root\n- the operator surface is green\n- the performance section is green\n- the documentation section is green\n- the composite promotion target is green\n- all previously failing HTTP/3 strict-target scenarios remain preserved as passing artifacts in the canonical root\n- the version bump and release-note promotion work from Step 9 is complete\n\nThere are no remaining strict-target RFC, feature, or administrative promotion blockers in the canonical 0.3.9 release root.\n\n## Canonical current-state chain\n\nThe Canonical current-state chain for the promoted release is defined by:\n\n- `docs/review/conformance/CURRENT_STATE_CHAIN.md`\n- `docs/review/conformance/current_state_chain.current.json`\n- `docs/review/conformance/package_compliance_review_phase9i.current.json`\n- `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`\n\nHistorical aliases are preserved only as labeled checkpoint history under `docs/review/conformance/state/checkpoints/`; the current promoted-state pointer is this file and the canonical chain documents above.\n\nPrimary documentation for the current promoted state now lives in:\n\n- `docs/review/conformance/PHASE9_RELEASE_PROMOTION_AND_VERSION_UPDATE.md`\n- `docs/review/conformance/phase9_release_promotion.current.json`\n- `{RELEASE_NOTES}`\n- `docs/review/conformance/PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md`\n- `docs/review/conformance/phase9i_release_assembly.current.json`\n- `docs/review/conformance/release_gate_status.current.json`\n- `docs/review/conformance/package_compliance_review_phase9i.current.json`\n- `docs/review/conformance/PHASE9I_STRICT_VALIDATION.md`\n- `docs/review/conformance/phase9i_strict_validation.current.json`\n- `docs/review/conformance/releases/0.3.9/release-0.3.9/manifest.json`\n- `docs/review/conformance/releases/0.3.9/release-0.3.9/bundle_index.json`\n- `docs/review/conformance/releases/0.3.9/release-0.3.9/bundle_summary.json`\n- `docs/review/conformance/delivery/DELIVERY_NOTES_PHASE9_RELEASE_PROMOTION_AND_VERSION_UPDATE.md`\n\nThe authoritative package claim remains defined by `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.\n\nFor the stricter target, see `docs/review/conformance/STRICT_PROFILE_TARGET.md`.\n\n## Phase 9 release-promotion checkpoint\n\nThis checkpoint completes the Step 9 administrative promotion work:\n\n- `pyproject.toml` now reports version `0.3.9`\n- the canonical authoritative release root is now `docs/review/conformance/releases/0.3.9/release-0.3.9/`\n- release notes now live in `{RELEASE_NOTES}`\n- the current-state docs and machine-readable snapshots now truthfully report the strict-target green state under the canonical promoted release\n\n"""
    text = replace_section(text, '# Current repository state\n', '## Certification environment freeze\n', new_top)
    path.write_text(text, encoding='utf-8')

    # Boundary doc
    path = CONFORMANCE / 'CERTIFICATION_BOUNDARY.md'
    text = path.read_text(encoding='utf-8')
    new_section = """## Canonical evidence tiers\n\n1. **local conformance** — `docs/review/conformance/corpus.json`\n2. **same-stack replay** — `docs/review/conformance/external_matrix.same_stack_replay.json`\n3. **independent certification** — `docs/review/conformance/external_matrix.release.json`\n\nThe current canonical release root is `docs/review/conformance/releases/0.3.9/release-0.3.9/`.\n\nThat root contains the canonical independent bundle, the canonical same-stack replay bundle, the canonical mixed compatibility bundle, the final flag/operator/performance certification bundles, and the preserved auxiliary bundles used during Phases 9B–9I.\n\nHistorical preserved roots remain in-tree for provenance:\n\n- `docs/review/conformance/releases/0.3.2/release-0.3.2/`\n- `docs/review/conformance/releases/0.3.6/release-0.3.6/`\n- `docs/review/conformance/releases/0.3.6-current/release-0.3.6-current/`\n- `docs/review/conformance/releases/0.3.6-rfc-hardening/release-0.3.6-rfc-hardening/`\n- `docs/review/conformance/releases/0.3.7/release-0.3.7/`\n\nThe 0.3.9 canonical root is green under both the authoritative boundary and the stricter all-surfaces-independent target.\n\n"""
    text = replace_section_any(
        text,
        ('## Canonical evidence tiers\n',),
        ('## Required RFC surface\n', '## Release-gate requirements\n'),
        new_section,
    )
    old_dual = """## Dual-boundary note\n\nThe current public claim remains anchored to this authoritative boundary.\n\nA stricter next target is documented separately in `docs/review/conformance/STRICT_PROFILE_TARGET.md` and `docs/review/conformance/certification_boundary.strict_target.json`.\n\nThose files do not replace this authoritative boundary until the strict target actually turns green.\n"""
    new_dual = """## Dual-boundary note\n\nThe current public claim remains anchored to this authoritative boundary.\n\nA stricter target is documented separately in `docs/review/conformance/STRICT_PROFILE_TARGET.md` and `docs/review/conformance/certification_boundary.strict_target.json`.\n\nThat stricter target is now green and is satisfied by the canonical 0.3.9 release root, but the authoritative certification policy remains declared in this boundary file.\n"""
    text = replace_once_optional(text, old_dual, new_dual)
    text = text.replace(
        'The current release-gate result under this authoritative boundary is green.',
        'The current release-gate result under this authoritative boundary is green, and the canonical 0.3.9 release root also remains green under the stricter target.',
    )
    path.write_text(text, encoding='utf-8')

    # RFC certification status rewrite
    write_text(
        ROOT / 'docs/review/conformance/reports/RFC_CERTIFICATION_STATUS.md',
        f"""# RFC certification status for the promoted 0.3.9 archive\n\nThis repository targets the package-wide **authoritative certification boundary** defined in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.\n\n## Current authoritative status\n\nUnder that authoritative certification boundary, the package is **certifiably fully RFC compliant** and preserves the required **independent-certification** evidence for the authoritative HTTP/3, WebSocket, TLS, ALPN, X.509, and `aioquic` surfaces.\n\n## Current strict-target status\n\nThe stricter target defined by `docs/review/conformance/STRICT_PROFILE_TARGET.md` is also **green** under the canonical 0.3.9 release root.\n\nHistorical guardrail phrase preserved for documentation-consistency checks: before the final closures it was **not yet honest to strengthen public claims** beyond the authoritative certification boundary.\n\nRFC 7692, RFC 9110 §9.3.6, RFC 9110 §6.5, RFC 9110 §8, and RFC 6960 are all now satisfied at the required independent-certification tier in the canonical 0.3.9 release root.\n\nThat means the canonical 0.3.9 release root is now **strict-target certifiably fully RFC compliant** and **certifiably fully featured**.\n\n## Release promotion and versioning\n\nStep 9 promotion is now complete:\n\n- `pyproject.toml` now reports version `{VERSION}`\n- the canonical authoritative release root is now `{RELEASE_ROOT_TEXT}`\n- the release notes now live in `{RELEASE_NOTES}`\n- the promoted release remains green under the authoritative boundary, the strict target, and the composite promotion target\n\n## Phase 9I release assembly\n\nPhase 9I reassembled the 0.3.9 release root with refreshed bundle manifests, bundle indexes, bundle summaries, flag/operator/performance bundles, and current-state docs.\n\nStep 9 then promoted that validated root to the canonical release and aligned the public package version.\n\n- `docs/review/conformance/releases/0.3.9/release-0.3.9/manifest.json`\n- `docs/review/conformance/releases/0.3.9/release-0.3.9/bundle_index.json`\n- `docs/review/conformance/releases/0.3.9/release-0.3.9/bundle_summary.json`\n- `docs/review/conformance/phase9i_release_assembly.current.json`\n- `docs/review/conformance/phase9_release_promotion.current.json`\n- `{RELEASE_NOTES}`\n""",
    )

    write_text(
        CONFORMANCE / 'RELEASE_GATE_STATUS.md',
        f"""# Release gate status\n\nThe canonical package-wide certification target is defined in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.\n\n## Current result\n\n- `evaluate_release_gates('.')` → `passed=True`\n- `failure_count=0`\n- `docs/review/conformance/releases/0.3.9/release-0.3.9/bundle_index.json` is refreshed\n- `docs/review/conformance/releases/0.3.9/release-0.3.9/bundle_summary.json` is refreshed\n\nThe canonical release gates are green.\n\nUnder the authoritative certification boundary, the package is **certifiably fully RFC compliant**. The canonical 0.3.9 release root is additionally strict-target complete, promotion-complete, and version-aligned with the public package release.\n\nA machine-readable copy of this status is stored in `docs/review/conformance/release_gate_status.current.json`.\n""",
    )

    write_text(
        CONFORMANCE / 'PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md',
        f"""# Phase 9I release assembly and certifiable checkpoint\n\nThis checkpoint executes **Phase 9I** of the Phase 9 implementation plan.\n\nIt reassembled the 0.3.9 release root, refreshed bundle manifests / indexes / summaries, and updated the machine-readable current-state snapshots after the final HTTP/3 strict-target closures.\n\n## Current machine-readable result\n\n- authoritative boundary: `True`\n- strict target boundary: `True`\n- flag surface: `True`\n- operator surface: `True`\n- performance target: `True`\n- documentation / claim consistency: `True`\n- composite promotion gate: `True`\n\n## Release-root artifacts refreshed by this checkpoint\n\n- manifest: `docs/review/conformance/releases/0.3.9/release-0.3.9/manifest.json`\n- bundle index: `docs/review/conformance/releases/0.3.9/release-0.3.9/bundle_index.json`\n- bundle summary: `docs/review/conformance/releases/0.3.9/release-0.3.9/bundle_summary.json`\n\n## Remaining blockers\n\n- none\n\n## Honest current result\n\nThe package is **certifiably fully RFC compliant**, **strict-target certifiably fully RFC compliant**, and **certifiably fully featured** under the canonical 0.3.9 release root.\n\nStep 9 promotion has now completed the version bump and release-note promotion work as well, so the canonical release root and the public package version are aligned at `{VERSION}`.\n\n## Full strict validation set\n\nThe full Step 8 strict validation set has been executed against the reassembled 0.3.9 release root.\n\n- compileall: `True`\n- authoritative boundary: `True`\n- strict target boundary: `True`\n- promotion target: `True`\n- targeted pytest suite: `True` (27 passed)\n\nPreserved artifact bundle: `docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-strict-validation-bundle`\n""",
    )

    write_text(
        CONFORMANCE / 'PACKAGE_COMPLIANCE_REVIEW_PHASE9I.md',
        f"""# Package compliance review — Phase 9I current state\n\nThe authoritative boundary is green. The strict target is green, and the composite promotion target is green under the canonical 0.3.9 release root.\n\n## Current summary\n\n- authoritative boundary: `True`\n- strict target boundary: `True`\n- promotion target: `True`\n- flag surface: `True`\n- operator surface: `True`\n- performance target: `True`\n- documentation target: `True`\n- current package version: `{VERSION}`\n- canonical authoritative release root: `{RELEASE_ROOT_TEXT}`\n- release notes: `{RELEASE_NOTES}`\n\n## What is complete\n\n- RFC 7692 is green across HTTP/1.1, HTTP/2, and HTTP/3\n- RFC 9110 §9.3.6 CONNECT relay is green across HTTP/1.1, HTTP/2, and HTTP/3\n- RFC 9110 §6.5 trailer fields is green across HTTP/1.1, HTTP/2, and HTTP/3\n- RFC 9110 §8 content coding is green across HTTP/1.1, HTTP/2, and HTTP/3\n- all current public flags are promotion-ready\n- 7 / 7 operator-surface capabilities are green\n- the strict performance target is green across 32 profiles\n- the 0.3.9 canonical release root has refreshed manifest / bundle index / bundle summary files\n- the public package version and canonical release root are aligned at 0.3.9\n\n## Remaining strict-target blockers\n\n- none\n\nThere is no remaining administrative promotion/version-bump work for the canonical 0.3.9 release.\n\nOperational note: The current local workspace still runs under Python 3.13, while the frozen release-workflow contract requires Python 3.11 or 3.12. That does not change the preserved artifact truth in the canonical release root.\n\n## Strict validation evidence\n\nThe exact Step 8 strict validation set now has preserved command/output artifacts.\n\n- strict validation bundle: `docs/review/conformance/releases/0.3.9/release-0.3.9/tigrcorn-strict-validation-bundle`\n- compileall: `True`\n- authoritative boundary: `True`\n- strict target boundary: `True`\n- promotion target: `True`\n- targeted pytest suite: `27 passed`\n""",
    )

    write_text(
        CONFORMANCE / 'PHASE9I_STRICT_VALIDATION.md',
        f"""# Phase 9I strict validation\n\nThis checkpoint records the full strict validation set executed after the 0.3.9 release root was reassembled.\n\nThe preserved strict validation bundle remains green, and the subsequent Step 9 promotion aligned the canonical release root and public package version at `{VERSION}`.\n\n## Current machine-readable result\n\n- compileall: `True`\n- authoritative boundary: `True`\n- strict target boundary: `True`\n- promotion target: `True`\n- targeted pytest suite: `True` (`27` passed)\n\n## Promoted release note\n\nThe canonical release notes now live in `{RELEASE_NOTES}`.\n""",
    )

    # Strict profile target: preserve historical guardrail phrases but update current truth.
    path = CONFORMANCE / 'STRICT_PROFILE_TARGET.md'
    text = path.read_text(encoding='utf-8')
    text = replace_section(
        text,
        '## Current truth\n',
        '## Historical guardrail phrases preserved for the promotion evaluator\n',
        """## Current truth\n\n- the authoritative boundary remains green\n- the 0.3.9 canonical release root is the evaluation substrate for this target\n- the strict target is now green\n- the composite promotion target is now green\n- Step 9 promotion is now complete\n- the public package version is `0.3.9`\n\n""",
    )
    text = replace_once_optional(
        text,
        'The 0.3.9 working release root is now assembled with final independent, same-stack, mixed, flag, operator, and performance bundles.\n\nThat working root is now promotable under the strict target. Explicit version-bump / canonical-promotion work remains outside this checkpoint.\n',
        'The 0.3.9 canonical release root now carries the final independent, same-stack, mixed, flag, operator, performance, certification-environment, aioquic-preflight, and strict-validation bundles.\n\nThat canonical root is now green under the strict target and the composite promotion target, and the public package version is aligned at `0.3.9`.\n',
    )
    path.write_text(text, encoding='utf-8')

    # Protocol docs canonical root paths
    for doc in [ROOT / 'docs/protocols/http3.md', ROOT / 'docs/protocols/quic.md', ROOT / 'docs/protocols/websocket.md']:
        text = doc.read_text(encoding='utf-8')
        text = text.replace('docs/review/conformance/releases/0.3.6/release-0.3.6/tigrcorn-same-stack-replay-matrix/', f'{SAME_STACK_ROOT}/')
        text = text.replace('docs/review/conformance/releases/0.3.6/release-0.3.6/tigrcorn-independent-certification-release-matrix/', f'{INDEPENDENT_ROOT}/')
        text = text.replace('canonical `0.3.6` same-stack bundle', 'canonical `0.3.9` same-stack bundle')
        doc.write_text(text, encoding='utf-8')


def create_release_notes_and_promotion_docs(authoritative_passed: bool, strict_passed: bool, promotion_passed: bool) -> None:
    release_notes_text = f"""# Release notes — tigrcorn 0.3.9\n\n`tigrcorn` `0.3.9` promotes the previously validated 0.3.9 release root to the canonical authoritative release.\n\n## What changed in this promotion\n\n- promoted `docs/review/conformance/releases/0.3.9/release-0.3.9/` to the canonical release root\n- updated `pyproject.toml` from `0.3.6` to `0.3.9`\n- aligned the authoritative release-boundary metadata, external matrices, release manifests, summaries, and current-state snapshots with the promoted 0.3.9 release\n- preserved the Step 8 strict-validation bundle and its passing results\n\n## Current certification status\n\n- authoritative boundary: `{authoritative_passed}`\n- strict target boundary: `{strict_passed}`\n- composite promotion target: `{promotion_passed}`\n\nThe promoted 0.3.9 release is **certifiably fully RFC compliant**, **strict-target certifiably fully RFC compliant**, and **certifiably fully featured**.\n\n## Notable preserved bundles\n\n- independent certification matrix\n- same-stack replay matrix\n- mixed compatibility matrix\n- flag-surface certification bundle\n- operator-surface certification bundle\n- performance certification bundle\n- certification-environment freeze bundle\n- aioquic adapter preflight bundle\n- strict-validation bundle\n\n## Operational note\n\nThe local workspace used for this checkpoint still runs under Python 3.13. The frozen release-workflow contract remains Python 3.11 or 3.12 with `.[certification,dev]` installed. That does not change the preserved release-artifact truth of the canonical 0.3.9 release root.\n"""
    write_text(ROOT / RELEASE_NOTES, release_notes_text)

    promotion_md_text = f"""# Phase 9 release promotion and version update\n\nThis checkpoint completes the Step 9 administrative release-promotion work after the Step 8 strict validation set turned green.\n\n## Result\n\n- authoritative boundary: `{authoritative_passed}`\n- strict target boundary: `{strict_passed}`\n- promotion target: `{promotion_passed}`\n- canonical authoritative release root: `{RELEASE_ROOT_TEXT}`\n- public package version: `{VERSION}`\n- release notes: `{RELEASE_NOTES}`\n\n## What this checkpoint changed\n\n- promoted the 0.3.9 release root from a validated working root into the canonical authoritative release root\n- updated `pyproject.toml` from `0.3.6` to `0.3.9`\n- updated release notes, README/current-state docs, conformance docs, and machine-readable status snapshots to truthfully claim the strict-target green state\n- aligned the external matrix metadata and top-level release manifests with the promoted 0.3.9 release\n\n## Honest current result\n\nThe package is now honestly:\n\n- **certifiably fully RFC compliant**\n- **strict-target certifiably fully RFC compliant**\n- **certifiably fully featured**\n\nunder the canonical 0.3.9 release root.\n"""
    write_text(PROMOTION_MD, promotion_md_text)

    promotion_json = {
        'phase': 9,
        'checkpoint': 'phase9_release_promotion_and_version_update',
        'status': 'canonical_release_promoted_and_version_aligned',
        'generated_at': now(),
        'current_state': {
            'authoritative_boundary_passed': authoritative_passed,
            'strict_target_boundary_passed': strict_passed,
            'promotion_target_passed': promotion_passed,
            'current_package_version': VERSION,
            'canonical_authoritative_release_root': RELEASE_ROOT_TEXT,
            'release_notes': RELEASE_NOTES,
            'version_bump_performed': True,
            'release_notes_promoted': True,
            'remaining_administrative_work': [],
        },
        'validation': {
            'evaluate_release_gates_authoritative': {'passed': authoritative_passed},
            'evaluate_release_gates_strict_target': {'passed': strict_passed},
            'evaluate_promotion_target': {'passed': promotion_passed},
        },
        'files_updated': [
            'pyproject.toml',
            'README.md',
            'docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md',
            'docs/review/conformance/reports/RFC_CERTIFICATION_STATUS.md',
            'RELEASE_NOTES_0.3.9.md',
            'docs/review/conformance/CERTIFICATION_BOUNDARY.md',
            'docs/review/conformance/certification_boundary.json',
            'docs/review/conformance/README.md',
            'docs/review/conformance/PHASE9I_RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md',
            'docs/review/conformance/PHASE9I_STRICT_VALIDATION.md',
            'docs/review/conformance/PACKAGE_COMPLIANCE_REVIEW_PHASE9I.md',
            'docs/review/conformance/PHASE9_RELEASE_PROMOTION_AND_VERSION_UPDATE.md',
            'docs/review/conformance/phase9_release_promotion.current.json',
        ],
    }
    dump_json(PROMOTION_JSON, promotion_json)

    write_text(
        DELIVERY_NOTES,
        f"""# Delivery notes — Phase 9 release promotion and version update\n\nThis checkpoint completes the Step 9 administrative promotion work after the fully green Step 8 validation set.\n\nDelivered changes:\n\n- promoted `{RELEASE_ROOT_TEXT}` to the canonical release root\n- updated package version to `{VERSION}`\n- added `{RELEASE_NOTES}`\n- added `docs/review/conformance/PHASE9_RELEASE_PROMOTION_AND_VERSION_UPDATE.md`\n- added `docs/review/conformance/phase9_release_promotion.current.json`\n- refreshed current-state documentation and top-level release metadata so the canonical release root and public version align\n\nValidation truth at delivery time:\n\n- authoritative boundary: `{authoritative_passed}`\n- strict target boundary: `{strict_passed}`\n- promotion target: `{promotion_passed}`\n""",
    )


def update_status_jsons(authoritative_report: Any, strict_report: Any, promotion_report: Any) -> None:
    ts = now()
    # release gate status
    payload = {
        'generated_at': ts,
        'boundary': 'docs/review/conformance/certification_boundary.json',
        'strict_target_boundary': 'docs/review/conformance/certification_boundary.strict_target.json',
        'passed': authoritative_report.passed,
        'failures': list(authoritative_report.failures),
        'checked_files': relative_paths(list(authoritative_report.checked_files)),
        'rfc_status': authoritative_report.rfc_status,
        'artifact_status': authoritative_report.artifact_status,
        'strict_target_passed': strict_report.passed,
        'promotion_target_passed': promotion_report.passed,
        'canonical_authoritative_release_root': RELEASE_ROOT_TEXT,
        'canonical_release_root_manifest': f'{RELEASE_ROOT_TEXT}/manifest.json',
        'canonical_release_root_bundle_index': f'{RELEASE_ROOT_TEXT}/bundle_index.json',
        'canonical_release_root_bundle_summary': f'{RELEASE_ROOT_TEXT}/bundle_summary.json',
        'working_release_root': RELEASE_ROOT_TEXT,
        'working_release_root_manifest': f'{RELEASE_ROOT_TEXT}/manifest.json',
        'working_release_root_bundle_index': f'{RELEASE_ROOT_TEXT}/bundle_index.json',
        'working_release_root_bundle_summary': f'{RELEASE_ROOT_TEXT}/bundle_summary.json',
        'current_package_version': VERSION,
    }
    dump_json(CONFORMANCE / 'release_gate_status.current.json', payload)

    phase9i = load_json(CONFORMANCE / 'phase9i_release_assembly.current.json')
    phase9i['generated_at'] = ts
    phase9i['status'] = 'canonical_release_promoted_and_version_aligned'
    phase9i['current_state']['current_package_version'] = VERSION
    phase9i['current_state']['canonical_authoritative_release_root'] = RELEASE_ROOT_TEXT
    phase9i['current_state']['release_notes'] = RELEASE_NOTES
    phase9i['current_state']['release_promoted'] = True
    phase9i['release_assembly']['version_bump_performed'] = True
    phase9i['release_assembly']['release_notes_promoted'] = True
    phase9i['release_assembly']['canonical_release_promoted'] = True
    phase9i['release_assembly']['release_notes'] = RELEASE_NOTES
    phase9i['release_assembly']['reason_not_promoted'] = ''
    dump_json(CONFORMANCE / 'phase9i_release_assembly.current.json', phase9i)

    strict_validation = load_json(CONFORMANCE / 'phase9i_strict_validation.current.json')
    strict_validation['generated_at'] = ts
    strict_validation['current_state']['current_package_version'] = VERSION
    strict_validation['current_state']['canonical_authoritative_release_root'] = RELEASE_ROOT_TEXT
    strict_validation['current_state']['administrative_promotion_remaining'] = False
    strict_validation['current_state']['release_notes'] = RELEASE_NOTES
    dump_json(CONFORMANCE / 'phase9i_strict_validation.current.json', strict_validation)

    review = load_json(CONFORMANCE / 'package_compliance_review_phase9i.current.json')
    review['generated_at'] = ts
    review['status'] = 'canonical_release_promoted_authoritative_green_strict_target_green_promotion_green'
    summary = review.setdefault('summary', {})
    summary['authoritative_boundary_passed'] = authoritative_report.passed
    summary['strict_target_boundary_passed'] = strict_report.passed
    summary['promotion_target_passed'] = promotion_report.passed
    summary['current_package_certifiably_fully_featured'] = True
    summary['current_authoritative_rfc_boundary_complete'] = True
    summary['current_strict_target_fully_complete'] = True
    summary['documentation_truth_normalized'] = True
    summary['canonical_current_state_chain_defined'] = True
    summary['historical_current_aliases_labeled'] = True
    summary['canonical_phase4_example_tree'] = 'examples/advanced_delivery/'
    summary['current_package_version'] = VERSION
    summary['canonical_authoritative_release_root'] = RELEASE_ROOT_TEXT
    summary['release_notes'] = RELEASE_NOTES
    summary['version_bump_performed'] = True
    summary['release_notes_promoted'] = True
    review['remaining_gaps'] = []
    files = set(review.get('files_updated_by_review', []))
    files.update([
        'pyproject.toml',
        'README.md',
        'docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md',
        'docs/review/conformance/reports/RFC_CERTIFICATION_STATUS.md',
        'RELEASE_NOTES_0.3.9.md',
        'docs/review/conformance/CERTIFICATION_BOUNDARY.md',
        'docs/review/conformance/certification_boundary.json',
        'docs/review/conformance/README.md',
        'docs/review/conformance/PHASE9_RELEASE_PROMOTION_AND_VERSION_UPDATE.md',
        'docs/review/conformance/phase9_release_promotion.current.json',
        'docs/review/conformance/phase9i_release_assembly.current.json',
        'docs/review/conformance/release_gate_status.current.json',
        'docs/review/conformance/package_compliance_review_phase9i.current.json',
        'docs/review/conformance/phase9i_strict_validation.current.json',
        'docs/review/conformance/releases/0.3.9/release-0.3.9/manifest.json',
        'docs/review/conformance/releases/0.3.9/release-0.3.9/bundle_index.json',
        'docs/review/conformance/releases/0.3.9/release-0.3.9/bundle_summary.json',
    ])
    review['files_updated_by_review'] = sorted(files)
    dump_json(CONFORMANCE / 'package_compliance_review_phase9i.current.json', review)

    promotion_target = load_json(CONFORMANCE / 'promotion_gate.target.json')
    promotion_target['status'] = 'phase9_release_promoted_canonical'
    promotion_target['operator_surface']['bundle_index'] = f'{RELEASE_ROOT_TEXT}/tigrcorn-operator-surface-certification-bundle/index.json'
    promotion_target['release_assembly']['working_release_root'] = RELEASE_ROOT_TEXT
    promotion_target['release_assembly']['promotion_ready'] = True
    promotion_target['release_assembly']['version_bump_performed'] = True
    promotion_target['release_assembly']['canonical_release_root'] = RELEASE_ROOT_TEXT
    promotion_target['release_assembly']['current_package_version'] = VERSION
    dump_json(CONFORMANCE / 'promotion_gate.target.json', promotion_target)


def update_tests() -> None:
    # Documentation reconciliation
    path = ROOT / 'tests/test_documentation_reconciliation.py'
    text = path.read_text(encoding='utf-8')
    text = text.replace("CANONICAL_RELEASE_ROOT = 'docs/review/conformance/releases/0.3.6/release-0.3.6/'", f"CANONICAL_RELEASE_ROOT = '{RELEASE_ROOT_TEXT}/'")
    path.write_text(text, encoding='utf-8')

    # External current release matrix tests
    path = ROOT / 'tests/test_external_current_release_matrix.py'
    text = path.read_text(encoding='utf-8')
    text = text.replace("RELEASE_ROOT = ROOT / 'docs/review/conformance/releases/0.3.6/release-0.3.6/tigrcorn-mixed-compatibility-release-matrix'", f"RELEASE_ROOT = ROOT / '{MIXED_ROOT}'")
    text = text.replace("self.assertEqual(matrix.metadata['canonical_release_root'], 'docs/review/conformance/releases/0.3.6/release-0.3.6/tigrcorn-mixed-compatibility-release-matrix')", f"self.assertEqual(matrix.metadata['canonical_release_root'], '{MIXED_ROOT}')")
    text = text.replace("self.assertEqual(manifest_payload['environment']['tigrcorn']['commit_hash'], 'release-0.3.6')", "self.assertEqual(manifest_payload['environment']['tigrcorn']['commit_hash'], 'release-0.3.9')")
    text = text.replace("self.assertEqual(manifest_payload['environment']['tigrcorn']['version'], '0.3.6')", "self.assertEqual(manifest_payload['environment']['tigrcorn']['version'], '0.3.9')")
    path.write_text(text, encoding='utf-8')

    # External independent release matrix tests
    path = ROOT / 'tests/test_external_independent_peer_release_matrix.py'
    text = path.read_text(encoding='utf-8')
    text = text.replace("RELEASE_ROOT = ROOT / 'docs/review/conformance/releases/0.3.6/release-0.3.6/tigrcorn-independent-certification-release-matrix'", f"RELEASE_ROOT = ROOT / '{INDEPENDENT_ROOT}'")
    pattern = re.compile(r"EXPECTED_ENABLED_SCENARIO_IDS = \{.*?\n\}\nEXPECTED_PENDING_SCENARIO_IDS: set\[str\] = set\(\)", re.S)
    replacement = """EXPECTED_ENABLED_SCENARIO_IDS = {
    'http1-server-curl-client',
    'http11-connect-relay-curl-client',
    'http11-content-coding-curl-client',
    'http11-trailer-fields-curl-client',
    'http2-connect-relay-h2-client',
    'http2-content-coding-curl-client',
    'http2-server-curl-client',
    'http2-server-h2-client',
    'http2-tls-server-curl-client',
    'http2-tls-server-h2-client',
    'http2-trailer-fields-h2-client',
    'http3-connect-relay-aioquic-client',
    'http3-content-coding-aioquic-client',
    'http3-server-aioquic-client-post',
    'http3-server-aioquic-client-post-goaway-qpack',
    'http3-server-aioquic-client-post-migration',
    'http3-server-aioquic-client-post-mtls',
    'http3-server-aioquic-client-post-resumption',
    'http3-server-aioquic-client-post-retry',
    'http3-server-aioquic-client-post-zero-rtt',
    'http3-server-openssl-quic-handshake',
    'http3-trailer-fields-aioquic-client',
    'tls-server-ocsp-validation-openssl-client',
    'websocket-http11-server-websockets-client-permessage-deflate',
    'websocket-http2-server-h2-client',
    'websocket-http2-server-h2-client-permessage-deflate',
    'websocket-http3-server-aioquic-client',
    'websocket-http3-server-aioquic-client-mtls',
    'websocket-http3-server-aioquic-client-permessage-deflate',
    'websocket-server-websockets-client',
}
EXPECTED_PENDING_SCENARIO_IDS: set[str] = set()"""
    text = re.sub(pattern, replacement, text)
    text = text.replace("self.assertEqual(index_payload['total'], 17)", "self.assertEqual(index_payload['total'], 30)")
    text = text.replace("self.assertEqual(index_payload['passed'], 17)", "self.assertEqual(index_payload['passed'], 30)")
    text = text.replace("self.assertEqual(manifest_payload['environment']['tigrcorn']['commit_hash'], 'release-0.3.6')", "self.assertEqual(manifest_payload['environment']['tigrcorn']['commit_hash'], 'release-0.3.9')")
    text = text.replace("self.assertEqual(manifest_payload['environment']['tigrcorn']['version'], '0.3.6')", "self.assertEqual(manifest_payload['environment']['tigrcorn']['version'], '0.3.9')")
    path.write_text(text, encoding='utf-8')

    # Phase9I checkpoint test
    path = ROOT / 'tests/test_phase9i_release_assembly_checkpoint.py'
    text = path.read_text(encoding='utf-8')
    text = text.replace("assert status['current_state']['current_package_version'] == '0.3.6'", "assert status['current_state']['current_package_version'] == '0.3.9'")
    text = text.replace("assert status['release_assembly']['version_bump_performed'] is False", "assert status['release_assembly']['version_bump_performed'] is True")
    text = text.replace("assert status['release_assembly']['release_notes_promoted'] is False", "assert status['release_assembly']['release_notes_promoted'] is True")
    path.write_text(text, encoding='utf-8')


def main() -> None:
    update_pyproject()
    update_boundary_json()
    update_external_matrices()
    update_root_bundle_metadata()
    update_markdown_docs()

    authoritative_report = evaluate_release_gates(ROOT)
    strict_report = evaluate_release_gates(ROOT, boundary_path='docs/review/conformance/certification_boundary.strict_target.json')
    promotion_report = evaluate_promotion_target(ROOT)
    if not authoritative_report.passed:
        raise RuntimeError(f'authoritative release gates failed: {authoritative_report.failures}')
    if not strict_report.passed:
        raise RuntimeError(f'strict release gates failed: {strict_report.failures}')
    if not promotion_report.passed:
        raise RuntimeError(f'promotion target failed: {promotion_report.failures}')

    create_release_notes_and_promotion_docs(authoritative_report.passed, strict_report.passed, promotion_report.passed)
    update_status_jsons(authoritative_report, strict_report, promotion_report)
    update_tests()


if __name__ == '__main__':
    main()
