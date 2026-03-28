# Operator docs index

This folder is the mutable operator-facing documentation entrypoint.

Read in this order:

1. `../../README.md`
2. `cli.md`
3. `public.md`
4. `../LIFECYCLE_AND_EMBEDDED_SERVER.md`
5. `../review/conformance/state/CURRENT_REPOSITORY_STATE.md`

What belongs here:

- CLI usage and flag-family guidance
- public operator/programmatic surface docs
- operator-focused examples and pointers into conformance materials

What does **not** belong here:

- immutable release artifacts
- canonical current-state reports
- release-root bundle material

When public CLI or API behavior changes, update this folder together with code, tests, machine-readable truth files, and `README.md`.
