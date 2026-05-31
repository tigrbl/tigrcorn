# Test Style Policy

This document governs forward test-runner motion.

Policy:

- `pytest` is the sole forward runner for CI and promotion-facing validation.
- New tests must be written in pytest style unless they are edits inside an already-inventoried legacy unittest file.
- `LEGACY_UNITTEST_INVENTORY.json` is the approved grandfathered list of unittest-bearing files.
- New unittest-bearing files are forbidden and cause release gates to fail closed.
- Existing legacy unittest files may remain until they are migrated or retired, but they are contained rather than treated as the forward style.

Execution posture:

- CI installs `.[certification,dev]` and runs validation through `python -m pytest`.
- Local environments that lack pytest are not promotion substitutes; they are environment gaps that must be recorded honestly.
