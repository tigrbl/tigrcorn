# Current repository state — Phase 7 negative-certification checkpoint

This checkpoint records the mutable-tree Phase 7 negative-certification closure work.

## What changed

- `src/tigrcorn/config/negative_surface.py` now defines the package-owned fail-state registry, the per-surface adversarial corpora, and the expected-outcome bundle metadata.
- Generated artifacts now exist at `docs/conformance/fail_state_registry.json`, `docs/conformance/fail_state_registry.md`, `docs/conformance/negative_corpora.json`, `docs/conformance/negative_corpora.md`, `docs/conformance/negative_bundles.json`, `docs/conformance/negative_bundles.md`, and `docs/conformance/negative_bundles/`.
- The fail-state registry now freezes package-owned behavior for proxy spoofing, early-data downgrade rejection, QUIC transport failures, origin/pathsend rejection, CONNECT anti-abuse posture, TLS/X.509 strict-validation failure, and mixed-topology gate rejection.
- Generated negative bundles now point to preserved historical release-root artifact trees where they already exist, including the canonical CONNECT relay and OCSP local-validation negative bundles under the `0.3.9` release root.
- CI now regenerates the Phase 7 artifacts and runs `tests/test_phase7_negative_certification.py`.

## Claim status

- `TC-NEG-FAIL-STATE-REGISTRY` is now implemented in-tree.
- `TC-NEG-ADVERSARIAL-CORPORA` is now implemented in-tree.
- `TC-NEG-BUNDLE-PRESERVATION` is now implemented in-tree.

## Current package truth

- The working tree still evaluates as **certifiably fully RFC compliant** under the authoritative certification boundary.
- The canonical `0.3.9` release root still evaluates as **strict-target certifiably fully RFC compliant** and **certifiably fully featured**.
- The new Phase 7 negative-certification artifacts are mutable-tree outputs only; they have not yet been promoted into a superseding frozen release root.

## Validation used for this checkpoint

- `python tools/cert/negative_surface.py`
- `python -m unittest tests.test_phase7_negative_certification`
- `python -m unittest tests.test_release_gates tests.test_phase5_origin_contract tests.test_phase9d1_connect_relay_local_negatives`
- `python tools/cert/status.py`

## Honest limitation

Remote GitHub required-check enforcement for the new Phase 7 tests still depends on GitHub-side ruleset and environment activation outside this repository tree.
