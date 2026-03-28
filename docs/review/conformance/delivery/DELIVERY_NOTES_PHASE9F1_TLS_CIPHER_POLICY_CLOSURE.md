# Delivery notes — Phase 9F1 TLS cipher-policy closure

This checkpoint advances **Phase 9F1** of the Phase 9 implementation plan.

## Included work

- public contract freeze for `--ssl-ciphers`
- resolved runtime fields in config / listener normalization
- live package-owned TCP/TLS cipher allowlist selection
- live package-owned QUIC/TLS cipher allowlist selection
- fail-fast validation for invalid expressions
- public API / CLI forwarding coverage
- updated current-state documentation

## Honest status

This repository remains:

- **authoritative-boundary green**
- **strict-target not green**
- **promotion-target not green**

This checkpoint closes the `--ssl-ciphers` flag gap only. The remaining six flag/runtime blockers and the strict performance target still remain.
