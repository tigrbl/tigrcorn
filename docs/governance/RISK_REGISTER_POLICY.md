# Risk Register Policy

This document governs SSOT-backed risk rows and their traceability links.

Policy:

- `.ssot/registry.json` is the only authoritative machine-readable source for governed risk rows.
- Each SSOT risk row must carry machine-readable links to claims, tests, evidence, and release-blocking posture.
- Open blocking risks are not allowed to pass release gates.
- Risk rows must name an owner, a status, and release-gate blocking posture.
- Evidence references must point to files or directories that exist in the working tree or preserved release roots.
- Standalone risk-register projection files are legacy and shall not be maintained.

Authority:

- Governance ownership remains package-owned and local to this repository.
- Promotion-facing truth lives in `.ssot/registry.json`, the generated release views, and current-state docs together.
