# Strict profile target

This target document defines the stricter next-step target that sits alongside the authoritative current boundary in `docs/review/conformance/CERTIFICATION_BOUNDARY.md`.

## Current truth

- the authoritative boundary remains green
- the 0.3.9 canonical release root is the evaluation substrate for this target
- the strict target is now green
- the composite promotion target is now green
- Step 9 promotion is now complete
- the public package version is `0.3.9`

## Historical guardrail phrases preserved for the promotion evaluator

This document is `docs/review/conformance/STRICT_PROFILE_TARGET.md`.

The authoritative boundary remains green.

Earlier checkpoints treated the frozen 0.3.7 candidate root as non-promotable. The next promotable root must be a new release root. At that point the plan still tracked 13 missing independent scenarios.

## What this target changes

Relative to `docs/review/conformance/certification_boundary.json`, `docs/review/conformance/certification_boundary.strict_target.json` promotes the following RFC surfaces from `local_conformance` to `independent_certification`:

- RFC 7692
- RFC 9110 §9.3.6
- RFC 9110 §6.5
- RFC 9110 §8
- RFC 6960

## Current blockers

- none

## Phase 9I release assembly progress

The 0.3.9 canonical release root now carries the final independent, same-stack, mixed, flag, operator, performance, certification-environment, aioquic-preflight, and strict-validation bundles.

That canonical root is now green under the strict target and the composite promotion target, and the public package version is aligned at `0.3.9`.
