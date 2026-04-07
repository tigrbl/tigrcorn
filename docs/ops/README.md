# Operator docs index

This folder is the mutable operator-facing documentation entrypoint.

Read in this order:

1. `../../README.md`
2. `profiles.md`
3. `defaults.md`
4. `policies.md`
5. `cli.md`
6. `public.md`
7. `../LIFECYCLE_AND_EMBEDDED_SERVER.md`
8. `../review/conformance/state/CURRENT_REPOSITORY_STATE.md`

What belongs here:

- CLI usage and flag-family guidance
- blessed deployment profile guidance
- generated default/help parity tables and profile-effective default audits
- generated proxy-contract, precedence, policy-surface, and QUIC semantic contract tables
- public operator/programmatic surface docs
- operator-focused examples and pointers into conformance materials

What does **not** belong here:

- immutable release artifacts
- canonical current-state reports
- release-root bundle material

When public CLI or API behavior changes, update this folder together with code, tests, machine-readable truth files, and `README.md`.
