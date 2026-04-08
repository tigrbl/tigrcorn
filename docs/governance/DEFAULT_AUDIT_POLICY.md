# Default Audit Policy

This document governs package-owned default audits and the generated tables derived from code.

Policy:

- Code is the source of truth for defaults. Hand-written prose may summarize defaults, but it must not invent them.
- `DEFAULT_AUDIT.json`, `DEFAULT_AUDIT.md`, and `PROFILE_DEFAULTS/` are generated artifacts and must be refreshed by CI.
- Runtime-randomized values must be represented as explicit runtime-randomized placeholders in audit outputs rather than frozen misleading literals.
- Default changes that alter operator posture must update the generated audits, the reviewed flag contract, and the current-state documentation in the same change.
- Default tables in operator docs must be generated from the same metadata path used by runtime and CLI help.

Phase 8 authority:

- This policy is owned by `tigrcorn-maintainers`.
- Release gates fail closed if the governance graph or default-audit inputs are missing or inconsistent.
