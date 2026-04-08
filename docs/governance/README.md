# GitHub governance

This directory tracks mutable GitHub control-plane policy that complements `docs/gov/`.

Use it for:

- branch and tag protection/ruleset policy
- environment policy for `ci`, `staging`, `testpypi`, `pypi`, and `docs`
- GitHub-side controls that cannot be frozen into release artifacts

Current primary document:

- `gh_ctrl.md` - required GitHub settings, workflow policy, and remaining manual activation steps
- `release_auto.md` - automated prerelease/release pipeline contract, provenance, and honesty boundaries
- `DEFAULT_AUDIT_POLICY.md` - generated-default and audit-source authority
- `RISK_REGISTER_POLICY.md` - machine-readable risk register ownership and fail-closed rule
- `TEST_STYLE_POLICY.md` - pytest-forward runner policy and legacy unittest containment
