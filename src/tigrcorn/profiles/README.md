# Blessed Profiles

This package module contains the canonical blessed deployment profile artifacts.

These JSON files are directly consumable via `tigrcorn --config <path>` because they include runtime config blocks plus profile metadata.

Read next:

1. `../docs/ops/profiles.md`
2. `../docs/conformance/profile_bundles.md`
3. `../docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`

- `src/tigrcorn/profiles/default.profile.json`
  - extends: `none`
  - required overrides: `none`
- `src/tigrcorn/profiles/strict-h1-origin.profile.json`
  - extends: `default`
  - required overrides: `none`
- `src/tigrcorn/profiles/strict-h2-origin.profile.json`
  - extends: `strict-h1-origin`
  - required overrides: `tls.certfile, tls.keyfile`
- `src/tigrcorn/profiles/strict-h3-edge.profile.json`
  - extends: `strict-h2-origin`
  - required overrides: `tls.certfile, tls.keyfile`
- `src/tigrcorn/profiles/strict-mtls-origin.profile.json`
  - extends: `strict-h2-origin`
  - required overrides: `tls.certfile, tls.keyfile, tls.ca_certs`
- `src/tigrcorn/profiles/static-origin.profile.json`
  - extends: `strict-h1-origin`
  - required overrides: `static.mount`
