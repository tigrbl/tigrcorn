# Phase 9H promotion-evaluator hardening

This checkpoint executes **Phase 9H** of the Phase 9 implementation plan.

It fixes the meta-problem in the strict-promotion program: the promotion evaluator must now enforce the full declared strict-performance contract rather than only the smaller subset that earlier checkpoints happened to check.

## What changed

### 1. The performance evaluator now enforces the declared strict artifact surface

The hardened evaluator now requires all declared performance artifact files, including `correctness.json`, and it treats missing root or per-profile files as explicit failures instead of allowing the tree to drift into a false green state.

### 2. The performance evaluator now requires the declared matrix lanes

The hardened evaluator now requires the matrix and the preserved artifact summary to declare both required lanes:

- `component_regression`
- `end_to_end_release`

### 3. The performance evaluator now requires certification-platform declarations

The hardened evaluator now requires certification-platform declarations in:

- matrix metadata
- per-profile matrix rows
- preserved environment payloads
- preserved command / result / summary artifacts

### 4. The performance evaluator now requires documented SLO coverage per profile

The hardened evaluator now requires each preserved profile to carry the full declared threshold and relative-regression-budget surface rather than only relying on aggregate set coverage across the matrix.

### 5. The performance evaluator now enforces correctness-under-load and live-listener metadata

For RFC-scoped profiles, the hardened evaluator now requires preserved correctness-under-load evidence.

For `end_to_end_release` profiles, the hardened evaluator now requires preserved live-listener metadata in the matrix and in the artifact payloads.

### 6. Negative tests now prove the evaluator fails closed

The repository now preserves negative tests for every intentionally incomplete fixture path required by the Phase 9H plan:

- missing metric key
- missing threshold key
- missing relative-regression budget key
- missing root artifact file
- missing profile artifact file
- missing lane declaration
- missing certification-platform declaration
- missing correctness-under-load metadata
- missing live-listener metadata

## Honest current result

This checkpoint makes the promotion evaluator trustworthy, but it does **not** make the repository fully promotion-ready.

What is true now:

- the authoritative boundary remains green
- the strict target remains not green
- the flag surface is green
- the operator surface is green
- the performance section remains green
- the documentation section remains green
- the composite promotion target remains not green

So the repository is still **not yet certifiably fully featured**, and it is still **not yet strict-target certifiably fully RFC compliant**.

The remaining blockers are now external to evaluator hardening itself:

- the preserved-but-non-passing HTTP/3 `aioquic` strict-target scenarios
- final release assembly under Phase 9I

## Why this phase matters

Without Phase 9H, the repository could report the strict target as green even if part of the declared strict-performance contract had silently fallen out of the preserved artifacts.

After this checkpoint, the promotion evaluator now enforces the strict target honestly.
