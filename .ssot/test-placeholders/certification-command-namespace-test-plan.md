# Certification Command Namespace Test Plan

Planned T2 coverage for `feat:certification-command-namespace`.

This placeholder owns the planned pytest coverage for:

- `tigrcorn certify static` umbrella CLI dispatch into `tigrcorn-certification`.
- Import-boundary checks that keep `tigrcorn-certification` a leaf package.
- Static certification output-directory and evidence-shape contract checks.
- Fail-closed behavior for unknown certification surfaces and unavailable required capabilities.

Implementation tests should move to `tests/test_certification_command_namespace.py` when runtime code is added.
