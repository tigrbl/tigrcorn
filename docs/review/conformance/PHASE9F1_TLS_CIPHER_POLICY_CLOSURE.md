# Phase 9F1 TLS cipher-policy closure

This checkpoint executes **Phase 9F1** of the Phase 9 implementation plan.

It closes the public runtime gap for `--ssl-ciphers` by turning the flag from a parse-only surface into a real package-owned TLS/QUIC allowlist control.

## What changed

### 1. The public contract is now frozen and implemented

`--ssl-ciphers` now has a concrete public runtime contract:

- accepted syntax: colon-separated or comma-separated TLS 1.3 suite names
- currently supported names:
  - `TLS_AES_128_GCM_SHA256`
  - `TLS_AES_256_GCM_SHA384`
- TLS version applicability: TLS 1.3 only
- carrier applicability:
  - package-owned TCP/TLS listeners
  - package-owned QUIC/TLS listeners used by HTTP/3

Invalid expressions now fail fast during config normalization / validation.

### 2. The resolved allowlist now survives config normalization

The repository now carries resolved runtime fields so the flag does not disappear after parsing:

- `config.tls.resolved_cipher_suites`
- `listener.ssl_ciphers`
- `listener.resolved_cipher_suites`

That closes the old parse-only gap.

### 3. Package-owned TLS and QUIC now honor the resolved allowlist

The resolved cipher list is now wired into:

- `src/tigrcorn/security/tls.py` for package-owned TCP/TLS listeners
- `src/tigrcorn/protocols/http3/handler.py` for package-owned HTTP/3 / QUIC listeners
- `src/tigrcorn/security/tls13/handshake.py` so the handshake driver actually selects from the configured allowlist rather than the hard-coded default tuple

### 4. The negotiated suite now changes measurably

The new closure tests prove two live outcomes:

- TCP/TLS negotiated suite changes when `--ssl-ciphers TLS_AES_128_GCM_SHA256` is set
- QUIC/TLS negotiated suite changes when `--ssl-ciphers TLS_AES_128_GCM_SHA256` is set

## Honest current result

This checkpoint closes only **9F1**.

What is true now:

- `--ssl-ciphers` is now **implemented**
- the authoritative boundary remains green
- the strict target is not yet green
- the promotion target is still not green
- the remaining flag/runtime blockers are now:
  - `--log-config`
  - `--statsd-host`
  - `--otel-endpoint`
  - `--limit-concurrency`
  - `--websocket-ping-interval`
  - `--websocket-ping-timeout`

So this repository is still **not yet certifiably fully featured** under the stricter promotion target, and it is still **not yet strict-target certifiably fully RFC compliant**.

## Why this phase matters

Before this checkpoint, `--ssl-ciphers` existed as a public flag but did not survive into a live package-owned cipher allowlist.

After this checkpoint, the flag is no longer just a surface claim. It now changes real package-owned TLS 1.3 selection behavior and rejects invalid values before listener start.
