# Code governance

## Code style

- Python 3.11+ source
- stdlib-first unless an explicit dependency is justified
- package-owned transport/protocol/runtime/security behavior stays package-owned
- no backward-compatibility shims
- no widening of public support through undocumented behavior
- config precedence remains `CLI > env > config file > defaults`

## Code behavior

- changes must preserve the current T/P/A/D/R boundary unless the boundary docs are updated first
- operator-only additions must not be presented as RFC certification claims
- RFC-facing changes must map to the canonical evidence policy before being marketed as complete
- immutable release roots are not a development workspace

## Public-surface discipline

When adding a public flag, API, or operator surface:

1. update code
2. update tests
3. update machine-readable docs
4. update human docs
5. update current-state docs
6. update release artifacts if the change is promotion-relevant

## Documentation discipline

New mutable docs should live under `docs/` short-path folders. Avoid creating new root notes.
