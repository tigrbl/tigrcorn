# Secondary repository-level partials status

The authoritative package-wide certification target remains `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

This document tracks repository-level partials that are no longer the main release-gate blockers but still matter for repository completeness and future-strengthening work.

## Completed in this update

- the archive ships a package-owned production scheduler in `src/tigrcorn/scheduler/runtime.py`
- `src/tigrcorn/server/runner.py` uses that scheduler for connection admission and CONNECT relay task management
- the archive preserves a formal intermediary / proxy seed corpus under `docs/review/conformance/intermediary_proxy_corpus/`
- the archive preserves a provisional QUIC / HTTP/3 flow-control review bundle under `docs/review/conformance/releases/0.3.6/release-0.3.6/tigrcorn-provisional-flow-control-gap-bundle/`
- the primary third-party HTTP/3 / RFC 9220 certification blockers are now closed in the authoritative release gate

## Current honest status

These additions improve repository completeness and remain useful after the primary certification closure.

They are **not** part of the current authoritative release-gate blocker set.

### Scheduler

The scheduler gap recorded in `docs/architecture/scheduler-model.md` is closed as a repository-level partial: a package-owned production scheduler is present in-tree.

### QUIC / HTTP/3 flow control

Broad independent certification beyond the authoritative boundary is still incomplete, but the gap is represented by a formal non-certifying review bundle and status document.

### Intermediary / proxy corpus

A seed corpus is bundled, but broader multi-carrier third-party intermediary / proxy evidence is still incomplete.
