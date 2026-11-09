# Optional performance comparisons

These comparison matrices are optional product-performance evidence.

They are tracked in SSOT as implemented performance-comparison surfaces, but they are outside the strict RFC certification boundary and outside the strict release-gate performance proof unless they are explicitly promoted later.

## Current optional comparison matrices

- `docs/review/performance/runtime_comparison_matrix.json`
- `docs/review/performance/aioquic_comparison_matrix.json`
- `docs/review/performance/websocket_peer_comparison_matrix.json`

## What these comparisons prove

- the comparison surface is defined in-repo
- the matrix is executable through the package-owned performance harness
- baseline and current artifact roots are declared and preserved as evidence targets
- thresholds and relative regression budgets are governed per matrix

## What these comparisons do not prove

- they do not strengthen RFC conformance claims
- they do not create independent third-party certification
- they do not automatically enter the strict promotion-grade performance matrix
- they do not become active release proof unless a later change explicitly promotes them
