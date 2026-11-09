# Release certification automated release checkpoint

This checkpoint records the mutable-tree release automation surface added after the canonical `0.3.9` promoted release root.

## What changed

- added `tools/cert/release_auto.py` to generate package-owned claim, risk, evidence-index, release-summary, and Pages artifacts
- updated `.github/workflows/publish-all-packages.yml` to build selected packages in `staging`, expose workflow-dispatch checkboxes for GitHub Release, PyPI, and npmjs publication, expose a package-selection dropdown for all packages, Tigrcorn Python packages, probes, or one named package, publish through token secrets, attest distributions, attach release assets, and deploy release Pages
- updated `.github/workflows/docs.yml` to regenerate and deploy the release-evidence Pages bundle for the mutable docs surface
- updated `scripts/ci/validate.sh` and `.github/workflows/_reusable-ci.yml` so Release certification release artifacts are generated, tested, and retained in CI
- documented the new control-plane contract in `docs/governance/release_auto.md`

## Validation

- `python tools/cert/release_auto.py`
- `python -m compileall -q src benchmarks tools`
- `python -m pytest -q tests/test_release_auto.py`
- `python tools/cert/status.py`
- broader mutable-tree pytest slice also passed: `79 passed, 2 skipped`

## Honesty boundary

This checkpoint proves that the mutable tree contains the release automation definition and generated release evidence surface.

It does not prove remote GitHub environment approval, secret configuration, successful TestPyPI/PyPI/npmjs publication, GitHub Release asset attachment, artifact attestation visibility, or GitHub Pages deployment until those systems show the successful run.
