# Profile Conformance Bundles

This document indexes the generated Phase 1 profile bundles.

| Profile | Claim IDs | Required overrides | Artifact |
|---|---|---|---|
| `default` | TC-PROFILE-DEFAULT-BASELINE | `none` | `profiles/default.profile.json` |
| `strict-h1-origin` | TC-PROFILE-DEFAULT-BASELINE, TC-PROFILE-STRICT-H1-ORIGIN | `none` | `profiles/strict-h1-origin.profile.json` |
| `strict-h2-origin` | TC-PROFILE-DEFAULT-BASELINE, TC-PROFILE-STRICT-H1-ORIGIN, TC-PROFILE-STRICT-H2-ORIGIN | `tls.certfile, tls.keyfile` | `profiles/strict-h2-origin.profile.json` |
| `strict-h3-edge` | TC-PROFILE-DEFAULT-BASELINE, TC-PROFILE-STRICT-H1-ORIGIN, TC-PROFILE-STRICT-H2-ORIGIN, TC-PROFILE-STRICT-H3-EDGE | `tls.certfile, tls.keyfile` | `profiles/strict-h3-edge.profile.json` |
| `strict-mtls-origin` | TC-PROFILE-DEFAULT-BASELINE, TC-PROFILE-STRICT-H1-ORIGIN, TC-PROFILE-STRICT-H2-ORIGIN, TC-PROFILE-STRICT-MTLS-ORIGIN | `tls.certfile, tls.keyfile, tls.ca_certs` | `profiles/strict-mtls-origin.profile.json` |
| `static-origin` | TC-PROFILE-DEFAULT-BASELINE, TC-PROFILE-STRICT-H1-ORIGIN, TC-PROFILE-STATIC-ORIGIN | `static.mount` | `profiles/static-origin.profile.json` |
