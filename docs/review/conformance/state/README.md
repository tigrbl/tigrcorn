# Current-state records

This directory contains the canonical promoted-state pointer and archived historical current-state checkpoints.

## Use these locations first

- current promoted-state pointer: `docs/review/conformance/state/CURRENT_REPOSITORY_STATE.md`
- canonical human current-state chain: `docs/review/conformance/CURRENT_STATE_CHAIN.md`
- canonical machine-readable registry: `.ssot/registry.json`
- machine-readable current-state chain: `docs/review/conformance/current_state_chain.current.json`
- historical checkpoint records: `docs/review/conformance/state/checkpoints/`

## Historical planning and promotion provenance

These files explain how the repository reached the current promoted state and what contracts were frozen at key checkpoints:

- `docs/review/conformance/RELEASE_IMPLEMENTATION_PLAN.md`
- `docs/review/conformance/release_implementation_plan.current.json`
- `docs/review/conformance/PROMOTION_CONTRACT_PROMOTION_CONTRACT_FREEZE.md`
- `docs/review/conformance/promotion_contract_promotion_contract.current.json`
- `docs/review/conformance/PROMOTION_CONTRACT_EXECUTION_BACKLOG.md`
- `docs/review/conformance/promotion_contract_execution_backlog.current.json`
- `docs/review/conformance/RELEASE_ASSEMBLY_AND_CERTIFIABLE_CHECKPOINT.md`
- `docs/review/conformance/release_assembly.current.json`

Treat those as planning/provenance documents, not as competing current-state sources.

Root-level `CURRENT_REPOSITORY_STATE*.md` files are intentionally not used; they were consolidated here to keep the repository root focused on package entrypoint documents.
