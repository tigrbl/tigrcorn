# Risk Register Policy

This document governs the machine-readable risk register and traceability graph.

Policy:

- `docs/conformance/risk/RISK_REGISTER.json` is the package-owned machine-readable risk register for release-gated governance work.
- `docs/conformance/risk/RISK_TRACEABILITY.json` links each governed risk to claims, tests, and retained evidence.
- Open blocking risks are not allowed to pass release gates.
- Risk rows must name an owner, a status, and release-gate blocking posture.
- Evidence references must point to files or directories that exist in the working tree or preserved release roots.
- Risk entries may be narrower than the mutable working note in `docs/notes/risk_reg.md`; the machine-readable register is the release-gated subset, not a replacement for planning notes.

Authority:

- Governance ownership remains package-owned and local to this repository.
- Promotion-facing truth lives in the machine-readable register, the traceability graph, and current-state docs together.
