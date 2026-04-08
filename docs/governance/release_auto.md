# Release automation

This document defines the mutable-tree automation contract for prerelease, release-candidate, TestPyPI, PyPI, GitHub Release, attestation, and Pages publication.

## Package-owned contract

- distributions are built exactly once in the `staging` environment
- downstream publication jobs consume the same uploaded `dist/` artifact rather than rebuilding
- TestPyPI and PyPI publication use OIDC-based trusted publishing
- generated release evidence is emitted from `tools/cert/release_auto.py`
- release assets include generated claim, risk, evidence-index, release-note, and current-state outputs
- release Pages content is generated from the same release evidence set

## Generated release artifacts

The release automation generator writes:

- `docs/conformance/claim_rep.json`
- `docs/conformance/claim_rep.md`
- `docs/conformance/risk_stat.json`
- `docs/conformance/risk_stat.md`
- `docs/conformance/evidence_ix.json`
- `docs/conformance/evidence_ix.md`
- `docs/conformance/release_auto.json`
- `docs/conformance/relnotes.json`
- `docs/conformance/relnotes.md`
- `.artifacts/pages/`

These files are package-owned summaries. They do not replace the canonical frozen release root, but they make the mutable-tree release surface auditable and reproducible.

## Workflow topology

- `.github/workflows/publish-pypi.yml` builds, validates, attests, publishes, attaches release assets, and deploys the release-evidence Pages bundle
- `.github/workflows/docs.yml` regenerates the mutable documentation and release-evidence Pages bundle for the docs surface
- `scripts/ci/validate.sh` regenerates the Phase 9 release artifacts so parity failures break CI before a release run

## Honesty boundary

Repository-local files can define the release pipeline, but they cannot prove that remote publication already happened.

Do not claim any of the following unless the external system shows the successful run and resulting publication:

- TestPyPI publication
- PyPI publication
- GitHub Release asset attachment
- artifact attestation visibility
- GitHub Pages deployment
- environment approval or trusted-publisher registration on GitHub, TestPyPI, or PyPI

## Remote activation still required

The following must exist outside this working tree:

- GitHub environments `staging`, `testpypi`, `pypi`, and `docs`
- GitHub Pages enabled for the repository
- trusted publisher registration on TestPyPI and PyPI for this repository/workflow identity
- repository rulesets that require the release and validation workflows
